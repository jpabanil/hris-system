"""Onboarding checks used by the service."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError

_DONE = {"done", "completed", "complete"}


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> str:
    actor.require("onboarding.view")
    return company_id(actor)


def require_manage(actor: Actor) -> str:
    actor.require("onboarding.manage")
    return company_id(actor)


def is_done(status: str) -> bool:
    return status.strip().lower() in _DONE


def parse_index(raw: str, size: int) -> int:
    if not raw.isdigit():
        raise AppError("not_found", "Task not found", 404)
    index = int(raw)
    if index >= size:
        raise AppError("not_found", "Task not found", 404)
    return index
