from __future__ import annotations

from contextvars import ContextVar

request_id: ContextVar[str | None] = ContextVar("nexo_request_id", default=None)
client_ip: ContextVar[str | None] = ContextVar("nexo_client_ip", default=None)
