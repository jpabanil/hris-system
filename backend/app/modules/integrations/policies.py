"""Webhook access. Secrets are write-only in API responses."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_manage(actor: Actor) -> str:
    actor.require("settings.manage")
    return company_id(actor)


def redact_webhook(data: dict) -> dict:
    cleaned = dict(data)
    cleaned.pop("secret", None)
    return cleaned


def require_secret(secret: str) -> None:
    if not secret or secret.startswith("$"):
        raise AppError("bad_request", "Webhook secret is required", 400)
