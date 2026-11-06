"""Who may post announcements, and which roles count as HR."""

from __future__ import annotations

from datetime import date

from app.core.actor import Actor
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_read(actor: Actor) -> str:
    allowed = (
        actor.has("self.service")
        or actor.has("employees.view")
        or actor.has("employees.view_team")
        or actor.has("helpdesk.view")
        or actor.has("employees.manage")
    )
    if not allowed:
        raise AppError("forbidden", "You do not have access to this action", 403)
    return company_id(actor)


def require_manage(actor: Actor) -> str:
    if not (
        actor.has("employees.manage")
        or actor.has("helpdesk.manage")
        or actor.has("settings.manage")
    ):
        raise AppError("forbidden", "You do not have access to this action", 403)
    return company_id(actor)


def is_hr_role(name: str) -> bool:
    return "hr" in name.lower()


def is_birthday(value: date | None, today: date) -> bool:
    if value is None:
        return False
    return value.month == today.month and value.day == today.day


def within_next_days(value: date | None, today: date, days: int) -> bool:
    if value is None:
        return False
    return 0 <= (value - today).days <= days
