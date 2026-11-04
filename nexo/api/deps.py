from __future__ import annotations

import math
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header, Request
from sqlalchemy import select

from nexo import db
from nexo.config import Settings, get_settings
from nexo.security import API_KEY_PREFIX, hash_api_key, read_token
from nexo.users import User, UserStore


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict[str, str] | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}
        self.headers = headers or {}


@lru_cache
def get_users() -> UserStore:
    return UserStore(get_settings().users_file)


KEY_SCOPES = ("full", "ask", "feed")

SCOPE_ROUTES: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "ask": tuple((m, re.compile(p)) for m, p in (
        ("POST", r"^/api/ask$"),
        ("POST", r"^/api/search$"),
        ("GET", r"^/api/bots(/[^/]+)?$"),
        ("GET", r"^/api/bases(/[^/]+)?$"),
        ("POST", r"^/api/conversations$"),
        ("GET", r"^/api/conversations/[^/]+$"),
        ("POST", r"^/api/conversations/[^/]+/messages(/stream)?$"),
        ("GET", r"^/api/conversations/[^/]+/export$"),
        ("POST", r"^/api/messages/[^/]+/feedback$"),
        ("GET", r"^/api/auth/me$"),
    )),
    "feed": tuple((m, re.compile(p)) for m, p in (
        ("GET", r"^/api/bases(/[^/]+)?$"),
        ("GET", r"^/api/bases/[^/]+/documents$"),
        ("POST", r"^/api/bases/[^/]+/(documents|texts|links)$"),
        ("GET", r"^/api/documents/[^/]+(/text|/chunks)?$"),
        ("PUT", r"^/api/documents/[^/]+/text$"),
        ("DELETE", r"^/api/documents/[^/]+$"),
        ("POST", r"^/api/documents/[^/]+/(reindex|refetch)$"),
        ("GET", r"^/api/formats$"),
        ("GET", r"^/api/auth/me$"),
    )),
}


@dataclass
class Principal:
    username: str
    name: str
    role: str
    key_scope: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin" and self.key_scope in (None, "full")


def _allowed(scope: str, method: str, path: str) -> bool:
    if scope == "full":
        return True
    return any(m == method and p.match(path) for m, p in SCOPE_ROUTES.get(scope, ()))


def _key_user(key: str, users: UserStore, request: Request | None) -> Principal:
    with db.session() as s:
        row = s.scalar(select(db.ApiKeyRow).where(db.ApiKeyRow.key_hash == hash_api_key(key)))
        if row is None:
            raise ApiError(401, "INVALID_API_KEY", "Chave de API inválida ou revogada.")
        if row.expires_at is not None and row.expires_at <= db.utcnow():
            raise ApiError(401, "API_KEY_EXPIRED", "Esta chave de API venceu. Crie outra em Integrações.")
        user = users.get(row.owner)
        if user is None:
            raise ApiError(401, "UNAUTHENTICATED", "Usuário não encontrado.")
        scope = row.scope or "full"
        if request is not None and not _allowed(scope, request.method, request.url.path):
            raise ApiError(403, "KEY_SCOPE", "Esta chave de API não tem permissão para esta rota.")
        row.last_used_at = db.utcnow()
        s.commit()
    return Principal(user.username, user.name, user.role, scope)


def current_user(request: Request, authorization: str | None = Header(None), x_api_key: str | None = Header(None),
                 settings: Settings = Depends(get_settings), users: UserStore = Depends(get_users)) -> Principal:
    if x_api_key and x_api_key.strip():
        return _key_user(x_api_key.strip(), users, request)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHENTICATED", "Entre para continuar.")
    if authorization[7:].strip().startswith(API_KEY_PREFIX):
        return _key_user(authorization[7:].strip(), users, request)
    claims = read_token(settings, authorization[7:].strip())
    if not claims:
        raise ApiError(401, "SESSION_EXPIRED", "Sua sessão expirou. Entre novamente.")
    user: User | None = users.get(claims.get("sub", ""))
    if user is None:
        raise ApiError(401, "UNAUTHENTICATED", "Usuário não encontrado.")
    if int(claims.get("ver", 0) or 0) != user.session_version:
        raise ApiError(401, "SESSION_REVOKED", "Sua sessão foi encerrada. Entre novamente.")
    return Principal(user.username, user.name, user.role)


class RateLimiter:
    def __init__(self, window: float = 60.0):
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int) -> int | None:
        if limit <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, math.ceil(self.window - (now - hits[0])))
            hits.append(now)
            return None


def limiter_for(request: Request) -> RateLimiter:
    state = request.app.state
    if not hasattr(state, "limiter"):
        state.limiter = RateLimiter()
    return state.limiter


def question_quota(request: Request, p: Principal = Depends(current_user),
                   settings: Settings = Depends(get_settings)) -> Principal:
    wait = limiter_for(request).hit(p.username, settings.rate_limit)
    if wait is not None:
        raise ApiError(429, "RATE_LIMITED", f"Muitas perguntas em pouco tempo. Tente de novo em {wait} s.",
                       headers={"Retry-After": str(wait)})
    return p
