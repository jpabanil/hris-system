"""Helpdesk access and the two-business-day SLA."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.actor import Actor
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def can_manage(actor: Actor) -> bool:
    return actor.has("helpdesk.manage")


def can_view_all(actor: Actor) -> bool:
    return actor.has("helpdesk.view") or actor.has("helpdesk.manage")


def require_file(actor: Actor) -> str:
    if not (can_manage(actor) or actor.has("self.service")):
        raise AppError("forbidden", "You do not have access to this action", 403)
    return company_id(actor)


def can_see(actor: Actor, employee_id: str) -> bool:
    if can_view_all(actor):
        return True
    return actor.employee_id is not None and actor.employee_id == employee_id


def add_business_days(start: datetime, days: int = 2) -> datetime:
    current = start
    left = days
    while left > 0:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current
