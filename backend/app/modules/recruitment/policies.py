"""Recruitment rules that do not belong in the router."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError
from app.core.money import money


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> str:
    actor.require("recruitment.view")
    return company_id(actor)


def require_manage(actor: Actor) -> str:
    actor.require("recruitment.manage")
    return company_id(actor)


def valid_headcount(headcount: int) -> None:
    if headcount < 1:
        raise AppError("bad_request", "Headcount must be at least 1", 400)


def safe_token(value: str | None) -> str | None:
    if value is None:
        return None
    if value.startswith("$") or "." in value:
        raise AppError("bad_field", "Illegal field name", 400)
    return value


def split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        raise AppError("bad_request", "Applicant name is required", 400)
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def redact_public_opening(data: dict, *, salary_visible: bool) -> dict:
    if not salary_visible:
        data["salary_min"] = None
        data["salary_max"] = None
    return data


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
