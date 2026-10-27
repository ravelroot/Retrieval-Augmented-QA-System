from __future__ import annotations

import hashlib
import logging
import math
import re
import secrets
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pypdf import PdfReader
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from nexo import __version__, db, jobs, webhooks
from nexo.api import schemas as sc
from nexo.api.deps import ApiError, Principal, current_user, get_users
from nexo.config import Settings, get_settings
from nexo.rag import providers
from nexo.rag.engine import Answer, get_engine
from nexo.rag.providers import ProviderError
from nexo.security import hash_api_key, issue_token, new_api_key
from nexo.users import UserError, UserStore

log = logging.getLogger("nexo.api")
router = APIRouter(prefix="/api")


def _user_error(e: UserError) -> ApiError:
    status = {"INVALID_CREDENTIALS": 401, "LOCKED": 429, "USERNAME_TAKEN": 409, "NOT_FOUND": 404}.get(e.code, 400)
    return ApiError(status, e.code, e.message, {e.field: e.message} if e.field else None)


def _session(settings: Settings, user) -> sc.SessionOut:
    token, expires = issue_token(settings, user.username, user.role)
    return sc.SessionOut(token=token, expires_at=expires, user=sc.UserOut(**user.public()))


def _require_admin(p: Principal, message: str) -> None:
    if not p.is_admin:
        raise ApiError(403, "FORBIDDEN", message)


def _require_ready(database: Session, action: str) -> None:
    ready = database.scalar(select(func.count()).select_from(db.DocumentRow).where(db.DocumentRow.status == "READY"))
    if not ready:
        raise ApiError(409, "NO_DOCUMENTS", f"Envie e aguarde a indexação de ao menos um PDF antes de {action}.")


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
    keys = database.scalar(select(func.count()).select_from(db.ApiKeyRow).where(db.ApiKeyRow.owner == p.username))
    hooks = database.scalar(select(func.count()).select_from(db.WebhookRow)) if p.is_admin else None
    return {
        "version": __version__,
        "providers": providers.describe(settings),
        "documents": {"total": sum(counts.values()), "by_status": counts, "chunks": int(chunks)},
        "users": len(users.all()) if p.is_admin else None,
        "registration": settings.allow_registration,
        "database": "SQLite" if settings.sqlalchemy_url.startswith("sqlite") else settings.sqlalchemy_url.split(":")[0],
        "integrations": {"api_keys": int(keys or 0), "webhooks": int(hooks or 0) if p.is_admin else None},
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


def _source_out(s) -> sc.SourceOut:
    return sc.SourceOut(rank=s.rank, document_id=s.document_id or None, document_title=s.document_title, page=s.page,
                        similarity=s.similarity, rerank_score=s.rerank_score, excerpt=s.excerpt)


def _message_out(m: db.MessageRow, username: str) -> sc.MessageOut:
    rating = next((f.rating for f in m.feedback if f.owner == username), None)
    return sc.MessageOut(
        id=m.id, role=m.role, content=m.content, answered=m.answered, grounded=m.grounded, model=m.model,
        latency_ms=m.latency_ms, created_at=m.created_at, my_rating=rating,
        sources=[_source_out(s) for s in m.sources])


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


def _slug(text: str) -> str:
    base = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60].strip("-") or "conversa"


def _when(value: datetime) -> str:
    return value.strftime("%d/%m/%Y %H:%M") + " (UTC)"


def _markdown(c: db.ConversationRow, exported: datetime) -> str:
    scope = ", ".join(d.title for d in c.documents) or "Todos os documentos"
    lines = [f"# {c.title}", "", f"- Data: {_when(c.created_at)}", f"- Escopo: {scope}",
             f"- Exportada em: {_when(exported)}", ""]
    for m in c.messages:
        if m.role == "user":
            lines += [f"## {' '.join(m.content.split())}", ""]
            continue
        lines += [m.content.strip(), ""]
        if m.sources:
            lines += ["**Fontes**", ""]
            lines += [f"- [{s.rank}] {s.document_title}, página {s.page}" for s in m.sources]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@router.get("/conversations/{conversation_id}/export")
def export_conversation(conversation_id: str, fmt: Literal["markdown", "json"] = Query("markdown", alias="format"),
                        p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    c = _conversation(database, conversation_id, p)
    name = f"nexo-{_slug(c.title)}"
    exported = db.utcnow()
    if fmt == "json":
        out = sc.ConversationExport(**_summary(c).model_dump(), items=[_message_out(m, p.username) for m in c.messages],
                                    exported_at=exported)
        return Response(out.model_dump_json(indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
    return Response(_markdown(c, exported), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}.md"'})


def _run(settings: Settings, question: str, history: list[tuple[str, str]], scope: list[str]) -> Answer:
    try:
        return get_engine(settings).ask(question, history, scope or None)
    except ProviderError as e:
        raise ApiError(503, "PROVIDER", str(e))
    except Exception as e:
        log.exception("Falha ao responder")
        raise ApiError(502, "LLM_FAILURE", f"O modelo não respondeu: {e}")


def _store_exchange(database: Session, c: db.ConversationRow, question: str,
                    result: Answer) -> tuple[db.MessageRow, db.MessageRow]:
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
    return user_msg, answer


def _notify_unanswered(result: Answer, question: str, conversation_id: str | None, p: Principal) -> None:
    if not result.answered:
        webhooks.emit("question.unanswered",
                      {"question": question, "conversation_id": conversation_id, "username": p.username})


@router.post("/conversations/{conversation_id}/messages", response_model=sc.ExchangeOut)
def ask(conversation_id: str, body: sc.QuestionIn, p: Principal = Depends(current_user),
        settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    c = _conversation(database, conversation_id, p)
    question = body.content.strip()
    if not question:
        raise ApiError(400, "EMPTY", "Escreva uma pergunta.", {"content": "Escreva uma pergunta."})
    _require_ready(database, "perguntar")
    result = _run(settings, question, [(m.role, m.content) for m in c.messages], [d.id for d in c.documents])
    user_msg, answer = _store_exchange(database, c, question, result)
    _notify_unanswered(result, question, c.id, p)
    return sc.ExchangeOut(question=_message_out(user_msg, p.username), answer=_message_out(answer, p.username),
                          conversation=_summary(c))


@router.post("/ask", response_model=sc.AskOut)
def ask_direct(body: sc.AskIn, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
               database: Session = Depends(db.get_db)):
    c = _conversation(database, body.conversation_id, p) if body.conversation_id else None
    question = body.question.strip()
    if not question:
        raise ApiError(400, "EMPTY", "Escreva uma pergunta.", {"question": "Escreva uma pergunta."})
    _require_ready(database, "perguntar")
    if body.document_ids:
        scope = [d.id for d in _documents(database, body.document_ids)]
    else:
        scope = [d.id for d in c.documents] if c else []
    history = [(m.role, m.content) for m in c.messages] if c else []
    result = _run(settings, question, history, scope)
    if c is None:
        sources = [_source_out(s) for s in result.sources]
    else:
        _, answer = _store_exchange(database, c, question, result)
        sources = [_source_out(s) for s in answer.sources]
    _notify_unanswered(result, question, c.id if c else None, p)
    return sc.AskOut(answer=result.text, answered=result.answered, grounded=result.grounded, model=result.model,
                     latency_ms=result.latency_ms, conversation_id=c.id if c else None, sources=sources)


@router.post("/search", response_model=sc.SearchOut)
def search(body: sc.SearchIn, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
           database: Session = Depends(db.get_db)):
    query = body.query.strip()
    if not query:
        raise ApiError(400, "EMPTY", "Escreva o que buscar.", {"query": "Escreva o que buscar."})
    _require_ready(database, "buscar")
    scope = [d.id for d in _documents(database, body.document_ids)]
    started = time.perf_counter()
    try:
        found = get_engine(settings).search(query, scope or None, rerank=body.rerank, limit=body.limit)
    except ProviderError as e:
        raise ApiError(503, "PROVIDER", str(e))
    except Exception as e:
        log.exception("Falha na busca")
        raise ApiError(502, "SEARCH_FAILURE", f"A busca falhou: {e}")
    took = int((time.perf_counter() - started) * 1000)
    return sc.SearchOut(query=query, took_ms=took, results=[_source_out(s) for s in found])


def _question_for(m: db.MessageRow) -> str:
    items = m.conversation.messages
    index = next((i for i, x in enumerate(items) if x.id == m.id), len(items))
    return next((x.content for x in reversed(items[:index]) if x.role == "user"), "")


@router.post("/messages/{message_id}/feedback", response_model=sc.MessageOut)
def feedback(message_id: str, body: sc.FeedbackIn, p: Principal = Depends(current_user),
             database: Session = Depends(db.get_db)):
    m = database.get(db.MessageRow, message_id)
    if m is None or m.role != "assistant" or m.conversation.owner != p.username:
        raise ApiError(404, "NOT_FOUND", "Resposta não encontrada.")
    current = next((f for f in m.feedback if f.owner == p.username), None)
    previous = current.rating if current is not None else None
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
    if body.rating == -1 and previous != -1:
        webhooks.emit("feedback.negative", {"message_id": m.id, "question": _question_for(m), "answer": m.content,
                                            "username": p.username})
    return _message_out(m, p.username)


def _pairs(rows: list[db.MessageRow]) -> list[tuple[db.MessageRow, db.MessageRow | None]]:
    by_conversation: dict[str, list[db.MessageRow]] = defaultdict(list)
    for m in rows:
        by_conversation[m.conversation_id].append(m)
    pairs: list[tuple[db.MessageRow, db.MessageRow | None]] = []
    for items in by_conversation.values():
        items.sort(key=lambda m: (m.created_at, m.role != "user"))
        pending: db.MessageRow | None = None
        for m in items:
            if m.role == "user":
                if pending is not None:
                    pairs.append((pending, None))
                pending = m
            elif pending is not None:
                pairs.append((pending, m))
                pending = None
        if pending is not None:
            pairs.append((pending, None))
    return pairs


@router.get("/metrics", response_model=sc.MetricsOut)
def metrics(days: int = Query(30, ge=1, le=365), p: Principal = Depends(current_user),
            database: Session = Depends(db.get_db)):
    first = db.utcnow().date() - timedelta(days=days - 1)
    query = (select(db.MessageRow).join(db.ConversationRow, db.MessageRow.conversation_id == db.ConversationRow.id)
             .where(db.MessageRow.created_at >= datetime.combine(first, datetime.min.time())))
    if not p.is_admin:
        query = query.where(db.ConversationRow.owner == p.username)
    pairs = _pairs(list(database.scalars(query).all()))
    answers = [a for _, a in pairs if a is not None]
    answered = sum(1 for a in answers if a.answered)
    missed = [(q, a) for q, a in pairs if a is not None and a.answered is False]
    latencies = sorted(a.latency_ms for a in answers if a.latency_ms is not None)
    votes = [f.rating for a in answers for f in a.feedback]

    per_day = Counter(q.created_at.date() for q, _ in pairs)
    missed_per_day = Counter(q.created_at.date() for q, _ in missed)
    daily = [sc.DailyCount(date=d.isoformat(), questions=per_day[d], unanswered=missed_per_day[d])
             for d in (first + timedelta(days=i) for i in range(days))]

    citations: Counter[str] = Counter()
    origin: dict[str, tuple[str | None, str]] = {}
    for a in answers:
        for s in a.sources:
            key = s.document_id or f"titulo:{s.document_title}"
            citations[key] += 1
            origin.setdefault(key, (s.document_id, s.document_title))
    top = sorted(citations.items(), key=lambda kv: (-kv[1], origin[kv[0]][1].lower()))[:6]
    ids = [origin[k][0] for k, _ in top if origin[k][0]]
    titles = dict(database.execute(select(db.DocumentRow.id, db.DocumentRow.title)
                                   .where(db.DocumentRow.id.in_(ids))).all()) if ids else {}
    top_documents = [sc.DocumentCitations(document_id=origin[k][0], title=titles.get(origin[k][0], origin[k][1]),
                                          citations=n) for k, n in top]

    missed.sort(key=lambda qa: qa[0].created_at, reverse=True)
    negative = [(q, a) for q, a in pairs if a is not None and any(f.rating < 0 for f in a.feedback)]
    negative.sort(key=lambda qa: qa[0].created_at, reverse=True)
    return sc.MetricsOut(
        scope="all" if p.is_admin else "mine",
        period_days=days,
        questions=len(pairs),
        answered=answered,
        unanswered=len(missed),
        answer_rate=round(answered / len(pairs), 4) if pairs else None,
        avg_latency_ms=round(sum(latencies) / len(latencies)) if latencies else None,
        p95_latency_ms=latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
        feedback=sc.FeedbackCount(up=sum(1 for v in votes if v > 0), down=sum(1 for v in votes if v < 0)),
        conversations=len({q.conversation_id for q, _ in pairs}),
        daily=daily,
        top_documents=top_documents,
        unanswered_recent=[sc.UnansweredItem(question=q.content, asked_at=q.created_at,
                                             conversation_id=q.conversation_id) for q, _ in missed[:10]],
        negative_recent=[sc.NegativeItem(question=q.content, answer=a.content, asked_at=q.created_at,
                                         conversation_id=q.conversation_id, message_id=a.id)
                         for q, a in negative[:10]],
    )


def _key_out(row: db.ApiKeyRow) -> sc.ApiKeyOut:
    return sc.ApiKeyOut.model_validate(row, from_attributes=True)


@router.get("/keys", response_model=list[sc.ApiKeyOut])
def list_keys(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    rows = database.scalars(select(db.ApiKeyRow).where(db.ApiKeyRow.owner == p.username)
                            .order_by(db.ApiKeyRow.created_at.desc())).all()
    return [_key_out(r) for r in rows]


@router.post("/keys", response_model=sc.ApiKeyCreated, status_code=201)
def create_key(body: sc.ApiKeyIn, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    name = " ".join(body.name.split())
    if not name:
        raise ApiError(400, "EMPTY", "Dê um nome à chave.", {"name": "Dê um nome à chave."})
    key = new_api_key()
    row = db.ApiKeyRow(owner=p.username, name=name, prefix=key[:12], key_hash=hash_api_key(key))
    database.add(row)
    database.commit()
    return sc.ApiKeyCreated(**_key_out(row).model_dump(), key=key)


@router.delete("/keys/{key_id}", status_code=204)
def delete_key(key_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = database.get(db.ApiKeyRow, key_id)
    if row is None or row.owner != p.username:
        raise ApiError(404, "NOT_FOUND", "Chave não encontrada.")
    database.delete(row)
    database.commit()
    return Response(status_code=204)


WEBHOOKS_ADMIN = "Só administradores podem gerenciar webhooks."


def _webhook_out(row: db.WebhookRow) -> sc.WebhookOut:
    return sc.WebhookOut(id=row.id, url=row.url, events=row.event_list, active=row.active, created_at=row.created_at,
                         last_status=row.last_status, last_error=row.last_error,
                         last_delivery_at=row.last_delivery_at)


def _webhook(database: Session, webhook_id: str, p: Principal) -> db.WebhookRow:
    _require_admin(p, WEBHOOKS_ADMIN)
    row = database.get(db.WebhookRow, webhook_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Webhook não encontrado.")
    return row


def _valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False


@router.get("/webhooks", response_model=list[sc.WebhookOut])
def list_webhooks(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _require_admin(p, WEBHOOKS_ADMIN)
    rows = database.scalars(select(db.WebhookRow).order_by(db.WebhookRow.created_at.desc())).all()
    return [_webhook_out(r) for r in rows]


@router.post("/webhooks", response_model=sc.WebhookCreated, status_code=201)
def create_webhook(body: sc.WebhookIn, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _require_admin(p, WEBHOOKS_ADMIN)
    url = body.url.strip()
    if not _valid_url(url):
        message = "Informe uma URL que comece com http:// ou https://."
        raise ApiError(400, "INVALID_URL", message, {"url": message})
    chosen = set(body.events)
    if not chosen or not chosen <= set(webhooks.EVENTS):
        message = "Escolha ao menos um evento válido."
        raise ApiError(400, "INVALID_EVENTS", message, {"events": message})
    secret = (body.secret or "").strip() or secrets.token_urlsafe(24)
    row = db.WebhookRow(url=url, events=",".join(e for e in webhooks.EVENTS if e in chosen), secret=secret,
                        active=True, created_by=p.username)
    database.add(row)
    database.commit()
    return sc.WebhookCreated(**_webhook_out(row).model_dump(), secret=secret)


@router.patch("/webhooks/{webhook_id}", response_model=sc.WebhookOut)
def update_webhook(webhook_id: str, body: sc.WebhookPatch, p: Principal = Depends(current_user),
                   database: Session = Depends(db.get_db)):
    row = _webhook(database, webhook_id, p)
    row.active = body.active
    database.commit()
    return _webhook_out(row)


@router.delete("/webhooks/{webhook_id}", status_code=204)
def delete_webhook(webhook_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    database.delete(_webhook(database, webhook_id, p))
    database.commit()
    return Response(status_code=204)


@router.post("/webhooks/{webhook_id}/test", response_model=sc.WebhookTestOut)
def test_webhook(webhook_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _webhook(database, webhook_id, p)
    database.commit()
    status, error = webhooks.deliver(row.id, "ping", {"webhook_id": row.id, "message": "Teste de entrega do Nexo."})
    return sc.WebhookTestOut(status=status, error=error)


USERS_ADMIN = "Só administradores podem gerenciar contas."


@router.get("/users", response_model=list[sc.UserOut])
def list_users(p: Principal = Depends(current_user), users: UserStore = Depends(get_users)):
    _require_admin(p, USERS_ADMIN)
    return [sc.UserOut(**u.public()) for u in users.all()]


@router.patch("/users/{username}", response_model=sc.UserOut)
def set_role(username: str, body: sc.RolePatch, p: Principal = Depends(current_user),
             users: UserStore = Depends(get_users)):
    _require_admin(p, USERS_ADMIN)
    key = username.strip().lower()
    if key == p.username and body.role != "admin":
        if users.admins() <= 1:
            message = "É preciso manter ao menos um administrador."
            raise ApiError(400, "LAST_ADMIN", message, {"role": message})
        message = "Você não pode rebaixar a própria conta."
        raise ApiError(400, "SELF", message, {"role": message})
    try:
        return sc.UserOut(**users.set_role(key, body.role).public())
    except UserError as e:
        raise _user_error(e)


@router.delete("/users/{username}", status_code=204)
def delete_user(username: str, p: Principal = Depends(current_user), users: UserStore = Depends(get_users),
                database: Session = Depends(db.get_db)):
    _require_admin(p, USERS_ADMIN)
    key = username.strip().lower()
    if key == p.username:
        raise ApiError(400, "SELF", "Você não pode excluir a própria conta.")
    try:
        users.delete(key)
    except UserError as e:
        raise _user_error(e)
    database.execute(delete(db.ApiKeyRow).where(db.ApiKeyRow.owner == key))
    for c in database.scalars(select(db.ConversationRow).where(db.ConversationRow.owner == key)).all():
        database.delete(c)
    database.commit()
    return Response(status_code=204)
