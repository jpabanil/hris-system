"""Benefit plans and enrollments. Dependent costs become recurring deductions."""

from __future__ import annotations

from decimal import Decimal

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.money import D, money
from app.core.repository import TenantRepo, api
from app.modules.benefits import policies
from app.modules.benefits.models import BenefitEnrollment, BenefitPlan
from app.modules.benefits.schemas import BenefitEnrollmentWrite, BenefitPlanWrite
from app.modules.employees.models import Employee
from app.modules.payroll.models import RecurringDeduction

_HMO = "HMO dependents"


async def _employee(actor: Actor, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if (
        employee is None
        or employee.company_id != actor.company_id
        or employee.deleted_at is not None
    ):
        raise AppError("not_found", "Employee not found", 404)
    return employee


async def _plan(actor: Actor, plan_id: str) -> BenefitPlan:
    plan = await TenantRepo(BenefitPlan, actor).get(plan_id)
    if not isinstance(plan, BenefitPlan):
        raise AppError("not_found", "Benefit plan not found", 404)
    return plan


async def _create_dependent_deduction(
    enrollment: BenefitEnrollment, plan: BenefitPlan, actor_id: str | None
) -> None:
    count = len(enrollment.covered_dependents)
    if count <= 0:
        return
    existing = await RecurringDeduction.find_one(
        {
            "company_id": enrollment.company_id,
            "employee_id": enrollment.employee_id,
            "type": _HMO,
        }
    )
    if existing is not None:
        return
    amount = money(D(plan.dependent_cost) * Decimal(count))
    deduction = RecurringDeduction(
        company_id=enrollment.company_id,
        employee_id=enrollment.employee_id,
        type=_HMO,
        label=_HMO,
        amount=amount,
        frequency="every_period",
        until=enrollment.effective_to,
        created_by=actor_id,
        updated_by=actor_id,
    )
    await deduction.insert()


async def ensure_deduction_for_enrollment(enrollment_id: str) -> None:
    enrollment = await BenefitEnrollment.get(enrollment_id)
    if enrollment is None:
        return
    plan = await BenefitPlan.get(enrollment.plan_id)
    if plan is None or plan.company_id != enrollment.company_id or plan.deleted_at is not None:
        return
    await _create_dependent_deduction(enrollment, plan, enrollment.updated_by)


async def list_plans(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_view(actor)
    return await TenantRepo(BenefitPlan, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("plan_name", "provider", "type"),
        sort_fields={"created_at", "plan_name"},
        q=q,
        sort="plan_name",
    )


async def create_plan(actor: Actor, body: BenefitPlanWrite) -> dict:
    policies.require_manage(actor)
    doc = await TenantRepo(BenefitPlan, actor).create(body)
    return api(doc)


async def get_plan(actor: Actor, plan_id: str) -> dict:
    policies.require_view(actor)
    return api(await _plan(actor, plan_id))


async def update_plan(actor: Actor, plan_id: str, body: BenefitPlanWrite) -> dict:
    policies.require_manage(actor)
    doc = await TenantRepo(BenefitPlan, actor).update(plan_id, body)
    return api(doc)


async def delete_plan(actor: Actor, plan_id: str) -> None:
    policies.require_manage(actor)
    await TenantRepo(BenefitPlan, actor).soft_delete(plan_id)


async def list_enrollments(
    actor: Actor, page: int, page_size: int, q: str | None, employee_id: str | None
) -> dict:
    if not (actor.has("benefits.view") or actor.has("benefits.manage")):
        if actor.has("self.service") and actor.employee_id:
            employee_id = actor.employee_id
        else:
            raise AppError("forbidden", "You do not have access to this action", 403)
    extra = {"employee_id": employee_id} if employee_id else None
    return await TenantRepo(BenefitEnrollment, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("card_no", "status"),
        sort_fields={"created_at", "status"},
        q=q,
        sort="-created_at",
        extra=extra,
    )


async def create_enrollment(actor: Actor, body: BenefitEnrollmentWrite) -> dict:
    policies.require_manage(actor)
    await _employee(actor, body.employee_id)
    plan = await _plan(actor, body.plan_id)
    if body.effective_to and body.effective_to < body.effective_from:
        raise AppError("bad_dates", "Coverage end is before the start", 400)
    doc = await TenantRepo(BenefitEnrollment, actor).create(body)
    if isinstance(doc, BenefitEnrollment):
        await _create_dependent_deduction(doc, plan, actor.user_id)
    return api(doc)


async def get_enrollment(actor: Actor, enrollment_id: str) -> dict:
    enrollment = await TenantRepo(BenefitEnrollment, actor).get(enrollment_id)
    if not isinstance(enrollment, BenefitEnrollment):
        raise AppError("not_found", "Enrollment not found", 404)
    if not (actor.has("benefits.view") or actor.has("benefits.manage")):
        if not (actor.has("self.service") and actor.employee_id == enrollment.employee_id):
            raise AppError("forbidden", "You do not have access to this action", 403)
    return api(enrollment)


async def update_enrollment(
    actor: Actor, enrollment_id: str, body: BenefitEnrollmentWrite
) -> dict:
    policies.require_manage(actor)
    await _employee(actor, body.employee_id)
    plan = await _plan(actor, body.plan_id)
    if body.effective_to and body.effective_to < body.effective_from:
        raise AppError("bad_dates", "Coverage end is before the start", 400)
    doc = await TenantRepo(BenefitEnrollment, actor).update(enrollment_id, body)
    if isinstance(doc, BenefitEnrollment):
        await _create_dependent_deduction(doc, plan, actor.user_id)
    return api(doc)


async def delete_enrollment(actor: Actor, enrollment_id: str) -> None:
    policies.require_manage(actor)
    doc = await TenantRepo(BenefitEnrollment, actor).get(enrollment_id)
    doc.status = "cancelled"
    doc.updated_at = utcnow()
    doc.updated_by = actor.user_id
    await doc.save()
