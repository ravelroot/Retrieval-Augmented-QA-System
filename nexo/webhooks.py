from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.error
import uuid
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime

from sqlalchemy import select

from nexo import __version__, db
from nexo.config import get_settings

log = logging.getLogger("nexo.webhooks")

EVENTS = ("document.ready", "document.failed", "question.unanswered", "feedback.negative", "whatsapp.message",
          "whatsapp.handoff")

RETRY_DELAYS = (1.0, 3.0)
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nexo-webhook")
_pending: set[Future] = set()
_pending_lock = threading.Lock()


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _post(url: str, secret: str, event: str, body: bytes, delivery: str,
          attempt: int) -> tuple[int | None, str | None]:
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": f"Nexo/{__version__}",
        "X-Nexo-Event": event,
        "X-Nexo-Delivery": delivery,
        "X-Nexo-Attempt": str(attempt),
        "X-Nexo-Signature": sign(secret, body),
    })
    try:
        with urllib.request.urlopen(request, timeout=get_settings().webhook_timeout) as response:
            return response.status, None
    except urllib.error.HTTPError as e:
        return e.code, f"O destino respondeu HTTP {e.code}."
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, TimeoutError):
            return None, "Tempo esgotado ao entregar."
        return None, f"Falha na entrega: {reason}"
    except TimeoutError:
        return None, "Tempo esgotado ao entregar."
    except Exception as e:
        return None, f"Falha na entrega: {e}"


def _retryable(status: int | None, error: str | None) -> bool:
    return bool(error) and (status is None or status in RETRY_STATUS)


def deliver(webhook_id: str, event: str, data: dict, retries: bool = True) -> tuple[int | None, str | None]:
    with db.session() as s:
        row = s.get(db.WebhookRow, webhook_id)
        if row is None:
            return None, "Webhook não encontrado."
        url, secret = row.url, row.secret
    delivery = uuid.uuid4().hex
    payload = {"event": event, "delivery": delivery,
               "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(), "data": data}
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    delays = RETRY_DELAYS if retries else ()
    attempt = 1
    status, error = _post(url, secret, event, body, delivery, attempt)
    while _retryable(status, error) and attempt <= len(delays):
        time.sleep(delays[attempt - 1])
        attempt += 1
        status, error = _post(url, secret, event, body, delivery, attempt)
    if error:
        if attempt > 1:
            error = f"{error} ({attempt} tentativas)"
        log.warning("Webhook %s (%s): %s", webhook_id, event, error)
    with db.session() as s:
        row = s.get(db.WebhookRow, webhook_id)
        if row is not None:
            row.last_status = status
            row.last_error = error[:2000] if error else None
            row.last_delivery_at = db.utcnow()
            s.commit()
    return status, error


def _safe_deliver(webhook_id: str, event: str, data: dict) -> None:
    try:
        deliver(webhook_id, event, data)
    except Exception:
        log.exception("Falha ao entregar o webhook %s", webhook_id)


def emit(event: str, data: dict) -> int:
    try:
        with db.session() as s:
            rows = s.scalars(select(db.WebhookRow).where(db.WebhookRow.active.is_(True))).all()
            ids = [r.id for r in rows if event in r.event_list]
        for webhook_id in ids:
            future = _executor.submit(_safe_deliver, webhook_id, event, data)
            with _pending_lock:
                _pending.add(future)
            future.add_done_callback(_done)
        return len(ids)
    except Exception:
        log.exception("Falha ao disparar o evento %s", event)
        return 0


def _done(future: Future) -> None:
    with _pending_lock:
        _pending.discard(future)


def wait_idle(timeout: float = 30.0) -> None:
    with _pending_lock:
        futures = list(_pending)
    wait(futures, timeout=timeout)
