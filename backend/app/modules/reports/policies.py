"""Report catalog and safe filter tokens."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError

REPORTS = (
    "headcount",
    "masterlist",
    "attendance-summary",
    "leave-balances",
    "payroll-register",
    "recruitment-funnel",
    "disciplinary-cases",
    "policy-acknowledgments",
)


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_view(actor: Actor) -> str:
    actor.require("reports.view")
    return company_id(actor)


def require_export(actor: Actor) -> str:
    actor.require("reports.export")
    return company_id(actor)


def require_known(report: str) -> str:
    if report not in REPORTS:
        raise AppError("not_found", "Unknown report", 404)
    return report


def safe_token(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if value.startswith("$") or "." in value:
        raise AppError("bad_field", "Illegal field name", 400)
    return value
