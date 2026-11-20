from __future__ import annotations

import json
import logging
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexo import audit, db, webhooks
from nexo.api import schemas as sc
from nexo.api.deps import ApiError, Principal, current_user, limiter_for
from nexo.api.routes import bot_profile, bot_scope, source_kinds
from nexo.config import Settings, get_settings
from nexo.rag import providers
from nexo.rag.engine import get_engine
from nexo.rag.providers import ProviderError

log = logging.getLogger("nexo.widget")
router = APIRouter()
STATIC = Path(__file__).resolve().parents[1] / "static" / "widget.js"
KEY_PREFIX = "nxw_"
HOST_RE = re.compile(r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*(:\d{1,5})?$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_BODY = 32 * 1024
ADMIN = "Só administradores publicam widgets."
BUSY = "O assistente está indisponível agora. Tente de novo em instantes."


def _admin(p: Principal) -> None:
    if not p.is_admin:
        raise ApiError(403, "FORBIDDEN", ADMIN)


def normalize_origin(raw: str) -> str:
    value = raw.strip().lower()
    if not value:
        raise ValueError("vazio")
    scheme = ""
    if "://" in value:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https"):
            raise ValueError(value)
        scheme, value = parts.scheme, parts.netloc
    else:
        value = value.split("/", 1)[0]
    if not HOST_RE.match(value):
        raise ValueError(raw)
    return f"{scheme}://{value}" if scheme else value


def _clean_origins(values: list[str]) -> str | None:
    out: list[str] = []
    bad: list[str] = []
    for raw in values:
        if not raw.strip():
            continue
        try:
            item = normalize_origin(raw)
        except ValueError:
            bad.append(raw.strip())
            continue
        if item not in out:
            out.append(item)
    if bad:
        message = f"Endereço inválido: {bad[0]}. Use só o domínio, como www.suaempresa.com.br ou *.suaempresa.com.br."
        raise ApiError(400, "INVALID_ORIGIN", message, {"origins": message})
    return "\n".join(out) or None


def origin_allowed(entries: list[str], origin: str) -> bool:
    try:
        parts = urlsplit(origin.lower())
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    host = parts.netloc
    for entry in entries:
        scheme, _, target = entry.rpartition("://")
        if scheme and scheme != parts.scheme:
            continue
        if target.startswith("*."):
            suffix = target[1:]
            if host.endswith(suffix) and len(host) > len(suffix):
                return True
        elif host == target:
            return True
    return False


def _base_url(request: Request, settings: Settings) -> str:
    return (settings.public_url or str(request.base_url)).rstrip("/")


def _snippet(base: str, key: str) -> str:
    return f'<script src="{base}/widget.js" data-nexo="{key}" async></script>'


def _out(row: db.WidgetRow, base: str, p: Principal) -> sc.WidgetOut:
    return sc.WidgetOut(id=row.id, name=row.name, bot_id=row.bot_id, bot_name=row.bot.name if row.bot else None,
                        public_key=row.public_key, origins=row.origin_list, title=row.title, welcome=row.welcome,
                        color=row.color, position=row.position, show_sources=row.show_sources, active=row.active,
                        questions=row.questions, unanswered=row.unanswered, last_used_at=row.last_used_at,
                        created_by=row.created_by, created_at=row.created_at, snippet=_snippet(base, row.public_key),
                        can_edit=p.is_admin)


def _widget(database: Session, widget_id: str) -> db.WidgetRow:
    row = database.get(db.WidgetRow, widget_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Widget não encontrado.")
    return row


def _bot(database: Session, bot_id: str) -> db.BotRow:
    bot = database.get(db.BotRow, bot_id)
    if bot is None:
        raise ApiError(400, "INVALID_BOT", "Escolha um agente que exista.", {"bot_id": "Escolha um agente que exista."})
    return bot


def _color(value: str | None) -> str:
    if value and not COLOR_RE.match(value):
        raise ApiError(400, "INVALID_COLOR", "Use uma cor no formato #RRGGBB.", {"color": "Use uma cor no formato #RRGGBB."})
    return value or "#000000"


def _text(value: str | None) -> str | None:
    value = " ".join((value or "").split()) if value is not None else None
    return value or None


@router.get("/api/widgets", response_model=list[sc.WidgetOut], tags=["Widget para sites"])
def list_widgets(request: Request, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                 database: Session = Depends(db.get_db)):
    base = _base_url(request, settings)
    rows = database.scalars(select(db.WidgetRow).order_by(db.WidgetRow.created_at)).all()
    return [_out(r, base, p) for r in rows]


@router.post("/api/widgets", response_model=sc.WidgetOut, status_code=201, tags=["Widget para sites"])
def create_widget(body: sc.WidgetIn, request: Request, p: Principal = Depends(current_user),
                  settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    _admin(p)
    bot = _bot(database, body.bot_id)
    name = _text(body.name)
    if not name:
        raise ApiError(400, "INVALID_NAME", "Dê um nome ao widget.", {"name": "Dê um nome ao widget."})
    row = db.WidgetRow(name=name, bot_id=bot.id, public_key=KEY_PREFIX + secrets.token_urlsafe(18),
                       origins=_clean_origins(body.origins), title=_text(body.title), welcome=(body.welcome or "").strip() or None,
                       color=_color(body.color or bot.color), position=body.position, show_sources=body.show_sources,
                       active=body.active, created_by=p.username)
    database.add(row)
    database.commit()
    database.refresh(row)
    audit.record("widget.create", "widget", row.id, {"name": row.name, "bot": bot.name, "origins": row.origin_list},
                 actor=p.username)
    return _out(row, _base_url(request, settings), p)


@router.patch("/api/widgets/{widget_id}", response_model=sc.WidgetOut, tags=["Widget para sites"])
def update_widget(widget_id: str, body: sc.WidgetPatch, request: Request, p: Principal = Depends(current_user),
                  settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    _admin(p)
    row = _widget(database, widget_id)
    data = body.model_dump(exclude_unset=True)
    if "bot_id" in data and data["bot_id"]:
        row.bot_id = _bot(database, data["bot_id"]).id
    if data.get("name") is not None:
        name = _text(data["name"])
        if not name:
            raise ApiError(400, "INVALID_NAME", "Dê um nome ao widget.", {"name": "Dê um nome ao widget."})
        row.name = name
    if "origins" in data and data["origins"] is not None:
        row.origins = _clean_origins(data["origins"])
    if "title" in data:
        row.title = _text(data["title"])
    if "welcome" in data:
        row.welcome = (data["welcome"] or "").strip() or None
    if data.get("color") is not None:
        row.color = _color(data["color"])
    for key in ("position", "show_sources", "active"):
        if data.get(key) is not None:
            setattr(row, key, data[key])
    row.updated_at = db.utcnow()
    database.commit()
    database.refresh(row)
    audit.record("widget.update", "widget", row.id, sorted(data), actor=p.username)
    return _out(row, _base_url(request, settings), p)


@router.post("/api/widgets/{widget_id}/rotate", response_model=sc.WidgetOut, tags=["Widget para sites"])
def rotate_widget(widget_id: str, request: Request, p: Principal = Depends(current_user),
                  settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    _admin(p)
    row = _widget(database, widget_id)
    row.public_key = KEY_PREFIX + secrets.token_urlsafe(18)
    row.updated_at = db.utcnow()
    database.commit()
    database.refresh(row)
    audit.record("widget.rotate", "widget", row.id, {"name": row.name}, actor=p.username)
    return _out(row, _base_url(request, settings), p)


@router.delete("/api/widgets/{widget_id}", status_code=204, tags=["Widget para sites"])
def delete_widget(widget_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _admin(p)
    row = _widget(database, widget_id)
    name = row.name
    database.delete(row)
    database.commit()
    audit.record("widget.delete", "widget", widget_id, {"name": name}, actor=p.username)
    return Response(status_code=204)


@router.get("/widget.js", include_in_schema=False)
def widget_script() -> Response:
    return Response(STATIC.read_text(encoding="utf-8"), media_type="application/javascript; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=600", "X-Content-Type-Options": "nosniff"})


def _cors(origin: str | None) -> dict[str, str]:
    if not origin:
        return {"Vary": "Origin"}
    return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "600", "Vary": "Origin"}


def _same_origin(request: Request, settings: Settings, origin: str) -> bool:
    own = {f"{request.url.scheme}://{request.headers.get('host', '')}".lower()}
    if settings.public_url:
        parts = urlsplit(settings.public_url)
        own.add(f"{parts.scheme}://{parts.netloc}".lower())
    return origin.lower().rstrip("/") in own


def _public(database: Session, key: str, request: Request, settings: Settings) -> tuple[db.WidgetRow, dict[str, str]]:
    origin = request.headers.get("origin")
    row = database.scalar(select(db.WidgetRow).where(db.WidgetRow.public_key == key)) if key.startswith(KEY_PREFIX) else None
    if row is None or not row.active:
        raise ApiError(404, "WIDGET_OFF", "Este assistente não está disponível.", headers=_cors(origin))
    entries = row.origin_list
    if entries:
        if not origin or not (origin_allowed(entries, origin) or _same_origin(request, settings, origin)):
            raise ApiError(403, "ORIGIN_NOT_ALLOWED", "Este site não está autorizado a usar este assistente.",
                           headers=_cors(origin))
    return row, _cors(origin)


@router.options("/api/public/widget/{key}/{action}", include_in_schema=False)
def widget_preflight(key: str, action: str, request: Request, settings: Settings = Depends(get_settings),
                     database: Session = Depends(db.get_db)) -> Response:
    _, headers = _public(database, key, request, settings)
    return Response(status_code=204, headers=headers)


@router.get("/api/public/widget/{key}/config", response_model=sc.WidgetConfigOut, tags=["Widget para sites"])
def widget_config(key: str, request: Request, response: Response, settings: Settings = Depends(get_settings),
                  database: Session = Depends(db.get_db)):
    row, headers = _public(database, key, request, settings)
    response.headers.update(headers)
    bot = row.bot
    suggestions = [line for line in (bot.suggestions or "").split("\n") if line.strip()][:4] if bot else []
    name = bot.name if bot else "Assistente"
    return sc.WidgetConfigOut(title=row.title or name, welcome=row.welcome or (bot.greeting if bot else None), color=row.color,
                              position=row.position, show_sources=row.show_sources, suggestions=suggestions, bot=name)


def _client(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "desconhecido")


@router.post("/api/public/widget/{key}/ask", response_model=sc.WidgetAnswerOut, tags=["Widget para sites"])
async def widget_ask(key: str, request: Request, response: Response, settings: Settings = Depends(get_settings)):
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY:
        raise ApiError(413, "TOO_LARGE", "Pergunta grande demais.", headers=_cors(request.headers.get("origin")))
    raw = b""
    async for part in request.stream():
        raw += part
        if len(raw) > MAX_BODY:
            raise ApiError(413, "TOO_LARGE", "Pergunta grande demais.", headers=_cors(request.headers.get("origin")))
    out, headers = await run_in_threadpool(_answer, key, raw, request, settings)
    response.headers.update(headers)
    return out


def _answer(key: str, raw: bytes, request: Request, settings: Settings) -> tuple[sc.WidgetAnswerOut, dict[str, str]]:
    with db.session() as database:
        row, headers = _public(database, key, request, settings)
        if len(raw) > MAX_BODY:
            raise ApiError(413, "TOO_LARGE", "Pergunta grande demais.", headers=headers)
        try:
            body = sc.WidgetAskIn.model_validate(json.loads(raw or b"{}"))
        except (ValueError, ValidationError):
            raise ApiError(422, "VALIDATION", "Escreva uma pergunta de até 2.000 caracteres.", headers=headers)
        question = body.question.strip()
        if not question:
            raise ApiError(422, "VALIDATION", "Escreva uma pergunta.", headers=headers)
        limiter = limiter_for(request)
        wait = limiter.hit(f"widget:{row.id}:{_client(request)}", settings.widget_rate_limit)
        if wait is None:
            wait = limiter.hit(f"widget:{row.id}", max(60, settings.widget_rate_limit * 20))
        if wait is not None:
            raise ApiError(429, "RATE_LIMITED", f"Muitas perguntas em pouco tempo. Tente de novo em {wait} s.",
                           headers={**headers, "Retry-After": str(wait)})
        bot = row.bot
        if bot is None:
            raise ApiError(404, "WIDGET_OFF", "Este assistente não está disponível.", headers=headers)
        keep = settings.history_turns * 2
        history = [(t.role, t.content.strip()[:1500]) for t in body.history if t.content.strip()][-keep:] if keep else []
        try:
            scope = bot_scope(database, bot, question)
            result = get_engine(settings).ask(question, history, scope, bot_profile(bot))
        except ApiError as e:
            if e.code == "NO_DOCUMENTS":
                raise ApiError(503, "NOT_READY", "Este assistente ainda está sendo preparado. Volte em instantes.", headers=headers)
            raise ApiError(e.status, e.code, BUSY, headers=headers)
        except ProviderError:
            log.warning("Widget %s sem modelo disponível", row.id)
            raise ApiError(503, "PROVIDER", BUSY, headers=headers)
        except Exception:
            log.exception("Falha ao responder pelo widget %s", row.id)
            raise ApiError(502, "LLM_FAILURE", BUSY, headers=headers)
        row.questions += 1
        row.unanswered += 0 if result.answered else 1
        row.last_used_at = db.utcnow()
        database.commit()
        widget_id, bot_id = row.id, bot.id
        kinds = source_kinds(database, result.sources)
        sources = []
        if row.show_sources and result.answered:
            seen: set[tuple[str, int]] = set()
            for s in providers.cited(result.text, result.sources):
                page = s.page if kinds.get(s.document_id, "pdf") == "pdf" else 0
                if (s.document_title, page) in seen:
                    continue
                seen.add((s.document_title, page))
                sources.append(sc.WidgetSource(rank=s.rank, title=s.document_title, page=page))
    if not result.answered:
        webhooks.emit("question.unanswered", {"question": question, "conversation_id": None, "username": None,
                                              "source": "widget", "widget_id": widget_id, "bot_id": bot_id})
    return sc.WidgetAnswerOut(answer=result.text, answered=result.answered, sources=sources), headers
