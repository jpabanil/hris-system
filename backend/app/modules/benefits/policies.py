"""Benefit permission checks."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> None:
    if actor.has("benefits.view") or actor.has("benefits.manage"):
        return
    raise AppError("forbidden", "You do not have access to this action", 403)


def require_manage(actor: Actor) -> None:
    actor.require("benefits.manage")
