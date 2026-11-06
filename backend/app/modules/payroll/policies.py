"""Payroll permission checks. Compute is never treated as approve."""

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


def require_tables(actor: Actor) -> None:
    actor.require("payroll.tables")


def require_approve(actor: Actor) -> None:
    """Only payroll.approve. payroll.compute does not pass this check."""
    if actor.is_superadmin:
        return
    if "payroll.approve" not in actor.permissions:
        raise AppError("forbidden", "You do not have access to this action", 403)


def require_separation(actor: Actor, computed_by: str | None) -> None:
    if not computed_by:
        raise AppError("conflict", "This run has no computer recorded", 409)
    if actor.user_id == computed_by:
        raise AppError("forbidden", "separation of duties", 403)


def require_payslip_access(actor: Actor, employee_id: str, published: bool) -> None:
    if actor.has("payroll.view"):
        return
    owns = actor.employee_id == employee_id and published and actor.has("self.service")
    if not owns:
        raise AppError("forbidden", "You do not have access to this action", 403)
