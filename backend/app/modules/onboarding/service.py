from __future__ import annotations

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.repository import TenantRepo, api
from app.modules.employees.models import Employee
from app.modules.onboarding import policies
from app.modules.onboarding.models import OnboardingChecklist, OnboardingTemplate
from app.modules.onboarding.schemas import TaskPatch, TemplateWrite


async def list_templates(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_view(actor)
    return await TenantRepo(OnboardingTemplate, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("name",),
        sort_fields={"created_at", "name"},
        q=q,
        sort="name",
    )


async def get_template(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(OnboardingTemplate, actor).get(doc_id))


async def create_template(actor: Actor, body: TemplateWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(OnboardingTemplate, actor).create(body))


async def update_template(actor: Actor, doc_id: str, body: TemplateWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(OnboardingTemplate, actor).update(doc_id, body))


async def delete_template(actor: Actor, doc_id: str) -> None:
    policies.require_manage(actor)
    await TenantRepo(OnboardingTemplate, actor).soft_delete(doc_id)


async def _employee(company: str, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if employee is None or employee.company_id != company or employee.deleted_at is not None:
        raise AppError("not_found", "Employee not found", 404)
    return employee


async def get_checklist(actor: Actor, employee_id: str) -> dict:
    company = policies.require_view(actor)
    await _employee(company, employee_id)
    checklist = await OnboardingChecklist.find_one(
        {"company_id": company, "employee_id": employee_id}
    )
    if checklist is None:
        raise AppError("not_found", "Onboarding checklist not found", 404)
    return api(checklist)


async def patch_task(actor: Actor, employee_id: str, task_id: str, body: TaskPatch) -> dict:
    company = policies.require_manage(actor)
    await _employee(company, employee_id)
    checklist = await OnboardingChecklist.find_one(
        {"company_id": company, "employee_id": employee_id}
    )
    if checklist is None:
        raise AppError("not_found", "Onboarding checklist not found", 404)
    index = policies.parse_index(task_id, len(checklist.tasks))
    task = checklist.tasks[index]
    task.status = body.status
    if "assignee_id" in body.model_fields_set:
        task.assignee_id = body.assignee_id
    task.completed_at = utcnow() if policies.is_done(body.status) else None
    checklist.updated_at = utcnow()
    checklist.updated_by = actor.user_id
    await checklist.save()
    return api(checklist)
