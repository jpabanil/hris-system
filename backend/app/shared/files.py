"""Local file storage with HMAC signed URLs. S3 can replace the writer later."""

from __future__ import annotations

import hashlib
import hmac
import mimetypes
import uuid
from pathlib import Path

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import AppError
from app.shared.models import StoredFile

_ALLOWED = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_BYTES = 10 * 1024 * 1024


def _root() -> Path:
    path = Path(get_settings().storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload(
    actor: Actor,
    *,
    filename: str,
    content_type: str,
    data: bytes,
    confidential: bool = False,
) -> StoredFile:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    guessed = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if guessed not in _ALLOWED:
        raise AppError("bad_file", "This file type is not allowed", 400)
    if len(data) > _MAX_BYTES:
        raise AppError("bad_file", "File is larger than 10 MB", 400)
    key = f"{actor.company_id}/{uuid.uuid4().hex}"
    destination = _root() / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    stored = StoredFile(
        company_id=actor.company_id,
        key=key,
        filename=filename,
        content_type=guessed,
        size=len(data),
        confidential=confidential,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await stored.insert()
    return stored


def signed_url(key: str, seconds: int = 300) -> str:
    settings = get_settings()
    expires = int(utcnow().timestamp()) + seconds
    signature = hmac.new(
        settings.secret_key.encode(),
        f"{key}.{expires}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{settings.api_base_url}/api/v1/files/content?key={key}&exp={expires}&sig={signature}"


def read_signed(key: str, exp: int, sig: str) -> tuple[bytes, str, str]:
    settings = get_settings()
    if int(utcnow().timestamp()) > exp:
        raise AppError("expired", "This link has expired", 403)
    expected = hmac.new(
        settings.secret_key.encode(),
        f"{key}.{exp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise AppError("forbidden", "This link is not valid", 403)
    path = _root() / key
    if not path.is_file():
        raise AppError("not_found", "File not found", 404)
    return path.read_bytes(), path.name, "application/octet-stream"
