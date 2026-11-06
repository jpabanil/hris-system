"""Clearance, notice, and final-pay amount rules."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.core.actor import Actor
from app.core.errors import AppError
from app.core.money import money


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> str:
    if (
        actor.has("offboarding.view")
        or actor.has("offboarding.manage")
        or actor.has("self.service")
    ):
        return company_id(actor)
    raise AppError("forbidden", "You do not have access to this action", 403)


def require_manage(actor: Actor) -> str:
    actor.require("offboarding.manage")
    return company_id(actor)


def can_file_resignation(actor: Actor, employee_id: str) -> bool:
    if actor.has("offboarding.manage"):
        return True
    return actor.has("self.service") and actor.employee_id == employee_id


def assert_notice(filed: date, last: date) -> None:
    if last < filed:
        raise AppError("bad_request", "Last working day cannot be before the file date", 400)


def clearance_status(items: list, unreturned_asset: bool) -> str:
    if unreturned_asset:
        return "open"
    for item in items:
        if getattr(item, "blocking", False) and getattr(item, "cleared_at", None) is None:
            return "open"
    return "cleared"


def parse_index(raw: str, size: int) -> int:
    if not raw.isdigit():
        raise AppError("not_found", "Clearance item not found", 404)
    index = int(raw)
    if index >= size:
        raise AppError("not_found", "Clearance item not found", 404)
    return index


def remaining_days(last_day: date | None, today: date, given: int | None) -> int:
    if given is not None:
        return given
    if last_day is None:
        return 0
    return max((last_day - today).days, 0)


def prorate_salary(daily_rate: Decimal, days: int) -> Decimal:
    if days <= 0:
        return Decimal("0.00")
    return money(daily_rate * Decimal(days))


def accountability_total(amounts: list[Decimal]) -> Decimal:
    total = Decimal("0.00")
    for amount in amounts:
        if amount > 0:
            total += amount
    return money(total)


def parse_money_input(value: object) -> str:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("float is not allowed for money")
    try:
        return format(money(value), "f")
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValueError("invalid money value") from exc


def parse_optional_money(value: object) -> str | None:
    if value is None or value == "":
        return None
    return parse_money_input(value)
