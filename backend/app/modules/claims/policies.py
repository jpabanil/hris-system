"""Claim permission checks."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> None:
    if actor.has("claims.view") or actor.has("claims.manage"):
        return
    raise AppError("forbidden", "You do not have access to this action", 403)


def require_manage(actor: Actor) -> None:
    actor.require("claims.manage")


def require_file(actor: Actor, employee_id: str) -> None:
    if actor.has("claims.manage"):
        return
    if actor.has("self.service") and actor.employee_id == employee_id:
        return
    raise AppError("forbidden", "You do not have access to this action", 403)
