"""Training access and money parsing."""

from __future__ import annotations

from datetime import date

from app.core.actor import Actor
from app.core.errors import AppError
from app.core.money import money


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> str:
    actor.require("training.view")
    return company_id(actor)


def require_manage(actor: Actor) -> str:
    actor.require("training.manage")
    return company_id(actor)


def bond_still_open(bond_until: date, today: date) -> bool:
    return bond_until > today


def parse_money_input(value: object) -> str:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("float is not allowed for money")
    try:
        return format(money(value), "f")
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValueError("invalid money value") from exc
