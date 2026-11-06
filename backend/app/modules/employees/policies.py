"""Who may see an employee record. Out of scope is a 404, not a 403."""

from __future__ import annotations

from app.core.actor import Actor
from app.modules.employees.models import Employee


def can_view_employee(actor: Actor, employee: Employee) -> bool:
    if employee.deleted_at is not None:
        return False
    if actor.company_id and employee.company_id != actor.company_id:
        return False
    if actor.has("employees.view"):
        return True
    mine = actor.employee_id
    if not mine:
        return False
    employee_id = str(employee.id)
    in_team = employee_id == mine or employee.reports_to == mine or mine in employee.manager_chain
    if actor.has("employees.view_team") and in_team:
        return True
    return actor.has("self.service") and employee_id == mine
