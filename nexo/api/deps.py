from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header

from nexo.config import Settings, get_settings
from nexo.security import read_token
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


def current_user(authorization: str | None = Header(None), settings: Settings = Depends(get_settings),
                 users: UserStore = Depends(get_users)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHENTICATED", "Entre para continuar.")
    claims = read_token(settings, authorization[7:].strip())
    if not claims:
        raise ApiError(401, "SESSION_EXPIRED", "Sua sessão expirou. Entre novamente.")
    user: User | None = users.get(claims.get("sub", ""))
    if user is None:
        raise ApiError(401, "UNAUTHENTICATED", "Usuário não encontrado.")
    return Principal(user.username, user.name, user.role)
