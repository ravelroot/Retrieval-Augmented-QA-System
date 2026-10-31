from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from nexo import __version__, db, webhooks
from nexo.config import get_settings

log = logging.getLogger("nexo.whatsapp")

PROVIDERS = ("cloud", "evolution", "simulador")
DEFAULT_API_VERSION = "v24.0"
GRAPH_URL = "https://graph.facebook.com"
MAX_TEXT = 4000
HANDOFF_RE = re.compile(r"\b(atendente|humano|humana|falar com (uma )?pessoa|falar com algu[eé]m)\b", re.I)
HANDOFF_TEXT = "Certo! Vou chamar uma pessoa da equipe para continuar o seu atendimento. Aguarde só um pouco."
PAUSED_TEXT = "Recebemos sua mensagem. Uma pessoa da equipe vai responder em breve."

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nexo-whatsapp")
_pending: set[Future] = set()
_lock = threading.Lock()


@dataclass
class Inbound:
    phone: str
    name: str | None
    text: str
    external_id: str | None
    from_me: bool = False


@dataclass
class StatusUpdate:
    external_id: str
    status: str
    error: str | None = None


def mask(value: str | None) -> str | None:
    if not value:
        return None
    return "••••" + value[-4:] if len(value) > 6 else "••••"


def clean_phone(value: str) -> str:
    return re.sub(r"\D", "", value or "")[:32]


def _http(method: str, url: str, headers: dict, body: dict | None = None) -> tuple[int | None, dict | None, str | None]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Accept": "application/json", "User-Agent": f"Nexo/{__version__}", **headers})
    try:
        with urllib.request.urlopen(request, timeout=get_settings().whatsapp_timeout) as response:
            raw = response.read()
            try:
                return response.status, json.loads(raw or b"{}"), None
            except json.JSONDecodeError:
                return response.status, None, None
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            payload = json.loads(e.read() or b"{}")
            detail = (payload.get("error") or {}).get("message") if isinstance(payload.get("error"), dict) \
                else payload.get("message") or payload.get("error") or ""
            if isinstance(detail, list):
                detail = "; ".join(str(x) for x in detail)
        except Exception:
            detail = ""
        return e.code, None, f"HTTP {e.code}" + (f": {detail}" if detail else "")
    except urllib.error.URLError as e:
        return None, None, f"Não foi possível conectar: {e.reason}"
    except TimeoutError:
        return None, None, "Tempo esgotado."
    except Exception as e:
        return None, None, f"Falha: {e}"


def _evolution_url(channel: db.WhatsAppChannelRow, path: str) -> str:
    return f"{(channel.base_url or '').rstrip('/')}/{path}/{urllib.parse.quote(channel.instance or '', safe='')}"


def _cloud_url(channel: db.WhatsAppChannelRow, suffix: str = "") -> str:
    return f"{GRAPH_URL}/{channel.api_version or DEFAULT_API_VERSION}/{channel.phone_number_id}{suffix}"


def missing_settings(channel: db.WhatsAppChannelRow) -> str | None:
    if channel.provider == "cloud" and not (channel.phone_number_id and channel.access_token):
        return "Informe o Phone Number ID e o token de acesso da API oficial."
    if channel.provider == "evolution" and not (channel.base_url and channel.api_key and channel.instance):
        return "Informe o endereço da Evolution API, a chave e o nome da instância."
    return None


def send_text(channel: db.WhatsAppChannelRow, to: str, text: str) -> tuple[str | None, str | None]:
    text = text[:MAX_TEXT]
    if channel.provider == "simulador":
        return f"sim-{db.new_id()[:16]}", None
    problem = missing_settings(channel)
    if problem:
        return None, problem
    if channel.provider == "cloud":
        status, data, error = _http("POST", _cloud_url(channel, "/messages"),
                                    {"Authorization": f"Bearer {channel.access_token}"},
                                    {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                                     "type": "text", "text": {"preview_url": False, "body": text}})
        if error:
            return None, error
        messages = (data or {}).get("messages") or [{}]
        return messages[0].get("id"), None
    status, data, error = _http("POST", _evolution_url(channel, "message/sendText"), {"apikey": channel.api_key or ""},
                                {"number": to, "text": text})
    if error:
        return None, error
    return ((data or {}).get("key") or {}).get("id"), None


def connection_state(channel: db.WhatsAppChannelRow) -> tuple[str, str | None]:
    if channel.provider == "simulador":
        return "open", "Simulador ativo: as mensagens não saem do Nexo."
    problem = missing_settings(channel)
    if problem:
        return "close", problem
    if channel.provider == "cloud":
        status, data, error = _http("GET", _cloud_url(channel, "?fields=display_phone_number,verified_name"),
                                    {"Authorization": f"Bearer {channel.access_token}"})
        if error:
            return "close", error
        name = (data or {}).get("verified_name")
        number = (data or {}).get("display_phone_number")
        return "open", " · ".join(x for x in (number, name) if x) or None
    status, data, error = _http("GET", _evolution_url(channel, "instance/connectionState"),
                                {"apikey": channel.api_key or ""})
    if error:
        return "unknown", error
    state = ((data or {}).get("instance") or {}).get("state") or (data or {}).get("state") or "unknown"
    return (state if state in ("open", "connecting", "close") else "unknown"), None


def qr_code(channel: db.WhatsAppChannelRow) -> tuple[str, str | None, str | None, str | None]:
    if channel.provider != "evolution":
        state, detail = connection_state(channel)
        return state, None, None, detail or "QR code só existe na conexão pela Evolution API."
    state, detail = connection_state(channel)
    if state == "open":
        return state, None, None, None
    problem = missing_settings(channel)
    if problem:
        return "close", None, None, problem
    status, data, error = _http("GET", _evolution_url(channel, "instance/connect"), {"apikey": channel.api_key or ""})
    if error:
        return state, None, None, error
    data = data or {}
    image = data.get("base64")
    if image and not image.startswith("data:"):
        image = f"data:image/png;base64,{image}"
    return "connecting", image, data.get("pairingCode"), None


def register_webhook(channel: db.WhatsAppChannelRow, url: str) -> tuple[bool, str | None]:
    if channel.provider != "evolution":
        return True, None
    problem = missing_settings(channel)
    if problem:
        return False, problem
    status, data, error = _http("POST", _evolution_url(channel, "webhook/set"), {"apikey": channel.api_key or ""},
                                {"enabled": True, "url": url, "webhookByEvents": False, "webhookBase64": False,
                                 "events": ["MESSAGES_UPSERT"]})
    return (error is None), error


def check_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.strip())


def _cloud_text(message: dict) -> str:
    kind = message.get("type")
    if kind == "text":
        return (message.get("text") or {}).get("body", "")
    if kind == "button":
        return (message.get("button") or {}).get("text", "")
    if kind == "interactive":
        inter = message.get("interactive") or {}
        reply = inter.get("button_reply") or inter.get("list_reply") or {}
        return reply.get("title", "")
    caption = (message.get(kind) or {}).get("caption") if isinstance(message.get(kind), dict) else None
    return caption or f"[{kind or 'mensagem'} recebida]"


def parse_cloud(payload: dict) -> tuple[list[Inbound], list[StatusUpdate]]:
    messages: list[Inbound] = []
    statuses: list[StatusUpdate] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts") or []}
            for m in value.get("messages") or []:
                phone = clean_phone(m.get("from", ""))
                if phone:
                    messages.append(Inbound(phone, names.get(m.get("from")), _cloud_text(m).strip(), m.get("id")))
            for st in value.get("statuses") or []:
                errors = st.get("errors") or []
                detail = (errors[0].get("title") or errors[0].get("message")) if errors else None
                if st.get("id") and st.get("status"):
                    statuses.append(StatusUpdate(st["id"], st["status"], detail))
    return messages, statuses


def _evolution_text(message: dict) -> str:
    if not isinstance(message, dict):
        return ""
    if message.get("conversation"):
        return message["conversation"]
    ext = message.get("extendedTextMessage") or {}
    if ext.get("text"):
        return ext["text"]
    for key in ("imageMessage", "videoMessage", "documentMessage"):
        if isinstance(message.get(key), dict):
            return message[key].get("caption") or f"[{key.replace('Message', '')} recebido]"
    if message.get("audioMessage"):
        return "[áudio recebido]"
    return "[mensagem recebida]" if message else ""


def parse_evolution(payload: dict) -> tuple[list[Inbound], list[StatusUpdate]]:
    event = str(payload.get("event") or "").lower().replace("_", ".")
    if event != "messages.upsert":
        return [], []
    items = payload.get("data")
    items = items if isinstance(items, list) else [items] if isinstance(items, dict) else []
    out: list[Inbound] = []
    for data in items:
        key = data.get("key") or {}
        jid = str(key.get("remoteJid") or "")
        if not jid or not jid.endswith("@s.whatsapp.net"):
            continue
        phone = clean_phone(jid.split("@")[0])
        text = _evolution_text(data.get("message") or {}).strip()
        if phone and text:
            out.append(Inbound(phone, None if key.get("fromMe") else data.get("pushName"), text, key.get("id"),
                               bool(key.get("fromMe"))))
    return out, []


def whatsapp_format(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
    return text.strip()


def sources_footer(sources: list[dict]) -> str:
    seen: list[str] = []
    for s in sources:
        unit = "p." if s.get("kind", "pdf") == "pdf" else "parte"
        line = f"[{s['rank']}] {s['document_title']}, {unit} {s['page']}"
        if line not in seen:
            seen.append(line)
    return "\n\nFontes:\n" + "\n".join(seen) if seen else ""


def _track(future: Future) -> None:
    with _lock:
        _pending.add(future)
    future.add_done_callback(lambda f: _discard(f))


def _discard(future: Future) -> None:
    with _lock:
        _pending.discard(future)


def wait_idle(timeout: float = 60.0) -> None:
    with _lock:
        futures = list(_pending)
    wait(futures, timeout=timeout)
    with _lock:
        futures = list(_pending)
    wait(futures, timeout=timeout)


def _contact(s, channel: db.WhatsAppChannelRow, phone: str, name: str | None) -> db.WhatsAppContactRow:
    row = s.scalar(select(db.WhatsAppContactRow).where(db.WhatsAppContactRow.channel_id == channel.id,
                                                       db.WhatsAppContactRow.phone == phone))
    if row is None:
        row = db.WhatsAppContactRow(channel_id=channel.id, phone=phone, name=name, bot_enabled=True,
                                    needs_human=False, unread=0)
        s.add(row)
        s.flush()
    elif name and not row.name:
        row.name = name
    return row


def receive(channel_id: str, items: list[Inbound], statuses: list[StatusUpdate] | None = None) -> list[str]:
    contacts: list[str] = []
    replies: list[tuple[str, str]] = []
    events: list[dict] = []
    with db.session() as s:
        channel = s.get(db.WhatsAppChannelRow, channel_id)
        if channel is None:
            return []
        channel.last_event_at = db.utcnow()
        for st in statuses or []:
            msg = s.scalar(select(db.WhatsAppMessageRow).where(db.WhatsAppMessageRow.external_id == st.external_id))
            if msg is not None and msg.direction == "out":
                msg.status = st.status if st.status in ("sent", "delivered", "read", "failed") else msg.status
                if st.error:
                    msg.error = st.error
        for item in items:
            if item.external_id and s.scalar(select(db.WhatsAppMessageRow.id)
                                             .where(db.WhatsAppMessageRow.external_id == item.external_id)):
                continue
            contact = _contact(s, channel, item.phone, item.name)
            now = db.utcnow()
            if item.from_me:
                s.add(db.WhatsAppMessageRow(contact_id=contact.id, direction="out", author="celular", body=item.text,
                                            status="sent", external_id=item.external_id, created_at=now))
                contact.last_message_at = now
                contacts.append(contact.id)
                continue
            msg = db.WhatsAppMessageRow(contact_id=contact.id, direction="in", author="cliente", body=item.text,
                                        status="received", external_id=item.external_id, created_at=now)
            s.add(msg)
            s.flush()
            contact.unread += 1
            contact.last_message_at = now
            contacts.append(contact.id)
            events.append({"channel_id": channel.id, "contact_id": contact.id, "phone": contact.phone,
                           "name": contact.name, "text": item.text})
            if channel.active and channel.auto_reply and channel.bot_id:
                if contact.bot_enabled and not contact.needs_human:
                    replies.append((contact.id, msg.id))
        s.commit()
    for data in events:
        webhooks.emit("whatsapp.message", data)
    for contact_id, message_id in replies:
        _track(_executor.submit(_safe_reply, contact_id, message_id))
    return contacts


def _safe_reply(contact_id: str, message_id: str) -> None:
    try:
        reply(contact_id, message_id)
    except Exception:
        log.exception("Falha ao responder no WhatsApp")


def history_for(s, contact_id: str, before: datetime | None, limit: int) -> list[tuple[str, str]]:
    if limit <= 0:
        return []
    query = select(db.WhatsAppMessageRow).where(db.WhatsAppMessageRow.contact_id == contact_id)
    if before is not None:
        query = query.where(db.WhatsAppMessageRow.created_at < before)
    rows = s.scalars(query.order_by(db.WhatsAppMessageRow.created_at.desc()).limit(limit)).all()
    return [("user" if r.direction == "in" else "assistant", r.body) for r in reversed(rows)]


def answer_for(s, bot: db.BotRow, question: str, history: list[tuple[str, str]]):
    from nexo.api.routes import base_scope, bot_profile, source_kinds
    from nexo.rag.engine import Answer, get_engine, is_salutation
    settings = get_settings()
    profile = bot_profile(bot)
    scope = base_scope(s, bot.base_id)
    if not scope and not (bot.greeting and is_salutation(question)):
        return Answer(profile.fallback or PAUSED_TEXT, False, [], None, "", 0, question), {}
    result = get_engine(settings).ask(question, history, scope or ["__vazio__"], profile)
    return result, source_kinds(s, result.sources)


def compose(bot: db.BotRow, result, kinds: dict[str, str]) -> tuple[str, list[dict]]:
    sources = [{"rank": x.rank, "document_id": x.document_id or None, "document_title": x.document_title,
                "page": x.page, "similarity": x.similarity, "rerank_score": x.rerank_score, "excerpt": x.excerpt,
                "kind": kinds.get(x.document_id, "pdf")} for x in result.sources]
    text = whatsapp_format(result.text)
    if bot.cite_sources and result.answered and sources:
        text += sources_footer(sources)
    return text[:MAX_TEXT], sources


def reply(contact_id: str, message_id: str) -> None:
    handoff = None
    with db.session() as s:
        contact = s.get(db.WhatsAppContactRow, contact_id)
        msg = s.get(db.WhatsAppMessageRow, message_id)
        if contact is None or msg is None:
            return
        channel = s.get(db.WhatsAppChannelRow, contact.channel_id)
        bot = s.get(db.BotRow, channel.bot_id) if channel and channel.bot_id else None
        if channel is None or bot is None or not contact.bot_enabled or contact.needs_human:
            return
        answered: bool | None = None
        sources: list[dict] = []
        if HANDOFF_RE.search(msg.body):
            text = HANDOFF_TEXT
            handoff = "pedido"
        else:
            history = history_for(s, contact.id, msg.created_at, get_settings().whatsapp_history)
            try:
                result, kinds = answer_for(s, bot, msg.body, history)
            except Exception as e:
                log.warning("Agente não respondeu no WhatsApp: %s", e)
                channel.last_error = f"O agente não respondeu: {e}"[:2000]
                contact.needs_human = True
                s.commit()
                webhooks.emit("whatsapp.handoff", {"channel_id": channel.id, "contact_id": contact.id,
                                                   "phone": contact.phone, "reason": "erro"})
                return
            text, sources = compose(bot, result, kinds)
            answered = result.answered
            if not result.answered:
                handoff = "sem_resposta"
        external_id, error = send_text(channel, contact.phone, text)
        s.add(db.WhatsAppMessageRow(contact_id=contact.id, direction="out", author="agente", body=text,
                                    status="failed" if error else "sent", external_id=external_id, error=error,
                                    answered=answered, sources_json=json.dumps(sources, ensure_ascii=False)
                                    if sources else None, created_at=db.utcnow()))
        contact.last_message_at = db.utcnow()
        if error:
            channel.last_error = error[:2000]
        if handoff:
            contact.needs_human = True
            contact.bot_enabled = False
        s.commit()
        data = {"channel_id": channel.id, "contact_id": contact.id, "phone": contact.phone, "name": contact.name,
                "question": msg.body, "reason": handoff}
    if handoff:
        webhooks.emit("whatsapp.handoff", data)
