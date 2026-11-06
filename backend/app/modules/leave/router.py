from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.core.errors import AppError
from app.modules.leave.schemas import (
    BalanceAdjust,
    LeaveBlackoutWrite,
    LeaveRequestCreate,
    LeaveTypeWrite,
)
from app.modules.leave.service import (
    adjust_balance,
    calendar,
    cancel_request,
    close_leave_year,
    create_blackout,
    create_leave_type,
    create_request,
    delete_blackout,
    delete_leave_type,
    get_blackout,
    get_leave_type,
    get_request,
    grant_company,
    list_balances,
    list_blackouts,
    list_leave_types,
    list_requests,
    rebuild_balances,
    update_blackout,
    update_leave_type,
)

router = APIRouter(tags=["leave"])


@router.get("/leave-types")
async def leave_types(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    sort: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_leave_types(actor, page, page_size, q, sort)


@router.post("/leave-types", status_code=201)
async def leave_types_create(
    body: LeaveTypeWrite, actor: Actor = Depends(require("leave.manage"))
) -> dict:
    return await create_leave_type(actor, body)


@router.get("/leave-types/{type_id}")
async def leave_types_get(type_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_leave_type(actor, type_id)


@router.put("/leave-types/{type_id}")
async def leave_types_update(
    type_id: str, body: LeaveTypeWrite, actor: Actor = Depends(require("leave.manage"))
) -> dict:
    return await update_leave_type(actor, type_id, body)


@router.delete("/leave-types/{type_id}", status_code=204)
async def leave_types_delete(
    type_id: str, actor: Actor = Depends(require("leave.manage"))
) -> Response:
    await delete_leave_type(actor, type_id)
    return Response(status_code=204)


@router.get("/leave-blackouts")
async def leave_blackouts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_blackouts(actor, page, page_size)


@router.post("/leave-blackouts", status_code=201)
async def leave_blackouts_create(
    body: LeaveBlackoutWrite, actor: Actor = Depends(require("leave.manage"))
) -> dict:
    return await create_blackout(actor, body)


@router.get("/leave-blackouts/{blackout_id}")
async def leave_blackouts_get(blackout_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_blackout(actor, blackout_id)


@router.put("/leave-blackouts/{blackout_id}")
async def leave_blackouts_update(
    blackout_id: str,
    body: LeaveBlackoutWrite,
    actor: Actor = Depends(require("leave.manage")),
) -> dict:
    return await update_blackout(actor, blackout_id, body)


@router.delete("/leave-blackouts/{blackout_id}", status_code=204)
async def leave_blackouts_delete(
    blackout_id: str, actor: Actor = Depends(require("leave.manage"))
) -> Response:
    await delete_blackout(actor, blackout_id)
    return Response(status_code=204)


@router.get("/leave-requests")
async def leave_requests(
    scope: str | None = None,
    employee_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_requests(
        actor, scope=scope, employee_id=employee_id, page=page, page_size=page_size
    )


@router.post("/leave-requests", status_code=201)
async def leave_requests_create(
    body: LeaveRequestCreate, actor: Actor = Depends(get_actor)
) -> dict:
    return await create_request(actor, body)


@router.get("/leave-requests/{request_id}")
async def leave_requests_get(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_request(actor, request_id)


@router.post("/leave-requests/{request_id}/cancel")
async def leave_requests_cancel(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await cancel_request(actor, request_id)


@router.get("/leave-balances")
async def leave_balances(
    employee_id: str | None = None,
    year: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_balances(actor, employee_id, year, page, page_size)


@router.post("/leave-balances/adjust")
async def leave_balances_adjust(
    body: BalanceAdjust, actor: Actor = Depends(require("leave.manage"))
) -> dict:
    return await adjust_balance(actor, body)


def _company(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


@router.post("/leave-balances/rebuild")
async def leave_balances_rebuild(actor: Actor = Depends(require("leave.manage"))) -> dict:
    await rebuild_balances(_company(actor))
    return {"ok": True}


@router.post("/leave-balances/grant")
async def leave_balances_grant(actor: Actor = Depends(require("leave.manage"))) -> dict:
    return {"granted": await grant_company(_company(actor))}


@router.post("/leave-balances/close-year")
async def leave_balances_close(
    year: int = Query(..., ge=2000, le=2100),
    actor: Actor = Depends(require("leave.manage")),
) -> dict:
    return {"closed": await close_leave_year(_company(actor), year)}


@router.get("/leave/calendar")
async def leave_calendar(
    start: date,
    end: date,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await calendar(actor, start, end)
