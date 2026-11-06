"""Performance rules, including when a probation outcome regularizes."""

from __future__ import annotations

from datetime import date

from app.core.actor import Actor
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> str:
    actor.require("performance.view")
    return company_id(actor)


def require_manage(actor: Actor) -> str:
    actor.require("performance.manage")
    return company_id(actor)


def should_regularize(outcome: str, previous: str) -> bool:
    return outcome == "regularize" and previous != "regularize"


def due_within(value: date | None, today: date, days: int) -> bool:
    if value is None:
        return False
    return 0 <= (value - today).days <= days
