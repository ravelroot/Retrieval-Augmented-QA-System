from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexo import __version__, db, jobs
from nexo.api import schemas as sc
from nexo.api.deps import ApiError, Principal, current_user, get_users
from nexo.config import Settings, get_settings
from nexo.rag import providers
from nexo.rag.engine import get_engine
from nexo.rag.providers import ProviderError
from nexo.security import issue_token
from nexo.users import UserError, UserStore

log = logging.getLogger("nexo.api")
router = APIRouter(prefix="/api")


def _user_error(e: UserError) -> ApiError:
    status = {"INVALID_CREDENTIALS": 401, "LOCKED": 429, "USERNAME_TAKEN": 409}.get(e.code, 400)
    return ApiError(status, e.code, e.message, {e.field: e.message} if e.field else None)


def _session(settings: Settings, user) -> sc.SessionOut:
    token, expires = issue_token(settings, user.username, user.role)
    return sc.SessionOut(token=token, expires_at=expires, user=sc.UserOut(**user.public()))


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/auth/options")
def auth_options(settings: Settings = Depends(get_settings), users: UserStore = Depends(get_users)) -> dict:
    return {"registration": settings.allow_registration, "default_admin": users.default_admin_active()}


@router.post("/auth/login", response_model=sc.SessionOut)
def login(body: sc.LoginIn, settings: Settings = Depends(get_settings), users: UserStore = Depends(get_users)):
    try:
        return _session(settings, users.authenticate(body.username, body.password))
    except UserError as e:
        raise _user_error(e)


@router.post("/auth/register", response_model=sc.SessionOut, status_code=201)
def register(body: sc.RegisterIn, settings: Settings = Depends(get_settings), users: UserStore = Depends(get_users)):
    if not settings.allow_registration:
        raise ApiError(403, "REGISTRATION_DISABLED", "O cadastro de novas contas está desativado.")
    try:
        return _session(settings, users.register(body.name, body.username, body.password))
    except UserError as e:
        raise _user_error(e)


@router.get("/auth/me", response_model=sc.UserOut)
def me(p: Principal = Depends(current_user), users: UserStore = Depends(get_users)):
    return sc.UserOut(**users.get(p.username).public())


@router.put("/auth/password", status_code=204)
def change_password(body: sc.PasswordIn, p: Principal = Depends(current_user), users: UserStore = Depends(get_users)):
    try:
        users.change_password(p.username, body.current_password, body.new_password)
    except UserError as e:
        raise _user_error(e)
    return Response(status_code=204)


@router.get("/system/status")
def status(p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
           database: Session = Depends(db.get_db), users: UserStore = Depends(get_users)) -> dict:
    counts = dict(database.execute(select(db.DocumentRow.status, func.count()).group_by(db.DocumentRow.status)).all())
    chunks = database.scalar(select(func.coalesce(func.sum(db.DocumentRow.chunks), 0))) or 0
    return {
        "version": __version__,
        "providers": providers.describe(settings),
        "documents": {"total": sum(counts.values()), "by_status": counts, "chunks": int(chunks)},
        "users": len(users.all()) if p.is_admin else None,
        "registration": settings.allow_registration,
        "database": "SQLite" if settings.sqlalchemy_url.startswith("sqlite") else settings.sqlalchemy_url.split(":")[0],
    }


def _doc_out(row: db.DocumentRow, p: Principal) -> sc.DocumentOut:
    out = sc.DocumentOut.model_validate(row, from_attributes=True)
    out.can_delete = p.is_admin or row.uploaded_by == p.username
    return out


def _clean_filename(name: str) -> str:
    base = Path(name or "documento.pdf").name
    base = re.sub(r"[^\w.\- ()]+", "_", base, flags=re.UNICODE).strip() or "documento.pdf"
    return base[:255]


@router.get("/documents", response_model=list[sc.DocumentOut])
def list_documents(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    rows = database.scalars(select(db.DocumentRow).order_by(db.DocumentRow.created_at.desc())).all()
    return [_doc_out(r, p) for r in rows]


@router.post("/documents", response_model=list[sc.DocumentOut], status_code=201)
async def upload(files: list[UploadFile] = File(...), p: Principal = Depends(current_user),
                 settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    if not files:
        raise ApiError(400, "NO_FILES", "Escolha ao menos um PDF.")
    limit = settings.max_upload_mb * 1024 * 1024
    created: list[db.DocumentRow] = []
    for f in files:
        name = _clean_filename(f.filename or "")
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise ApiError(413, "FILE_TOO_LARGE", f"{name} passa do limite de {settings.max_upload_mb} MB.")
        if not data.startswith(b"%PDF"):
            raise ApiError(415, "NOT_A_PDF", f"{name} não é um PDF válido.")
        digest = hashlib.sha256(data).hexdigest()
        existing = database.scalar(select(db.DocumentRow).where(db.DocumentRow.sha256 == digest))
        if existing is not None:
            raise ApiError(409, "DUPLICATE", f"{name} já foi enviado como \"{existing.title}\".")
        row = db.DocumentRow(title=Path(name).stem[:200], filename=name, sha256=digest, size_bytes=len(data),
                             uploaded_by=p.username, status="PENDING")
        database.add(row)
        database.flush()
        path = jobs.pdf_path(row.id)
        path.write_bytes(data)
        try:
            meta = PdfReader(str(path)).metadata
            if meta and meta.title and meta.title.strip():
                row.title = meta.title.strip()[:200]
        except Exception:
            pass
        created.append(row)
    database.commit()
    for row in created:
        jobs.enqueue(row.id)
    return [_doc_out(r, p) for r in created]


def _document(database: Session, document_id: str) -> db.DocumentRow:
    row = database.get(db.DocumentRow, document_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Documento não encontrado.")
    return row


@router.get("/documents/{document_id}", response_model=sc.DocumentOut)
def get_document(document_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    return _doc_out(_document(database, document_id), p)


@router.patch("/documents/{document_id}", response_model=sc.DocumentOut)
def rename_document(document_id: str, body: sc.DocumentPatch, p: Principal = Depends(current_user),
                    database: Session = Depends(db.get_db)):
    row = _document(database, document_id)
    if not (p.is_admin or row.uploaded_by == p.username):
        raise ApiError(403, "FORBIDDEN", "Só quem enviou o documento ou um administrador pode alterá-lo.")
    row.title = " ".join(body.title.split())[:200]
    database.commit()
    if row.status == "READY":
        row.status = "PENDING"
        database.commit()
        jobs.enqueue(row.id)
    return _doc_out(row, p)


@router.get("/documents/{document_id}/file")
def document_file(document_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _document(database, document_id)
    path = jobs.pdf_path(row.id)
    if not path.exists():
        raise ApiError(404, "FILE_MISSING", "O arquivo original não está mais na pasta de uploads.")
    return FileResponse(path, media_type="application/pdf", filename=row.filename,
                        content_disposition_type="inline")


@router.post("/documents/{document_id}/reindex", response_model=sc.DocumentOut)
def reindex(document_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _document(database, document_id)
    if not (p.is_admin or row.uploaded_by == p.username):
        raise ApiError(403, "FORBIDDEN", "Só quem enviou o documento ou um administrador pode reindexá-lo.")
    if not jobs.pdf_path(row.id).exists():
        raise ApiError(404, "FILE_MISSING", "O arquivo original não está mais na pasta de uploads.")
    row.status = "PENDING"
    row.error = None
    database.commit()
    jobs.enqueue(row.id)
    return _doc_out(row, p)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                    database: Session = Depends(db.get_db)):
    row = _document(database, document_id)
    if not (p.is_admin or row.uploaded_by == p.username):
        raise ApiError(403, "FORBIDDEN", "Só quem enviou o documento ou um administrador pode excluí-lo.")
    try:
        get_engine(settings).delete(row.id)
    except ProviderError as e:
        raise ApiError(503, "PROVIDER", str(e))
    database.delete(row)
    database.commit()
    jobs.pdf_path(document_id).unlink(missing_ok=True)
    return Response(status_code=204)


def _message_out(m: db.MessageRow, username: str) -> sc.MessageOut:
    rating = next((f.rating for f in m.feedback if f.owner == username), None)
    return sc.MessageOut(
        id=m.id, role=m.role, content=m.content, answered=m.answered, grounded=m.grounded, model=m.model,
        latency_ms=m.latency_ms, created_at=m.created_at, my_rating=rating,
        sources=[sc.SourceOut(rank=s.rank, document_id=s.document_id, document_title=s.document_title, page=s.page,
                              similarity=s.similarity, rerank_score=s.rerank_score, excerpt=s.excerpt)
                 for s in m.sources])


def _summary(c: db.ConversationRow) -> sc.ConversationSummary:
    return sc.ConversationSummary(id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at,
                                  document_ids=[d.id for d in c.documents], messages=len(c.messages))


def _conversation(database: Session, conversation_id: str, p: Principal) -> db.ConversationRow:
    c = database.get(db.ConversationRow, conversation_id)
    if c is None or c.owner != p.username:
        raise ApiError(404, "NOT_FOUND", "Conversa não encontrada.")
    return c


def _documents(database: Session, ids: list[str]) -> list[db.DocumentRow]:
    if not ids:
        return []
    rows = database.scalars(select(db.DocumentRow).where(db.DocumentRow.id.in_(set(ids)))).all()
    if len(rows) != len(set(ids)):
        raise ApiError(400, "UNKNOWN_DOCUMENT", "Um dos documentos escolhidos não existe mais.")
    return list(rows)


@router.get("/conversations", response_model=list[sc.ConversationSummary])
def list_conversations(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    rows = database.scalars(select(db.ConversationRow).where(db.ConversationRow.owner == p.username)
                            .order_by(db.ConversationRow.updated_at.desc())).all()
    return [_summary(c) for c in rows]


@router.post("/conversations", response_model=sc.ConversationOut, status_code=201)
def create_conversation(body: sc.ConversationIn, p: Principal = Depends(current_user),
                        database: Session = Depends(db.get_db)):
    c = db.ConversationRow(owner=p.username, title=(body.title or "Nova conversa").strip()[:160] or "Nova conversa")
    c.documents = _documents(database, body.document_ids)
    database.add(c)
    database.commit()
    return sc.ConversationOut(**_summary(c).model_dump(), items=[])


@router.get("/conversations/{conversation_id}", response_model=sc.ConversationOut)
def get_conversation(conversation_id: str, p: Principal = Depends(current_user),
                     database: Session = Depends(db.get_db)):
    c = _conversation(database, conversation_id, p)
    return sc.ConversationOut(**_summary(c).model_dump(), items=[_message_out(m, p.username) for m in c.messages])


@router.patch("/conversations/{conversation_id}", response_model=sc.ConversationSummary)
def update_conversation(conversation_id: str, body: sc.ConversationPatch, p: Principal = Depends(current_user),
                        database: Session = Depends(db.get_db)):
    c = _conversation(database, conversation_id, p)
    if body.title is not None:
        c.title = " ".join(body.title.split())[:160]
    if body.document_ids is not None:
        c.documents = _documents(database, body.document_ids)
    c.updated_at = db.utcnow()
    database.commit()
    return _summary(c)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, p: Principal = Depends(current_user),
                        database: Session = Depends(db.get_db)):
    database.delete(_conversation(database, conversation_id, p))
    database.commit()
    return Response(status_code=204)


@router.post("/conversations/{conversation_id}/messages", response_model=sc.ExchangeOut)
def ask(conversation_id: str, body: sc.QuestionIn, p: Principal = Depends(current_user),
        settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    c = _conversation(database, conversation_id, p)
    question = body.content.strip()
    if not question:
        raise ApiError(400, "EMPTY", "Escreva uma pergunta.", {"content": "Escreva uma pergunta."})
    ready = database.scalar(select(func.count()).select_from(db.DocumentRow).where(db.DocumentRow.status == "READY"))
    if not ready:
        raise ApiError(409, "NO_DOCUMENTS", "Envie e aguarde a indexação de ao menos um PDF antes de perguntar.")
    history = [(m.role, m.content) for m in c.messages]
    scope = [d.id for d in c.documents]
    try:
        result = get_engine(settings).ask(question, history, scope or None)
    except ProviderError as e:
        raise ApiError(503, "PROVIDER", str(e))
    except Exception as e:
        log.exception("Falha ao responder")
        raise ApiError(502, "LLM_FAILURE", f"O modelo não respondeu: {e}")
    user_msg = db.MessageRow(conversation_id=c.id, role="user", content=question)
    database.add(user_msg)
    database.flush()
    answer = db.MessageRow(conversation_id=c.id, role="assistant", content=result.text, answered=result.answered,
                           grounded=result.grounded, model=result.model, latency_ms=result.latency_ms,
                           created_at=db.utcnow())
    answer.sources = [db.SourceRow(document_id=s.document_id or None, document_title=s.document_title,
                                   chunk_id=s.chunk_id, page=s.page, rank=s.rank, similarity=s.similarity,
                                   rerank_score=s.rerank_score, excerpt=s.excerpt) for s in result.sources]
    database.add(answer)
    if c.title == "Nova conversa":
        c.title = (question[:77] + "…") if len(question) > 80 else question
    c.updated_at = db.utcnow()
    database.commit()
    database.refresh(c)
    return sc.ExchangeOut(question=_message_out(user_msg, p.username), answer=_message_out(answer, p.username),
                          conversation=_summary(c))


@router.post("/messages/{message_id}/feedback", response_model=sc.MessageOut)
def feedback(message_id: str, body: sc.FeedbackIn, p: Principal = Depends(current_user),
             database: Session = Depends(db.get_db)):
    m = database.get(db.MessageRow, message_id)
    if m is None or m.role != "assistant" or m.conversation.owner != p.username:
        raise ApiError(404, "NOT_FOUND", "Resposta não encontrada.")
    current = next((f for f in m.feedback if f.owner == p.username), None)
    if body.rating == 0:
        if current is not None:
            database.delete(current)
    elif current is None:
        m.feedback.append(db.FeedbackRow(owner=p.username, rating=body.rating, comment=body.comment))
    else:
        current.rating = body.rating
        current.comment = body.comment
    database.commit()
    database.refresh(m)
    return _message_out(m, p.username)
