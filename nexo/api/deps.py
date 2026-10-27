from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header
from sqlalchemy import select

from nexo import db
from nexo.config import Settings, get_settings
from nexo.security import API_KEY_PREFIX, hash_api_key, read_token
from nexo.users import User, UserStore


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}


@lru_cache
def get_users() -> UserStore:
    return UserStore(get_settings().users_file)


@dataclass
class Principal:
    username: str
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _key_user(key: str, users: UserStore) -> Principal:
    with db.session() as s:
        row = s.scalar(select(db.ApiKeyRow).where(db.ApiKeyRow.key_hash == hash_api_key(key)))
        if row is None:
            raise ApiError(401, "INVALID_API_KEY", "Chave de API inválida ou revogada.")
        user = users.get(row.owner)
        if user is None:
            raise ApiError(401, "UNAUTHENTICATED", "Usuário não encontrado.")
        row.last_used_at = db.utcnow()
        s.commit()
    return Principal(user.username, user.name, user.role)


def current_user(authorization: str | None = Header(None), x_api_key: str | None = Header(None),
                 settings: Settings = Depends(get_settings), users: UserStore = Depends(get_users)) -> Principal:
    if x_api_key and x_api_key.strip():
        return _key_user(x_api_key.strip(), users)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHENTICATED", "Entre para continuar.")
    if authorization[7:].strip().startswith(API_KEY_PREFIX):
        return _key_user(authorization[7:].strip(), users)
    claims = read_token(settings, authorization[7:].strip())
    if not claims:
        raise ApiError(401, "SESSION_EXPIRED", "Sua sessão expirou. Entre novamente.")
    user: User | None = users.get(claims.get("sub", ""))
    if user is None:
        raise ApiError(401, "UNAUTHENTICATED", "Usuário não encontrado.")
    return Principal(user.username, user.name, user.role)
