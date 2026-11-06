from __future__ import annotations

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.errors import AppError
from app.core.repository import TenantRepo, api
from app.modules.employees.models import Employee, EmployeeMovement
from app.modules.performance import policies
from app.modules.performance.models import (
    Goal,
    OneOnOne,
    PerformanceReview,
    ProbationEvaluation,
    ReviewCycle,
    ReviewTemplate,
)
from app.modules.performance.schemas import (
    CycleWrite,
    GoalWrite,
    OneOnOneWrite,
    ProbationWrite,
    ReviewWrite,
    TemplateWrite,
)


async def _page(
    actor: Actor,
    model,
    search: tuple[str, ...],
    page: int,
    page_size: int,
    q: str | None,
) -> dict:
    policies.require_view(actor)
    return await TenantRepo(model, actor).list(
        page=page,
        page_size=page_size,
        search_fields=search,
        sort_fields={"created_at", "name", "title", "date"},
        q=q,
        sort="-created_at",
    )


async def list_cycles(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, ReviewCycle, ("name",), page, page_size, q)


async def get_cycle(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(ReviewCycle, actor).get(doc_id))


async def create_cycle(actor: Actor, body: CycleWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(ReviewCycle, actor).create(body))


async def update_cycle(actor: Actor, doc_id: str, body: CycleWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(ReviewCycle, actor).update(doc_id, body))


async def list_templates(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, ReviewTemplate, ("name",), page, page_size, q)


async def get_template(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(ReviewTemplate, actor).get(doc_id))


async def create_template(actor: Actor, body: TemplateWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(ReviewTemplate, actor).create(body))


async def update_template(actor: Actor, doc_id: str, body: TemplateWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(ReviewTemplate, actor).update(doc_id, body))


async def list_reviews(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, PerformanceReview, ("employee_id", "status"), page, page_size, q)


async def get_review(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(PerformanceReview, actor).get(doc_id))


async def create_review(actor: Actor, body: ReviewWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(PerformanceReview, actor).create(body))


async def update_review(actor: Actor, doc_id: str, body: ReviewWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(PerformanceReview, actor).update(doc_id, body))


async def list_goals(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, Goal, ("title", "employee_id"), page, page_size, q)


async def get_goal(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(Goal, actor).get(doc_id))


async def create_goal(actor: Actor, body: GoalWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Goal, actor).create(body))


async def update_goal(actor: Actor, doc_id: str, body: GoalWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Goal, actor).update(doc_id, body))


async def _regularize(actor: Actor, employee_id: str, session) -> None:
    employee = await Employee.get(employee_id, session=session)
    if (
        employee is None
        or employee.company_id != actor.company_id
        or employee.deleted_at is not None
    ):
        raise AppError("not_found", "Employee not found", 404)
    today = utcnow().date()
    movement = EmployeeMovement(
        company_id=actor.company_id or "",
        employee_id=str(employee.id),
        type="regularization",
        from_value={"employment_type": employee.employment_type},
        to_value={"employment_type": "regular"},
        effective_date=today,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await movement.insert(session=session)
    employee.employment_type = "regular"
    employee.regularization_date = today
    employee.revision += 1
    employee.updated_at = utcnow()
    employee.updated_by = actor.user_id
    await employee.save(session=session)


async def list_probations(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, ProbationEvaluation, ("employee_id", "outcome"), page, page_size, q)


async def get_probation(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(ProbationEvaluation, actor).get(doc_id))


async def create_probation(actor: Actor, body: ProbationWrite) -> dict:
    policies.require_manage(actor)
    if policies.should_regularize(body.outcome, ""):
        async with transaction() as session:
            doc = await TenantRepo(ProbationEvaluation, actor).create(body, session=session)
            await _regularize(actor, doc.employee_id, session)
            return api(doc)
    return api(await TenantRepo(ProbationEvaluation, actor).create(body))


async def update_probation(actor: Actor, doc_id: str, body: ProbationWrite) -> dict:
    policies.require_manage(actor)
    current = await TenantRepo(ProbationEvaluation, actor).get(doc_id)
    outcome = body.outcome if "outcome" in body.model_fields_set else current.outcome
    if policies.should_regularize(outcome, current.outcome):
        async with transaction() as session:
            doc = await TenantRepo(ProbationEvaluation, actor).update(doc_id, body, session=session)
            await _regularize(actor, doc.employee_id, session)
            return api(doc)
    return api(await TenantRepo(ProbationEvaluation, actor).update(doc_id, body))


async def list_one_on_ones(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, OneOnOne, ("employee_id", "manager_id"), page, page_size, q)


async def get_one_on_one(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(OneOnOne, actor).get(doc_id))


async def create_one_on_one(actor: Actor, body: OneOnOneWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(OneOnOne, actor).create(body))


async def update_one_on_one(actor: Actor, doc_id: str, body: OneOnOneWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(OneOnOne, actor).update(doc_id, body))
