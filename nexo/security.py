from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from nexo.config import Settings

ALGORITHM = "HS256"
API_KEY_PREFIX = "nxk_"


def new_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def secret_key(settings: Settings) -> str:
    if settings.secret:
        return settings.secret
    path = settings.data_dir / ".segredo"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def issue_token(settings: Settings, username: str, role: str) -> tuple[str, datetime]:
    expires = datetime.now(UTC) + timedelta(hours=settings.token_hours)
    payload = {"sub": username, "role": role, "exp": expires, "iat": datetime.now(UTC)}
    return jwt.encode(payload, secret_key(settings), algorithm=ALGORITHM), expires


def read_token(settings: Settings, token: str) -> dict | None:
    try:
        return jwt.decode(token, secret_key(settings), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
