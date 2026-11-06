"""Benefits HTTP routes. Mounted at /api/v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.benefits.schemas import BenefitEnrollmentWrite, BenefitPlanWrite
from app.modules.benefits.service import (
    create_enrollment,
    create_plan,
    delete_enrollment,
    delete_plan,
    get_enrollment,
    get_plan,
    list_enrollments,
    list_plans,
    update_enrollment,
    update_plan,
)

router = APIRouter(tags=["benefits"])


@router.get("/benefit-plans")
async def benefit_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("benefits.view")),
) -> dict:
    return await list_plans(actor, page, page_size, q)


@router.post("/benefit-plans", status_code=201)
async def benefit_plans_create(
    body: BenefitPlanWrite, actor: Actor = Depends(require("benefits.manage"))
) -> dict:
    return await create_plan(actor, body)


@router.get("/benefit-plans/{plan_id}")
async def benefit_plans_get(plan_id: str, actor: Actor = Depends(require("benefits.view"))) -> dict:
    return await get_plan(actor, plan_id)


@router.put("/benefit-plans/{plan_id}")
async def benefit_plans_update(
    plan_id: str, body: BenefitPlanWrite, actor: Actor = Depends(require("benefits.manage"))
) -> dict:
    return await update_plan(actor, plan_id, body)


@router.delete("/benefit-plans/{plan_id}", status_code=204)
async def benefit_plans_delete(
    plan_id: str, actor: Actor = Depends(require("benefits.manage"))
) -> Response:
    await delete_plan(actor, plan_id)
    return Response(status_code=204)


@router.get("/benefit-enrollments")
async def benefit_enrollments(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    employee_id: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_enrollments(actor, page, page_size, q, employee_id)


@router.post("/benefit-enrollments", status_code=201)
async def benefit_enrollments_create(
    body: BenefitEnrollmentWrite, actor: Actor = Depends(require("benefits.manage"))
) -> dict:
    return await create_enrollment(actor, body)


@router.get("/benefit-enrollments/{enrollment_id}")
async def benefit_enrollments_get(
    enrollment_id: str, actor: Actor = Depends(get_actor)
) -> dict:
    return await get_enrollment(actor, enrollment_id)


@router.put("/benefit-enrollments/{enrollment_id}")
async def benefit_enrollments_update(
    enrollment_id: str,
    body: BenefitEnrollmentWrite,
    actor: Actor = Depends(require("benefits.manage")),
) -> dict:
    return await update_enrollment(actor, enrollment_id, body)


@router.delete("/benefit-enrollments/{enrollment_id}", status_code=204)
async def benefit_enrollments_delete(
    enrollment_id: str, actor: Actor = Depends(require("benefits.manage"))
) -> Response:
    await delete_enrollment(actor, enrollment_id)
    return Response(status_code=204)
