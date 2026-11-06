from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.offboarding.schemas import (
    ClearancePatch,
    ExitInterviewWrite,
    FinalPayRequest,
    ResignationWrite,
)
from app.modules.offboarding.service import (
    approve_final_pay,
    compute_employee_final_pay,
    create_interview,
    create_resignation,
    get_clearance,
    get_interview,
    get_resignation,
    list_interviews,
    list_resignations,
    patch_clearance_item,
    release_final_pay,
    update_interview,
    update_resignation,
)

router = APIRouter(tags=["offboarding"])


@router.get("/resignations")
async def resignations_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_resignations(actor, page, page_size, q)


@router.post("/resignations", status_code=201)
async def resignations_create(body: ResignationWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_resignation(actor, body)


@router.get("/resignations/{id}")
async def resignations_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_resignation(actor, id)


@router.put("/resignations/{id}")
async def resignations_update(
    id: str,
    body: ResignationWrite,
    actor: Actor = Depends(require("offboarding.manage")),
) -> dict:
    return await update_resignation(actor, id, body)


@router.get("/clearances/{employee_id}")
async def clearances_get(employee_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_clearance(actor, employee_id)


@router.patch("/clearances/{employee_id}/items/{item_id}")
async def clearances_patch(
    employee_id: str,
    item_id: str,
    body: ClearancePatch,
    actor: Actor = Depends(require("offboarding.manage")),
) -> dict:
    return await patch_clearance_item(actor, employee_id, item_id, body)


@router.get("/exit-interviews")
async def interviews_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("offboarding.view")),
) -> dict:
    return await list_interviews(actor, page, page_size, q)


@router.post("/exit-interviews", status_code=201)
async def interviews_create(
    body: ExitInterviewWrite,
    actor: Actor = Depends(require("offboarding.manage")),
) -> dict:
    return await create_interview(actor, body)


@router.get("/exit-interviews/{id}")
async def interviews_get(id: str, actor: Actor = Depends(require("offboarding.view"))) -> dict:
    return await get_interview(actor, id)


@router.put("/exit-interviews/{id}")
async def interviews_update(
    id: str,
    body: ExitInterviewWrite,
    actor: Actor = Depends(require("offboarding.manage")),
) -> dict:
    return await update_interview(actor, id, body)


@router.post("/final-pay/{employee_id}/compute")
async def final_compute(
    employee_id: str,
    body: FinalPayRequest,
    actor: Actor = Depends(require("offboarding.manage")),
) -> dict:
    return await compute_employee_final_pay(actor, employee_id, body)


@router.post("/final-pay/{employee_id}/approve")
async def final_approve(
    employee_id: str,
    actor: Actor = Depends(require("offboarding.manage")),
) -> dict:
    return await approve_final_pay(actor, employee_id)


@router.post("/final-pay/{employee_id}/release")
async def final_release(
    employee_id: str,
    actor: Actor = Depends(require("offboarding.manage")),
) -> dict:
    return await release_final_pay(actor, employee_id)
