"""Who can see or file attendance. Team scope walks the manager chain."""

from __future__ import annotations

from typing import Any

from app.core.actor import Actor
from app.core.errors import AppError
from app.modules.employees.models import Employee


def require_company(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def require_reader(actor: Actor) -> None:
    if actor.has("attendance.view") or actor.has("attendance.manage"):
        return
    if actor.has("attendance.view_team") or actor.has("self.service"):
        return
    raise AppError("forbidden", "You do not have access to this action", 403)


def require_clock(actor: Actor) -> None:
    if actor.has("self.service") or actor.has("attendance.manage"):
        return
    raise AppError("forbidden", "You do not have access to this action", 403)


async def team_employee_ids(company_id: str, manager_employee_id: str) -> list[str]:
    """Employees who report up to this manager, directly or through manager_chain."""
    if not company_id or not manager_employee_id:
        return []
    rows = await Employee.find({"company_id": company_id, "deleted_at": None}).to_list()
    children: dict[str, list[str]] = {}
    extra: list[str] = []
    for row in rows:
        row_id = str(row.id)
        if manager_employee_id in row.manager_chain:
            extra.append(row_id)
        if row.reports_to:
            children.setdefault(row.reports_to, []).append(row_id)
    seen: set[str] = set()
    stack = [*children.get(manager_employee_id, []), *extra]
    while stack:
        current = stack.pop()
        if current == manager_employee_id or current in seen:
            continue
        seen.add(current)
        stack.extend(children.get(current, []))
    return sorted(seen)


async def employee_scope(actor: Actor, employee_id: str | None) -> dict[str, Any]:
    """Mongo filter fragment for one employee, the team, or the whole company."""
    require_company(actor)
    if actor.has("attendance.view") or actor.has("attendance.manage"):
        if employee_id:
            return {"employee_id": employee_id}
        return {}
    if actor.has("attendance.view_team") and actor.employee_id:
        team = await team_employee_ids(actor.company_id or "", actor.employee_id)
        allowed = set(team)
        allowed.add(actor.employee_id)
        if employee_id:
            if employee_id not in allowed:
                raise AppError("forbidden", "You do not have access to this action", 403)
            return {"employee_id": employee_id}
        return {"employee_id": {"$in": sorted(allowed)}}
    if actor.has("self.service") and actor.employee_id:
        if employee_id and employee_id != actor.employee_id:
            raise AppError("forbidden", "You do not have access to this action", 403)
        return {"employee_id": actor.employee_id}
    raise AppError("forbidden", "You do not have access to this action", 403)


def subject_employee_id(employee_id: str | None, requester_id: str | None) -> str:
    return employee_id or requester_id or ""


def resolve_filer(actor: Actor, employee_id: str | None) -> str:
    """Own employee id, unless attendance.manage files for someone else."""
    if employee_id and employee_id != actor.employee_id:
        actor.require("attendance.manage")
        return employee_id
    if not actor.has("attendance.manage") and not actor.has("self.service"):
        actor.require("self.service")
    chosen = employee_id or actor.employee_id
    if not chosen:
        raise AppError("employee_required", "Employee is required", 400)
    return chosen


async def assert_can_touch(actor: Actor, employee_id: str) -> None:
    if actor.has("attendance.view") or actor.has("attendance.manage"):
        return
    if actor.employee_id == employee_id and (
        actor.has("self.service") or actor.has("attendance.view_team")
    ):
        return
    if actor.has("attendance.view_team") and actor.employee_id:
        team = await team_employee_ids(actor.company_id or "", actor.employee_id)
        if employee_id in team:
            return
    raise AppError("forbidden", "You do not have access to this action", 403)
