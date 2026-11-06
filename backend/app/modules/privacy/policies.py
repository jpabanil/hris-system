"""Privacy access and retention cutoff checks."""

from __future__ import annotations

from datetime import date

from app.core.actor import Actor
from app.core.encryption import decrypt, mask
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> str:
    actor.require("privacy.view")
    return company_id(actor)


def require_manage(actor: Actor) -> str:
    actor.require("privacy.manage")
    return company_id(actor)


def due_for_anonymization(separation_date: date | None, cutoff: date) -> bool:
    return separation_date is not None and separation_date < cutoff


def mask_value(value: str) -> str:
    if not value:
        return ""
    plain = value
    if value.startswith("v1:"):
        try:
            plain = decrypt(value)
        except Exception:
            return "••••"
    return mask(plain)
