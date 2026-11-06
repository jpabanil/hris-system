"""AES-GCM field encryption. Ciphertext is versioned so keys can rotate."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _key() -> bytes:
    settings = get_settings()
    if settings.field_encryption_key:
        raw = base64.b64decode(settings.field_encryption_key)
        if len(raw) != 32:
            raise RuntimeError("FIELD_ENCRYPTION_KEY must be 32 bytes, base64-encoded")
        return raw
    if settings.is_production:
        raise RuntimeError("FIELD_ENCRYPTION_KEY is required in production")
    return hashlib.sha256(settings.secret_key.encode()).digest()


def encrypt(plain: str) -> str:
    nonce = os.urandom(12)
    token = AESGCM(_key()).encrypt(nonce, plain.encode(), None)
    return "v1:" + base64.b64encode(nonce + token).decode()


def decrypt(stored: str) -> str:
    if not stored.startswith("v1:"):
        raise ValueError("unknown ciphertext version")
    blob = base64.b64decode(stored[3:])
    nonce, token = blob[:12], blob[12:]
    return AESGCM(_key()).decrypt(nonce, token, None).decode()


def mask(value: str) -> str:
    if len(value) <= 4:
        return "••••"
    return "•" * (len(value) - 4) + value[-4:]
