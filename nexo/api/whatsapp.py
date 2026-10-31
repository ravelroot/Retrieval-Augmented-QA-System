from __future__ import annotations

import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexo import db, whatsapp
from nexo.api import schemas as sc
from nexo.api.deps import ApiError, Principal, current_user
from nexo.api.routes import _valid_url
from nexo.config import Settings, get_settings
from nexo.rag.providers import ProviderError

router = APIRouter(prefix="/api/whatsapp")
ADMIN = "Só administradores configuram as conexões do WhatsApp."
MAX_BODY = 2 * 1024 * 1024


def _admin(p: Principal) -> None:
    if not p.is_admin:
        raise ApiError(403, "FORBIDDEN", ADMIN)


def _path(row: db.WhatsAppChannelRow) -> str:
    path = f"/api/whatsapp/webhook/{row.id}"
    return path if row.provider == "cloud" else f"{path}?token={row.webhook_token}"


def _channel_out(database: Session, row: db.WhatsAppChannelRow) -> sc.ChannelOut:
    stats = database.execute(select(func.count(), func.coalesce(func.sum(db.WhatsAppContactRow.unread), 0))
                             .where(db.WhatsAppContactRow.channel_id == row.id)).one()
    waiting = database.scalar(select(func.count()).select_from(db.WhatsAppContactRow)
                              .where(db.WhatsAppContactRow.channel_id == row.id,
                                     db.WhatsAppContactRow.needs_human.is_(True))) or 0
    return sc.ChannelOut(
        id=row.id, name=row.name, provider=row.provider, bot_id=row.bot_id,
        bot_name=row.bot.name if row.bot is not None else None, auto_reply=row.auto_reply, active=row.active,
        phone=row.phone, webhook_path=_path(row), verify_token=row.verify_token,
        settings=sc.ChannelSettings(api_version=row.api_version, phone_number_id=row.phone_number_id,
                                    base_url=row.base_url, instance=row.instance),
        secrets=sc.ChannelSecrets(access_token=whatsapp.mask(row.access_token), app_secret=whatsapp.mask(row.app_secret),
                                  api_key=whatsapp.mask(row.api_key)),
        created_at=row.created_at, last_event_at=row.last_event_at, last_error=row.last_error,
        contacts=int(stats[0] or 0), unread=int(stats[1] or 0), waiting=int(waiting))


def _channel(database: Session, channel_id: str) -> db.WhatsAppChannelRow:
    row = database.get(db.WhatsAppChannelRow, channel_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Conexão do WhatsApp não encontrada.")
    return row


def _apply(row: db.WhatsAppChannelRow, data: dict, database: Session) -> None:
    if "name" in data and data["name"]:
        row.name = " ".join(data["name"].split())[:80]
    if data.get("provider"):
        row.provider = data["provider"]
    if "bot_id" in data:
        if data["bot_id"]:
            if database.get(db.BotRow, data["bot_id"]) is None:
                raise ApiError(404, "NOT_FOUND", "Agente não encontrado.", {"bot_id": "Agente não encontrado."})
            row.bot_id = data["bot_id"]
        else:
            row.bot_id = None
    for field in ("auto_reply", "active"):
        if data.get(field) is not None:
            setattr(row, field, bool(data[field]))
    if "phone" in data:
        row.phone = (data["phone"] or "").strip() or None
    for field in ("api_version", "phone_number_id", "instance"):
        if field in data:
            setattr(row, field, (data[field] or "").strip() or None)
    if "base_url" in data:
        url = (data["base_url"] or "").strip().rstrip("/") or None
        if url and not _valid_url(url):
            message = "Informe um endereço que comece com http:// ou https://."
            raise ApiError(400, "INVALID_URL", message, {"base_url": message})
        row.base_url = url
    for field in ("access_token", "app_secret", "api_key"):
        value = data.get(field)
        if value is not None and value.strip():
            setattr(row, field, value.strip())


@router.get("/channels", response_model=list[sc.ChannelOut])
def list_channels(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    rows = database.scalars(select(db.WhatsAppChannelRow).order_by(db.WhatsAppChannelRow.created_at)).all()
    return [_channel_out(database, r) for r in rows]


@router.post("/channels", response_model=sc.ChannelOut, status_code=201)
def create_channel(body: sc.ChannelIn, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _admin(p)
    row = db.WhatsAppChannelRow(name=body.name, provider=body.provider, auto_reply=True, active=True,
                                verify_token=secrets.token_urlsafe(18), webhook_token=secrets.token_urlsafe(24),
                                created_by=p.username)
    _apply(row, body.model_dump(), database)
    if row.provider == "cloud" and not row.api_version:
        row.api_version = whatsapp.DEFAULT_API_VERSION
    database.add(row)
    database.commit()
    database.refresh(row)
    return _channel_out(database, row)


@router.patch("/channels/{channel_id}", response_model=sc.ChannelOut)
def update_channel(channel_id: str, body: sc.ChannelPatch, p: Principal = Depends(current_user),
                   database: Session = Depends(db.get_db)):
    _admin(p)
    row = _channel(database, channel_id)
    _apply(row, body.model_dump(exclude_unset=True), database)
    if row.provider == "cloud" and not row.api_version:
        row.api_version = whatsapp.DEFAULT_API_VERSION
    database.commit()
    database.refresh(row)
    return _channel_out(database, row)


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(channel_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _admin(p)
    database.delete(_channel(database, channel_id))
    database.commit()
    return Response(status_code=204)


@router.get("/channels/{channel_id}/status", response_model=sc.ChannelStatusOut)
def channel_status(channel_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    state, detail = whatsapp.connection_state(_channel(database, channel_id))
    return sc.ChannelStatusOut(state=state, detail=detail)


@router.get("/channels/{channel_id}/qrcode", response_model=sc.QrOut)
def channel_qr(channel_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _admin(p)
    state, image, pairing, detail = whatsapp.qr_code(_channel(database, channel_id))
    if detail and not image and state not in ("open",):
        raise ApiError(502, "WHATSAPP", detail)
    return sc.QrOut(state=state, base64=image, pairing_code=pairing)


@router.post("/channels/{channel_id}/webhook", response_model=sc.WebhookSetupOut)
def channel_webhook(channel_id: str, body: sc.WebhookSetupIn, request: Request, p: Principal = Depends(current_user),
                    settings: Settings = Depends(get_settings), database: Session = Depends(db.get_db)):
    _admin(p)
    row = _channel(database, channel_id)
    base = (body.public_url or settings.public_url or str(request.base_url)).strip().rstrip("/")
    if not _valid_url(base):
        message = "Informe o endereço público do Nexo, começando com http:// ou https://."
        raise ApiError(400, "INVALID_URL", message, {"public_url": message})
    url = base + _path(row)
    ok, detail = whatsapp.register_webhook(row, url)
    if not ok:
        row.last_error = detail
        database.commit()
    return sc.WebhookSetupOut(ok=ok, url=url, detail=detail)


@router.post("/channels/{channel_id}/simulate", status_code=202)
def simulate(channel_id: str, body: sc.SimulateIn, p: Principal = Depends(current_user),
             database: Session = Depends(db.get_db)) -> dict:
    row = _channel(database, channel_id)
    if row.provider != "simulador":
        raise ApiError(400, "NOT_SIMULATOR", "Mensagens simuladas só existem em conexões do tipo simulador.")
    phone = whatsapp.clean_phone(body.phone)
    if len(phone) < 8:
        raise ApiError(400, "INVALID_PHONE", "Informe o telefone com DDD.", {"phone": "Informe o telefone com DDD."})
    found = whatsapp.receive(row.id, [whatsapp.Inbound(phone, (body.name or "").strip() or None, body.text.strip(),
                                                       f"simin-{db.new_id()[:16]}")])
    return {"contact_id": found[0] if found else None}


@router.get("/webhook/{channel_id}", include_in_schema=False)
def verify(channel_id: str, mode: str | None = Query(None, alias="hub.mode"),
           token: str | None = Query(None, alias="hub.verify_token"),
           challenge: str | None = Query(None, alias="hub.challenge")):
    with db.session() as s:
        row = s.get(db.WhatsAppChannelRow, channel_id)
        expected = row.verify_token if row is not None else None
    if expected and mode == "subscribe" and token and secrets.compare_digest(token, expected):
        return PlainTextResponse(challenge or "")
    return PlainTextResponse("Verificação recusada.", status_code=403)


@router.post("/webhook/{channel_id}", include_in_schema=False)
async def inbound(channel_id: str, request: Request, token: str | None = Query(None)):
    body = await request.body()
    if len(body) > MAX_BODY:
        return JSONResponse({"ok": False}, status_code=413)
    with db.session() as s:
        row = s.get(db.WhatsAppChannelRow, channel_id)
        if row is None:
            return JSONResponse({"ok": False}, status_code=404)
        provider, app_secret, hook_token, active = row.provider, row.app_secret, row.webhook_token, row.active
    if provider == "cloud":
        if app_secret and not whatsapp.check_signature(app_secret, body, request.headers.get("x-hub-signature-256")):
            return JSONResponse({"ok": False}, status_code=401)
    elif not token or not secrets.compare_digest(token, hook_token):
        return JSONResponse({"ok": False}, status_code=401)
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return JSONResponse({"ok": False}, status_code=400)
    if not isinstance(payload, dict) or not active:
        return {"ok": True}
    if provider == "cloud":
        items, statuses = whatsapp.parse_cloud(payload)
    else:
        items, statuses = whatsapp.parse_evolution(payload)
    whatsapp.receive(channel_id, items, statuses)
    return {"ok": True}


@router.get("/summary", response_model=sc.WaSummaryOut)
def summary(p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    today = datetime.combine(db.utcnow().date(), datetime.min.time())
    contacts, unread = database.execute(select(func.count(), func.coalesce(func.sum(db.WhatsAppContactRow.unread), 0))
                                        .select_from(db.WhatsAppContactRow)).one()
    waiting = database.scalar(select(func.count()).select_from(db.WhatsAppContactRow)
                              .where(db.WhatsAppContactRow.needs_human.is_(True))) or 0
    bot = database.scalar(select(func.count()).select_from(db.WhatsAppMessageRow)
                          .where(db.WhatsAppMessageRow.author == "agente",
                                 db.WhatsAppMessageRow.created_at >= today)) or 0
    channels = database.scalar(select(func.count()).select_from(db.WhatsAppChannelRow)) or 0
    return sc.WaSummaryOut(channels=int(channels), contacts=int(contacts or 0), unread=int(unread or 0),
                           waiting=int(waiting), bot_answers_today=int(bot))


def _last(database: Session, contact_id: str) -> db.WhatsAppMessageRow | None:
    return database.scalar(select(db.WhatsAppMessageRow).where(db.WhatsAppMessageRow.contact_id == contact_id)
                           .order_by(db.WhatsAppMessageRow.created_at.desc()).limit(1))


def _contact_out(database: Session, row: db.WhatsAppContactRow) -> sc.ContactOut:
    last = _last(database, row.id)
    return sc.ContactOut(id=row.id, channel_id=row.channel_id, phone=row.phone, name=row.name,
                         bot_enabled=row.bot_enabled, needs_human=row.needs_human, unread=row.unread,
                         last_message=last.body[:160] if last else None, last_direction=last.direction if last else None,
                         last_message_at=row.last_message_at, created_at=row.created_at)


def _message_out(m: db.WhatsAppMessageRow) -> sc.WaMessageOut:
    sources = [sc.SourceOut(**x) for x in json.loads(m.sources_json)] if m.sources_json else []
    return sc.WaMessageOut(id=m.id, direction=m.direction, author=m.author, body=m.body, status=m.status, error=m.error,
                           created_at=m.created_at, answered=m.answered, sources=sources)


def _get_contact(database: Session, contact_id: str) -> db.WhatsAppContactRow:
    row = database.get(db.WhatsAppContactRow, contact_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Contato não encontrado.")
    return row


@router.get("/contacts", response_model=list[sc.ContactOut])
def list_contacts(channel_id: str | None = Query(None), filter: str = Query("all"), q: str = Query(""),
                  p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    query = select(db.WhatsAppContactRow)
    if channel_id:
        query = query.where(db.WhatsAppContactRow.channel_id == channel_id)
    if filter == "unread":
        query = query.where(db.WhatsAppContactRow.unread > 0)
    elif filter == "waiting":
        query = query.where(db.WhatsAppContactRow.needs_human.is_(True))
    elif filter == "bot":
        query = query.where(db.WhatsAppContactRow.bot_enabled.is_(True))
    elif filter == "human":
        query = query.where(db.WhatsAppContactRow.bot_enabled.is_(False))
    term = q.strip()
    if term:
        like = f"%{term.lower()}%"
        query = query.where(func.lower(func.coalesce(db.WhatsAppContactRow.name, "")).like(like)
                            | db.WhatsAppContactRow.phone.like(f"%{whatsapp.clean_phone(term) or term}%"))
    rows = database.scalars(query.order_by(db.WhatsAppContactRow.last_message_at.desc()).limit(300)).all()
    return [_contact_out(database, r) for r in rows]


@router.get("/contacts/{contact_id}", response_model=sc.ContactDetailOut)
def get_contact(contact_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _get_contact(database, contact_id)
    if row.unread:
        row.unread = 0
        database.commit()
    messages = database.scalars(select(db.WhatsAppMessageRow).where(db.WhatsAppMessageRow.contact_id == row.id)
                                .order_by(db.WhatsAppMessageRow.created_at)).all()
    return sc.ContactDetailOut(**_contact_out(database, row).model_dump(), messages=[_message_out(m) for m in messages])


@router.patch("/contacts/{contact_id}", response_model=sc.ContactOut)
def update_contact(contact_id: str, body: sc.ContactPatch, p: Principal = Depends(current_user),
                   database: Session = Depends(db.get_db)):
    row = _get_contact(database, contact_id)
    if body.bot_enabled is not None:
        row.bot_enabled = body.bot_enabled
        if body.bot_enabled:
            row.needs_human = False
    if body.needs_human is not None:
        row.needs_human = body.needs_human
    if body.name is not None:
        row.name = " ".join(body.name.split())[:120] or None
    database.commit()
    return _contact_out(database, row)


@router.post("/contacts/{contact_id}/messages", response_model=sc.WaMessageOut, status_code=201)
def send(contact_id: str, body: sc.SendIn, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _get_contact(database, contact_id)
    channel = _channel(database, row.channel_id)
    text = body.text.strip()
    if not text:
        raise ApiError(400, "EMPTY", "Escreva a mensagem.", {"text": "Escreva a mensagem."})
    external_id, error = whatsapp.send_text(channel, row.phone, text)
    msg = db.WhatsAppMessageRow(contact_id=row.id, direction="out", author=p.username, body=text[:whatsapp.MAX_TEXT],
                                status="failed" if error else "sent", external_id=external_id, error=error,
                                created_at=db.utcnow())
    database.add(msg)
    row.bot_enabled = False
    row.needs_human = False
    row.unread = 0
    row.last_message_at = msg.created_at
    if error:
        channel.last_error = error[:2000]
    database.commit()
    return _message_out(msg)


@router.post("/contacts/{contact_id}/suggest", response_model=sc.SuggestOut)
def suggest(contact_id: str, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    row = _get_contact(database, contact_id)
    channel = _channel(database, row.channel_id)
    bot = database.get(db.BotRow, channel.bot_id) if channel.bot_id else None
    if bot is None:
        raise ApiError(409, "NO_BOT", "Escolha um agente para esta conexão em Conexões para receber sugestões.")
    last = database.scalar(select(db.WhatsAppMessageRow).where(db.WhatsAppMessageRow.contact_id == row.id,
                                                               db.WhatsAppMessageRow.direction == "in")
                           .order_by(db.WhatsAppMessageRow.created_at.desc()).limit(1))
    if last is None:
        raise ApiError(409, "NO_MESSAGE", "O cliente ainda não mandou mensagem.")
    history = whatsapp.history_for(database, row.id, last.created_at, get_settings().whatsapp_history)
    try:
        result, kinds = whatsapp.answer_for(database, bot, last.body, history)
    except ProviderError as e:
        raise ApiError(503, "PROVIDER", str(e))
    except Exception as e:
        raise ApiError(502, "LLM_FAILURE", f"O modelo não respondeu: {e}")
    text, sources = whatsapp.compose(bot, result, kinds)
    return sc.SuggestOut(text=text, answered=result.answered, sources=[sc.SourceOut(**x) for x in sources])
