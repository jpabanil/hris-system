"""Compliance HTTP routes. Mounted at /api/v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import require
from app.modules.compliance.schemas import RemittanceWrite
from app.modules.compliance.service import (
    alphalist,
    annualize_year,
    compute_thirteenth,
    create_remittance,
    delete_remittance,
    generate_2316,
    get_remittance,
    list_remittances,
    remittance_report,
    update_remittance,
)

router = APIRouter(tags=["compliance"])


@router.post("/year-end/{year}/annualize")
async def year_end_annualize(
    year: int, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await annualize_year(actor, year)


@router.get("/year-end/{year}/2316")
async def year_end_2316(year: int, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await generate_2316(actor, year)


@router.get("/year-end/{year}/alphalist")
async def year_end_alphalist(
    year: int,
    export_format: str = Query("json", alias="format"),
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await alphalist(actor, year, export_format)


@router.get("/remittances/reports/{agency}")
async def remittances_report(
    agency: str,
    month: str = Query(...),
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await remittance_report(actor, agency, month)


@router.get("/remittances")
async def remittances(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_remittances(actor, page, page_size)


@router.post("/remittances", status_code=201)
async def remittances_create(
    body: RemittanceWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await create_remittance(actor, body)


@router.get("/remittances/{remittance_id}")
async def remittances_get(
    remittance_id: str, actor: Actor = Depends(require("payroll.view"))
) -> dict:
    return await get_remittance(actor, remittance_id)


@router.put("/remittances/{remittance_id}")
async def remittances_update(
    remittance_id: str, body: RemittanceWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await update_remittance(actor, remittance_id, body)


@router.delete("/remittances/{remittance_id}", status_code=204)
async def remittances_delete(
    remittance_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> Response:
    await delete_remittance(actor, remittance_id)
    return Response(status_code=204)


@router.post("/thirteenth-month/{year}/compute")
async def thirteenth_compute(
    year: int, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await compute_thirteenth(actor, year)
