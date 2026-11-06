from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.actor import Actor
from app.core.deps import require
from app.modules.reports.schemas import ReportFilters
from app.modules.reports.service import export_report, get_export, report_catalog, run_report

router = APIRouter(tags=["reports"])


def _filters(
    department_id: str | None,
    year: int | None,
    status: str | None,
    employee_id: str | None,
) -> ReportFilters:
    return ReportFilters(
        department_id=department_id,
        year=year,
        status=status,
        employee_id=employee_id,
    )


@router.get("/reports")
async def reports(actor: Actor = Depends(require("reports.view"))) -> dict:
    items = report_catalog()
    return {"items": items, "total": len(items), "page": 1, "page_size": len(items)}


@router.get("/reports/{report}")
async def report_get(
    report: str,
    department_id: str | None = None,
    year: int | None = None,
    status: str | None = None,
    employee_id: str | None = None,
    actor: Actor = Depends(require("reports.view")),
) -> dict:
    filters = _filters(department_id, year, status, employee_id)
    return await run_report(actor, report, filters)


@router.post("/reports/{report}/export", status_code=201)
async def report_export(
    report: str,
    department_id: str | None = None,
    year: int | None = None,
    status: str | None = None,
    employee_id: str | None = None,
    actor: Actor = Depends(require("reports.export")),
) -> dict:
    filters = _filters(department_id, year, status, employee_id)
    return await export_report(actor, report, filters)


@router.get("/exports/{id}")
async def exports_get(id: str, actor: Actor = Depends(require("reports.view"))) -> dict:
    return await get_export(actor, id)
