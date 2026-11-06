"""Disciplinary state machine and who may read case details."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError

_STEPS = {
    "issue-nte": ("open", "nte_issued"),
    "record-explanation": ("nte_issued", "explanation_received"),
    "schedule-hearing": ("explanation_received", "hearing"),
    "decide": ("hearing", "decided"),
}


def company_id(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_manage(actor: Actor) -> str:
    actor.require("relations.manage")
    return company_id(actor)


def require_case_read(actor: Actor) -> str:
    allowed = (
        actor.has("relations.view")
        or actor.has("relations.manage")
        or actor.has("employees.view_team")
    )
    if not allowed:
        raise AppError("forbidden", "You do not have access to this action", 403)
    return company_id(actor)


def can_view_details(actor: Actor) -> bool:
    return actor.has("relations.view")


def transition(action: str, current: str) -> str:
    expected, nxt = _STEPS[action]
    if current != expected:
        raise AppError("conflict", f"Cannot {action} while the case is {current}", 409)
    return nxt


def assert_manual_close(current: str, new: str) -> None:
    if current == new:
        return
    if current == "decided" and new == "closed":
        return
    raise AppError("conflict", "That status change is not allowed", 409)


def can_file_grievance(actor: Actor) -> bool:
    return actor.has("relations.manage") or actor.has("self.service")


def can_acknowledge(actor: Actor) -> bool:
    return actor.employee_id is not None and (
        actor.has("self.service") or actor.has("relations.manage") or actor.has("employees.view")
    )
