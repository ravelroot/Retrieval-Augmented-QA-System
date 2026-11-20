from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexo import db, webhooks
from nexo.api.deps import ApiError, Principal, current_user, question_quota
from nexo.api.routes import _require_ready, bot_profile, bot_scope, source_kinds
from nexo.config import Settings, get_settings
from nexo.rag.engine import NOT_FOUND, Answer, BotProfile, get_engine
from nexo.rag.providers import ProviderError, cited
from nexo.whatsapp import sources_footer

log = logging.getLogger("nexo.openai")
router = APIRouter(prefix="/v1", tags=["Compatível com OpenAI"])
GENERAL = "nexo"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: str = Field(max_length=20)
    content: str | list[dict[str, Any]] | None = None


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = Field(min_length=1, max_length=120)
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    stream: bool = False


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "agente"


def model_ids(bots: list[db.BotRow]) -> dict[str, db.BotRow]:
    taken: dict[str, db.BotRow] = {}
    for bot in sorted(bots, key=lambda b: b.created_at):
        name = slug(bot.name)
        if name in taken or name == GENERAL:
            name = f"{name}-{bot.id[:6]}"
        taken[name] = bot
    return taken


def resolve(database: Session, model: str) -> tuple[str, db.BotRow | None]:
    wanted = model.strip()
    if wanted.lower() == GENERAL:
        return GENERAL, None
    bots = list(database.scalars(select(db.BotRow)).all())
    ids = model_ids(bots)
    for name, bot in ids.items():
        if wanted in (name, bot.id) or wanted.lower() == bot.name.lower() or slug(wanted) == name:
            return name, bot
    raise ApiError(404, "model_not_found", f"O modelo '{wanted[:60]}' não existe. Use GET /v1/models para ver os agentes.")


def _text(content: str | list[dict[str, Any]] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = [str(p.get("text", "")) for p in content if isinstance(p, dict) and p.get("type") in (None, "text", "input_text")]
    return "\n".join(x for x in parts if x)


def conversation(messages: list[ChatMessage]) -> tuple[str, list[tuple[str, str]]]:
    turns = [(m.role, _text(m.content).strip()) for m in messages if m.role in ("user", "assistant")]
    turns = [(r, t) for r, t in turns if t]
    if not turns or turns[-1][0] != "user":
        raise ApiError(400, "invalid_request_error", "A última mensagem precisa ser do usuário (role: user).")
    question = turns[-1][1]
    if len(question) > 4000:
        raise ApiError(400, "invalid_request_error", "A pergunta passa de 4.000 caracteres.")
    return question, [(r, t[:4000]) for r, t in turns[:-1]][-20:]


def _plan(database: Session, bot: db.BotRow | None, question: str) -> tuple[list[str] | None, BotProfile | None, bool]:
    if bot is None:
        _require_ready(database, "perguntar")
        return None, None, True
    return bot_scope(database, bot, question), bot_profile(bot), bot.cite_sources


def _footer(database: Session, result: Answer, cite: bool) -> str:
    if not (cite and result.answered and result.sources):
        return ""
    kinds = source_kinds(database, result.sources)
    return sources_footer([{"rank": s.rank, "document_title": s.document_title, "page": s.page,
                            "kind": kinds.get(s.document_id, "pdf")} for s in cited(result.text, result.sources)])


def _sources(result: Answer) -> list[dict]:
    return [{"rank": s.rank, "document_id": s.document_id or None, "document_title": s.document_title, "page": s.page,
             "similarity": s.similarity, "rerank_score": s.rerank_score} for s in result.sources]


def _usage(prompt: str, answer: str) -> dict:
    prompt_tokens, completion_tokens = max(1, len(prompt) // 4), max(1, len(answer) // 4)
    return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens}


def _notify(result: Answer, question: str, p: Principal, model: str) -> None:
    if not result.answered:
        webhooks.emit("question.unanswered", {"question": question, "conversation_id": None, "username": p.username,
                                              "source": "openai", "model": model})


@router.get("/models")
def list_models(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)) -> dict:
    created = int(time.time())
    data = [{"id": GENERAL, "object": "model", "created": created, "owned_by": "nexo",
             "name": "Acervo inteiro", "description": "Responde com todos os documentos prontos."}]
    for name, bot in model_ids(list(database.scalars(select(db.BotRow)).all())).items():
        data.append({"id": name, "object": "model", "created": int(bot.created_at.timestamp()), "owned_by": "nexo",
                     "name": bot.name, "description": bot.description or f"Agente com a base {bot.base.name if bot.base else ''}"})
    return {"object": "list", "data": data}


@router.post("/chat/completions")
def chat_completions(body: ChatIn, p: Principal = Depends(question_quota), settings: Settings = Depends(get_settings),
                     database: Session = Depends(db.get_db)):
    model, bot = resolve(database, body.model)
    question, history = conversation(body.messages)
    scope, profile, cite = _plan(database, bot, question)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    if body.stream:
        return StreamingResponse(_stream(settings, completion_id, created, model, question, history, scope, profile, cite, p),
                                 media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
    try:
        result = get_engine(settings).ask(question, history, scope, profile)
    except ProviderError as e:
        raise ApiError(503, "provider_unavailable", str(e))
    except Exception as e:
        log.exception("Falha ao responder pela rota compatível com OpenAI")
        raise ApiError(502, "upstream_error", f"O modelo não respondeu: {e}")
    content = result.text + _footer(database, result, cite)
    _notify(result, question, p, model)
    return {"id": completion_id, "object": "chat.completion", "created": created, "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": _usage(question, content),
            "nexo": {"answered": result.answered, "latency_ms": result.latency_ms, "sources": _sources(result)}}


def _chunk(completion_id: str, created: int, model: str, delta: dict, finish: str | None = None, extra: dict | None = None) -> str:
    payload = {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model,
               "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if extra:
        payload.update(extra)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream(settings: Settings, completion_id: str, created: int, model: str, question: str, history: list[tuple[str, str]],
            scope: list[str] | None, profile: BotProfile | None, cite: bool, p: Principal):
    yield _chunk(completion_id, created, model, {"role": "assistant", "content": ""})
    marker = NOT_FOUND.lower()[:30]
    held = ""
    released = False
    result: Answer | None = None
    try:
        for item in get_engine(settings).ask_stream(question, history, scope, profile):
            if isinstance(item, Answer):
                result = item
                continue
            if released:
                yield _chunk(completion_id, created, model, {"content": item})
                continue
            held += item
            if len(held) >= len(marker) or not marker.startswith(held.lower().strip()[:len(marker)]):
                if marker in held.lower():
                    continue
                released = True
                yield _chunk(completion_id, created, model, {"content": held})
    except ProviderError as e:
        yield _chunk(completion_id, created, model, {"content": f"\n\n[Nexo] {e}"}, "stop")
        yield "data: [DONE]\n\n"
        return
    except Exception as e:
        log.exception("Falha ao responder em streaming pela rota compatível com OpenAI")
        yield _chunk(completion_id, created, model, {"content": f"\n\n[Nexo] O modelo não respondeu: {e}"}, "stop")
        yield "data: [DONE]\n\n"
        return
    if result is None:
        yield _chunk(completion_id, created, model, {}, "stop")
        yield "data: [DONE]\n\n"
        return
    if not released:
        yield _chunk(completion_id, created, model, {"content": result.text})
    with db.session() as s:
        footer = _footer(s, result, cite)
    if footer:
        yield _chunk(completion_id, created, model, {"content": footer})
    yield _chunk(completion_id, created, model, {}, "stop",
                 {"nexo": {"answered": result.answered, "latency_ms": result.latency_ms, "sources": _sources(result)}})
    yield "data: [DONE]\n\n"
    _notify(result, question, p, model)
