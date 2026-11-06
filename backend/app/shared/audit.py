"""Append-only audit log. Sensitive values are redacted before they are stored."""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.clock import utcnow
from app.shared.models import AuditLog

_SECRET_KEYS = {
    "password_hash",
    "totp_secret",
    "tin",
    "sss_no",
    "philhealth_no",
    "pagibig_no",
    "account_no",
    "details",
    "secret",
}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in _SECRET_KEYS or key.endswith("_secret") or key.endswith("_hash"):
                cleaned[key] = "***"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


async def write_audit(
    *,
    company_id: str | None,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    session: AsyncClientSession | None = None,
) -> None:
    log = AuditLog(
        company_id=company_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=redact(before) if before else None,
        after=redact(after) if after else None,
        ip=ip,
        user_agent=user_agent,
        at=utcnow(),
    )
    await log.insert(session=session)
