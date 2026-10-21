from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import bcrypt

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Nexo@2026"
DEFAULT_ADMIN_NAME = "Administrador"

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
MAX_FAILURES = 5
LOCK_SECONDS = 300


class UserError(Exception):
    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


@dataclass
class User:
    username: str
    name: str
    role: str
    password_hash: str
    created_at: str
    last_login_at: str | None = None

    def public(self) -> dict:
        return {"username": self.username, "name": self.name, "role": self.role, "created_at": self.created_at,
                "last_login_at": self.last_login_at}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def validate_password(password: str, username: str) -> None:
    if len(password) < 8 or len(password) > 72:
        raise UserError("WEAK_PASSWORD", "A senha precisa ter de 8 a 72 caracteres.", "password")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise UserError("WEAK_PASSWORD", "Use letras e números na senha.", "password")
    if username and username.lower() in password.lower():
        raise UserError("WEAK_PASSWORD", "A senha não pode conter o nome de usuário.", "password")


class UserStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self._failures: dict[str, tuple[int, float]] = {}
        self._dummy = hash_password("nexo-dummy-password-1")
        self._default_admin: bool | None = None
        with self._lock:
            users = self._read()
            if DEFAULT_ADMIN_USERNAME not in users:
                users[DEFAULT_ADMIN_USERNAME] = User(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_NAME, "admin",
                                                     hash_password(DEFAULT_ADMIN_PASSWORD), _now())
                self._write(users)

    def _read(self) -> dict[str, User]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        return {u["username"]: User(**u) for u in data.get("usuarios", [])}

    def _write(self, users: dict[str, User]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"versao": 1, "usuarios": [asdict(u) for u in sorted(users.values(), key=lambda u: u.username)]}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".usuarios-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get(self, username: str) -> User | None:
        with self._lock:
            return self._read().get(username.strip().lower())

    def all(self) -> list[User]:
        with self._lock:
            return sorted(self._read().values(), key=lambda u: u.username)

    def authenticate(self, username: str, password: str) -> User:
        key = username.strip().lower()
        count, until = self._failures.get(key, (0, 0.0))
        if until > time.time():
            minutes = max(1, int((until - time.time()) // 60) + 1)
            raise UserError("LOCKED", f"Muitas tentativas. Tente de novo em {minutes} min.")
        with self._lock:
            users = self._read()
            user = users.get(key)
            if user is None or not check_password(password, user.password_hash):
                if user is None:
                    check_password(password, self._dummy)
                count += 1
                self._failures[key] = (0, time.time() + LOCK_SECONDS) if count >= MAX_FAILURES else (count, 0.0)
                raise UserError("INVALID_CREDENTIALS", "Usuário ou senha incorretos.")
            self._failures.pop(key, None)
            user.last_login_at = _now()
            users[key] = user
            self._write(users)
            return user

    def register(self, name: str, username: str, password: str) -> User:
        key = username.strip().lower()
        name = " ".join(name.split())
        if len(name) < 2 or len(name) > 80:
            raise UserError("INVALID_NAME", "Informe seu nome (2 a 80 caracteres).", "name")
        if not USERNAME_RE.match(key):
            raise UserError("INVALID_USERNAME", "Use de 3 a 32 letras minúsculas, números, ponto, hífen ou sublinhado.",
                            "username")
        validate_password(password, key)
        with self._lock:
            users = self._read()
            if key in users:
                raise UserError("USERNAME_TAKEN", "Esse nome de usuário já existe.", "username")
            user = User(key, name, "user", hash_password(password), _now(), _now())
            users[key] = user
            self._write(users)
            return user

    def change_password(self, username: str, current: str, new: str) -> None:
        with self._lock:
            users = self._read()
            user = users.get(username)
            if user is None or not check_password(current, user.password_hash):
                raise UserError("WRONG_PASSWORD", "Senha atual incorreta.", "current_password")
            validate_password(new, username)
            user.password_hash = hash_password(new)
            users[username] = user
            self._write(users)
            self._default_admin = None

    def reset_password(self, username: str, new: str) -> None:
        key = username.strip().lower()
        with self._lock:
            users = self._read()
            user = users.get(key)
            if user is None:
                raise UserError("NOT_FOUND", "Usuário não encontrado.", "username")
            validate_password(new, key)
            user.password_hash = hash_password(new)
            users[key] = user
            self._write(users)
            self._failures.pop(key, None)
            self._default_admin = None

    def default_admin_active(self) -> bool:
        if self._default_admin is None:
            user = self.get(DEFAULT_ADMIN_USERNAME)
            self._default_admin = bool(user and check_password(DEFAULT_ADMIN_PASSWORD, user.password_hash))
        return self._default_admin
