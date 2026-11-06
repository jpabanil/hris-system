"""Compliance uses payroll permissions. There is no separate compliance grant."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> None:
    actor.require("payroll.view")


def require_compute(actor: Actor) -> None:
    actor.require("payroll.compute")
