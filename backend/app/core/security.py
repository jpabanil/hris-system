"""Passwords, JWT, and CSRF. Refresh tokens are stored only as hashes."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.clock import utcnow
from app.core.config import get_settings

_hasher = PasswordHash.recommended()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_csrf() -> str:
    return secrets.token_urlsafe(32)


def new_refresh() -> str:
    return secrets.token_urlsafe(48)


def encode_token(payload: dict[str, Any], *, minutes: int = 0, days: int = 0) -> str:
    settings = get_settings()
    now = utcnow()
    body = dict(payload)
    body["iat"] = int(now.timestamp())
    expires = now + timedelta(minutes=minutes, days=days)
    body["exp"] = int(expires.timestamp())
    return jwt.encode(body, settings.secret_key, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        from app.core.errors import AppError

        raise AppError("unauthorized", "Session is not valid", 401) from exc
    if not isinstance(data, dict):
        from app.core.errors import AppError

        raise AppError("unauthorized", "Session is not valid", 401)
    return data
