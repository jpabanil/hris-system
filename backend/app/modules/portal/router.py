from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.actor import Actor
from app.core.deps import get_actor
from app.modules.portal.service import list_attendance_logs, list_payslips

router = APIRouter(tags=["portal"])


@router.get("/payslips")
async def payslips(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_payslips(actor, page, page_size)


@router.get("/attendance-logs")
async def attendance_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_attendance_logs(actor, page, page_size)
