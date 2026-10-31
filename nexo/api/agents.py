from __future__ import annotations

import hashlib
import re

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexo import db, jobs
from nexo.api import schemas as sc
from nexo.api.deps import ApiError, Principal, current_user
from nexo.api.routes import _doc_out, _document, _slug, file_on_disk, get_base, store_files
from nexo.config import Settings, get_settings
from nexo.rag.engine import get_engine
from nexo.rag.providers import ProviderError

router = APIRouter(prefix="/api")

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _color(value: str | None, fallback: str = "#000000") -> str:
    return value if value and COLOR_RE.match(value) else fallback


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _base_out(database: Session, row: db.KnowledgeBaseRow, p: Principal) -> sc.BaseOut:
    docs = database.execute(select(db.DocumentRow.status, db.DocumentRow.kind, db.DocumentRow.pages,
                                   db.DocumentRow.chunks).where(db.DocumentRow.base_id == row.id)).all()
    ready = [d for d in docs if d.status == "READY"]
    bots = database.scalar(select(func.count()).select_from(db.BotRow).where(db.BotRow.base_id == row.id)) or 0
    return sc.BaseOut(
        id=row.id, name=row.name, description=row.description, color=row.color, is_default=row.is_default,
        created_by=row.created_by, created_at=row.created_at, updated_at=row.updated_at, documents=len(docs),
        ready=len(ready), processing=sum(1 for d in docs if d.status in ("PENDING", "PROCESSING")),
        failed=sum(1 for d in docs if d.status == "FAILED"), notes=sum(1 for d in docs if d.kind == "note"),
        files=sum(1 for d in docs if d.kind != "note"), pages=sum(d.pages for d in ready),
        chunks=sum(d.chunks for d in ready), bots=int(bots), can_edit=p.is_admin or row.created_by == p.username)


def _editable_base(database: Session, base_id: str, p: Principal) -> db.KnowledgeBaseRow:
    row = get_base(database, base_id)
    if not (p.is_admin or row.created_by == p.username):
        raise ApiError(403, "FORBIDDEN", "Só quem criou a base ou um administrador pode alterá-la.")
    return row


@router.get("/bases", response_model=list[sc.BaseOut])
def list_bases(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    rows = database.scalars(select(db.KnowledgeBaseRow).order_by(db.KnowledgeBaseRow.is_default.desc(),
                                                                 db.KnowledgeBaseRow.name)).all()
    return [_base_out(database, r, p) for r in rows]


@router.post("/bases", response_model=sc.BaseOut, status_code=201)
def create_base(body: sc.BaseIn, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    name = " ".join(body.name.split())[:120]
    if not name:
        raise ApiError(400, "EMPTY", "Dê um nome à base.", {"name": "Dê um nome à base."})
    if database.scalar(select(db.KnowledgeBaseRow).where(func.lower(db.KnowledgeBaseRow.name) == name.lower())):
        raise ApiError(409, "NAME_TAKEN", "Já existe uma base com esse nome.", {"name": "Já existe uma base com esse nome."})
    row = db.KnowledgeBaseRow(name=name, description=_clean(body.description), color=_color(body.color),
                              is_default=False, created_by=p.username)
    database.add(row)
    database.commit()
    return _base_out(database, row, p)


@router.get("/bases/{base_id}", response_model=sc.BaseOut)
def get_one_base(base_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    return _base_out(database, get_base(database, base_id), p)


@router.patch("/bases/{base_id}", response_model=sc.BaseOut)
def update_base(base_id: str, body: sc.BasePatch, p: Principal = Depends(current_user),
                database: Session = Depends(db.get_db)):
    row = _editable_base(database, base_id, p)
    if body.name is not None:
        name = " ".join(body.name.split())[:120]
        clash = database.scalar(select(db.KnowledgeBaseRow).where(func.lower(db.KnowledgeBaseRow.name) == name.lower(),
                                                                  db.KnowledgeBaseRow.id != row.id))
        if clash is not None:
            raise ApiError(409, "NAME_TAKEN", "Já existe uma base com esse nome.",
                           {"name": "Já existe uma base com esse nome."})
        row.name = name
    if body.description is not None:
        row.description = _clean(body.description)
    if body.color is not None:
        row.color = _color(body.color, row.color)
    row.updated_at = db.utcnow()
    database.commit()
    return _base_out(database, row, p)


@router.delete("/bases/{base_id}", status_code=204)
def delete_base(base_id: str, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                database: Session = Depends(db.get_db)):
    row = _editable_base(database, base_id, p)
    if row.is_default:
        raise ApiError(409, "DEFAULT_BASE", "A base padrão não pode ser excluída. Você pode renomeá-la.")
    bots = database.scalars(select(db.BotRow.name).where(db.BotRow.base_id == row.id)).all()
    if bots:
        raise ApiError(409, "BASE_IN_USE", f"Esta base é usada por {', '.join(bots)}. Troque a base desses agentes antes.")
    docs = database.scalars(select(db.DocumentRow).where(db.DocumentRow.base_id == row.id)).all()
    try:
        for d in docs:
            get_engine(settings).delete(d.id)
    except ProviderError as e:
        raise ApiError(503, "PROVIDER", str(e))
    paths = [file_on_disk(d) for d in docs if d.kind != "note"]
    for d in docs:
        database.delete(d)
    database.delete(row)
    database.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    return Response(status_code=204)


@router.get("/bases/{base_id}/documents", response_model=list[sc.DocumentOut])
def base_documents(base_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    get_base(database, base_id)
    rows = database.scalars(select(db.DocumentRow).where(db.DocumentRow.base_id == base_id)
                            .order_by(db.DocumentRow.created_at.desc())).all()
    return [_doc_out(r, p) for r in rows]


@router.post("/bases/{base_id}/documents", response_model=list[sc.DocumentOut], status_code=201)
async def base_upload(base_id: str, files: list[UploadFile] = File(...), p: Principal = Depends(current_user),
                      settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    base = get_base(database, base_id)
    created = await store_files(database, files, base.id, p, settings)
    return [_doc_out(r, p) for r in created]


def _text_hash(title: str, content: str) -> str:
    return hashlib.sha256(f"nota\n{title}\n{content}".encode("utf-8")).hexdigest()


@router.post("/bases/{base_id}/texts", response_model=sc.DocumentOut, status_code=201)
def create_text(base_id: str, body: sc.TextIn, p: Principal = Depends(current_user),
                database: Session = Depends(db.get_db)):
    base = get_base(database, base_id)
    title = " ".join(body.title.split())[:200]
    content = body.content.strip()
    if not title or not content:
        raise ApiError(400, "EMPTY", "Preencha o título e o texto.")
    digest = _text_hash(title, content)
    if database.scalar(select(db.DocumentRow).where(db.DocumentRow.base_id == base.id, db.DocumentRow.sha256 == digest)):
        raise ApiError(409, "DUPLICATE", "Esse texto já está nesta base.")
    row = db.DocumentRow(title=title, filename=f"{_slug(title)}.txt", sha256=digest,
                         size_bytes=len(content.encode("utf-8")), uploaded_by=p.username, status="PENDING",
                         base_id=base.id, kind="note", extension="note", content=content)
    database.add(row)
    database.commit()
    jobs.enqueue(row.id)
    return _doc_out(row, p)


@router.get("/documents/{document_id}/text", response_model=sc.TextOut)
def read_text(document_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _document(database, document_id)
    if row.kind != "note":
        raise ApiError(400, "NOT_A_TEXT", "Este item é um arquivo, não um texto editável.")
    return sc.TextOut(title=row.title, content=row.content or "")


@router.put("/documents/{document_id}/text", response_model=sc.DocumentOut)
def update_text(document_id: str, body: sc.TextIn, p: Principal = Depends(current_user),
                database: Session = Depends(db.get_db)):
    row = _document(database, document_id)
    if row.kind != "note":
        raise ApiError(400, "NOT_A_TEXT", "Este item é um arquivo, não um texto editável.")
    base = get_base(database, row.base_id)
    if not (p.is_admin or row.uploaded_by == p.username or base.created_by == p.username):
        raise ApiError(403, "FORBIDDEN", "Só quem escreveu o texto, o dono da base ou um administrador pode editá-lo.")
    title = " ".join(body.title.split())[:200]
    content = body.content.strip()
    digest = _text_hash(title, content)
    clash = database.scalar(select(db.DocumentRow).where(db.DocumentRow.base_id == row.base_id,
                                                         db.DocumentRow.sha256 == digest, db.DocumentRow.id != row.id))
    if clash is not None:
        raise ApiError(409, "DUPLICATE", "Já existe um texto igual nesta base.")
    row.title = title
    row.content = content
    row.sha256 = digest
    row.filename = f"{_slug(title)}.txt"
    row.size_bytes = len(content.encode("utf-8"))
    row.updated_at = db.utcnow()
    row.status = "PENDING"
    database.commit()
    jobs.enqueue(row.id)
    return _doc_out(row, p)


def _bot_out(database: Session, row: db.BotRow, p: Principal) -> sc.BotOut:
    conversations = database.scalar(select(func.count()).select_from(db.ConversationRow)
                                    .where(db.ConversationRow.bot_id == row.id,
                                           db.ConversationRow.owner == p.username)) or 0
    ready = database.scalar(select(func.count()).select_from(db.DocumentRow)
                            .where(db.DocumentRow.base_id == row.base_id, db.DocumentRow.status == "READY")) or 0
    return sc.BotOut(id=row.id, name=row.name, description=row.description, base_id=row.base_id,
                     base_name=row.base.name if row.base is not None else "", instructions=row.instructions,
                     greeting=row.greeting, fallback=row.fallback, color=row.color, cite_sources=row.cite_sources,
                     created_by=row.created_by, created_at=row.created_at, updated_at=row.updated_at,
                     conversations=int(conversations), ready=ready > 0,
                     can_edit=p.is_admin or row.created_by == p.username)


def _bot(database: Session, bot_id: str) -> db.BotRow:
    row = database.get(db.BotRow, bot_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Agente não encontrado.")
    return row


def _editable_bot(database: Session, bot_id: str, p: Principal) -> db.BotRow:
    row = _bot(database, bot_id)
    if not (p.is_admin or row.created_by == p.username):
        raise ApiError(403, "FORBIDDEN", "Só quem criou o agente ou um administrador pode alterá-lo.")
    return row


@router.get("/bots", response_model=list[sc.BotOut])
def list_bots(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    rows = database.scalars(select(db.BotRow).order_by(db.BotRow.name)).all()
    return [_bot_out(database, r, p) for r in rows]


@router.post("/bots", response_model=sc.BotOut, status_code=201)
def create_bot(body: sc.BotIn, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    name = " ".join(body.name.split())[:80]
    if not name:
        raise ApiError(400, "EMPTY", "Dê um nome ao agente.", {"name": "Dê um nome ao agente."})
    base = get_base(database, body.base_id)
    row = db.BotRow(name=name, base_id=base.id, description=_clean(body.description),
                    instructions=_clean(body.instructions), greeting=_clean(body.greeting),
                    fallback=_clean(body.fallback), color=_color(body.color), cite_sources=body.cite_sources,
                    created_by=p.username)
    database.add(row)
    database.commit()
    database.refresh(row)
    return _bot_out(database, row, p)


@router.get("/bots/{bot_id}", response_model=sc.BotOut)
def get_bot(bot_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    return _bot_out(database, _bot(database, bot_id), p)


@router.patch("/bots/{bot_id}", response_model=sc.BotOut)
def update_bot(bot_id: str, body: sc.BotPatch, p: Principal = Depends(current_user),
               database: Session = Depends(db.get_db)):
    row = _editable_bot(database, bot_id, p)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        row.name = " ".join(data["name"].split())[:80] or row.name
    if data.get("base_id"):
        row.base_id = get_base(database, data["base_id"]).id
    for field in ("description", "instructions", "greeting", "fallback"):
        if field in data:
            setattr(row, field, _clean(data[field]))
    if data.get("color"):
        row.color = _color(data["color"], row.color)
    if data.get("cite_sources") is not None:
        row.cite_sources = data["cite_sources"]
    row.updated_at = db.utcnow()
    database.commit()
    database.refresh(row)
    return _bot_out(database, row, p)


@router.delete("/bots/{bot_id}", status_code=204)
def delete_bot(bot_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _editable_bot(database, bot_id, p)
    for c in database.scalars(select(db.ConversationRow).where(db.ConversationRow.bot_id == row.id)).all():
        database.delete(c)
    for channel in database.scalars(select(db.WhatsAppChannelRow).where(db.WhatsAppChannelRow.bot_id == row.id)).all():
        channel.bot_id = None
    database.delete(row)
    database.commit()
    return Response(status_code=204)
