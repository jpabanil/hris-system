"""Company-scoped reports and Excel exports."""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openpyxl import Workbook

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.money import money
from app.core.repository import api
from app.modules.attendance.models import AttendanceDay
from app.modules.employee_relations.models import DisciplinaryCase, PolicyAcknowledgment
from app.modules.employees.models import Employee
from app.modules.leave.models import LeaveBalance
from app.modules.payroll.models import Payslip
from app.modules.recruitment.models import Applicant
from app.modules.reports import policies
from app.modules.reports.models import ExportJob
from app.modules.reports.schemas import ReportFilters
from app.shared.files import save_upload


def _cell(value: object) -> str | int | bool:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(money(value), "f")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return str(value)


def _filters(raw: ReportFilters) -> ReportFilters:
    return ReportFilters(
        department_id=policies.safe_token(raw.department_id),
        year=raw.year,
        status=policies.safe_token(raw.status),
        employee_id=policies.safe_token(raw.employee_id),
    )


async def headcount(company: str, filters: ReportFilters) -> dict:
    match: dict[str, Any] = {
        "company_id": company,
        "deleted_at": None,
        "employment_status": "active",
    }
    if filters.department_id:
        match["department_id"] = filters.department_id
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "department_id": "$department_id",
                    "employment_type": "$employment_type",
                    "gender": "$gender",
                },
                "headcount": {"$sum": 1},
            }
        },
        {"$sort": {"headcount": -1}},
        {"$limit": 5000},
    ]
    raw = await Employee.aggregate(pipeline).to_list()
    columns = ["department_id", "employment_type", "gender", "headcount"]
    rows = []
    for item in raw:
        key = item.get("_id") or {}
        rows.append(
            {
                "department_id": key.get("department_id") or "",
                "employment_type": key.get("employment_type") or "",
                "gender": key.get("gender") or "",
                "headcount": int(item.get("headcount") or 0),
            }
        )
    return {"columns": columns, "rows": rows}


async def masterlist(company: str, filters: ReportFilters) -> dict:
    query: dict[str, Any] = {"company_id": company, "deleted_at": None}
    if filters.department_id:
        query["department_id"] = filters.department_id
    if filters.status:
        query["employment_status"] = filters.status
    if filters.employee_id:
        one = await Employee.get(filters.employee_id)
        matches = (
            one is not None
            and one.company_id == company
            and one.deleted_at is None
            and (not filters.department_id or one.department_id == filters.department_id)
            and (not filters.status or one.employment_status == filters.status)
        )
        employees = [one] if matches and one is not None else []
    else:
        employees = await Employee.find(query).limit(5000).to_list()
    columns = [
        "employee_no",
        "first_name",
        "last_name",
        "department_id",
        "position_id",
        "employment_type",
        "employment_status",
        "date_hired",
    ]
    rows = [
        {
            "employee_no": employee.employee_no,
            "first_name": employee.name.first,
            "last_name": employee.name.last,
            "department_id": employee.department_id or "",
            "position_id": employee.position_id or "",
            "employment_type": employee.employment_type,
            "employment_status": employee.employment_status,
            "date_hired": employee.date_hired.isoformat() if employee.date_hired else "",
        }
        for employee in employees
    ]
    return {"columns": columns, "rows": rows}


async def attendance_summary(company: str, filters: ReportFilters) -> dict:
    match: dict[str, Any] = {"company_id": company}
    if filters.employee_id:
        match["employee_id"] = filters.employee_id
    if filters.year:
        match["date"] = {
            "$gte": datetime(filters.year, 1, 1),
            "$lte": datetime(filters.year, 12, 31, 23, 59, 59),
        }
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": "$employee_id",
                "days": {"$sum": 1},
                "late_minutes": {"$sum": "$late_minutes"},
                "undertime_minutes": {"$sum": "$undertime_minutes"},
                "overtime_minutes": {"$sum": "$overtime_minutes"},
                "absences": {"$sum": {"$cond": [{"$eq": ["$status", "absent"]}, 1, 0]}},
            }
        },
        {"$limit": 5000},
    ]
    raw = await AttendanceDay.aggregate(pipeline).to_list()
    columns = [
        "employee_id",
        "days",
        "late_minutes",
        "undertime_minutes",
        "overtime_minutes",
        "absences",
    ]
    rows = [
        {
            "employee_id": item.get("_id") or "",
            "days": int(item.get("days") or 0),
            "late_minutes": int(item.get("late_minutes") or 0),
            "undertime_minutes": int(item.get("undertime_minutes") or 0),
            "overtime_minutes": int(item.get("overtime_minutes") or 0),
            "absences": int(item.get("absences") or 0),
        }
        for item in raw
    ]
    return {"columns": columns, "rows": rows}


async def leave_balances(company: str, filters: ReportFilters) -> dict:
    query: dict[str, Any] = {"company_id": company}
    if filters.year:
        query["year"] = filters.year
    if filters.employee_id:
        query["employee_id"] = filters.employee_id
    rows_src = await LeaveBalance.find(query).limit(5000).to_list()
    columns = [
        "employee_id",
        "leave_type_id",
        "year",
        "entitled",
        "accrued",
        "used",
        "carried_over",
        "adjusted",
    ]
    rows = [
        {
            "employee_id": row.employee_id,
            "leave_type_id": row.leave_type_id,
            "year": row.year,
            "entitled": row.entitled,
            "accrued": row.accrued,
            "used": row.used,
            "carried_over": row.carried_over,
            "adjusted": row.adjusted,
        }
        for row in rows_src
    ]
    return {"columns": columns, "rows": rows}


async def payroll_register(company: str, filters: ReportFilters) -> dict:
    query: dict[str, Any] = {"company_id": company}
    if filters.employee_id:
        query["employee_id"] = filters.employee_id
    slips = await Payslip.find(query).limit(5000).to_list()
    columns = [
        "employee_id",
        "period_id",
        "basic_pay",
        "gross",
        "withholding_tax",
        "total_deductions",
        "net_pay",
    ]
    rows = []
    for slip in slips:
        if filters.year and slip.created_at.year != filters.year:
            continue
        rows.append(
            {
                "employee_id": slip.employee_id,
                "period_id": slip.period_id,
                "basic_pay": format(money(slip.basic_pay), "f"),
                "gross": format(money(slip.gross), "f"),
                "withholding_tax": format(money(slip.withholding_tax), "f"),
                "total_deductions": format(money(slip.total_deductions), "f"),
                "net_pay": format(money(slip.net_pay), "f"),
            }
        )
    return {"columns": columns, "rows": rows}


async def recruitment_funnel(company: str, filters: ReportFilters) -> dict:
    match: dict[str, Any] = {"company_id": company}
    if filters.status:
        match["stage"] = filters.status
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$stage", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    raw = await Applicant.aggregate(pipeline).to_list()
    columns = ["stage", "count"]
    rows = [{"stage": item.get("_id") or "", "count": int(item.get("count") or 0)} for item in raw]
    return {"columns": columns, "rows": rows}


async def disciplinary_cases(company: str, filters: ReportFilters) -> dict:
    query: dict[str, Any] = {"company_id": company}
    if filters.status:
        query["status"] = filters.status
    if filters.employee_id:
        query["employee_id"] = filters.employee_id
    cases = await DisciplinaryCase.find(query).limit(5000).to_list()
    columns = ["case_no", "employee_id", "status", "sanction_type", "suspension_days"]
    rows = [
        {
            "case_no": case.case_no,
            "employee_id": case.employee_id,
            "status": case.status,
            "sanction_type": case.sanction_type,
            "suspension_days": case.suspension_days,
        }
        for case in cases
    ]
    return {"columns": columns, "rows": rows}


async def policy_acknowledgments(company: str, filters: ReportFilters) -> dict:
    query: dict[str, Any] = {"company_id": company}
    if filters.employee_id:
        query["employee_id"] = filters.employee_id
    rows_src = await PolicyAcknowledgment.find(query).limit(5000).to_list()
    columns = ["policy_id", "version", "employee_id", "acknowledged_at", "ip"]
    rows = [
        {
            "policy_id": row.policy_id,
            "version": row.version,
            "employee_id": row.employee_id,
            "acknowledged_at": row.acknowledged_at.isoformat(),
            "ip": row.ip or "",
        }
        for row in rows_src
    ]
    return {"columns": columns, "rows": rows}


_RUNNERS = {
    "headcount": headcount,
    "masterlist": masterlist,
    "attendance-summary": attendance_summary,
    "leave-balances": leave_balances,
    "payroll-register": payroll_register,
    "recruitment-funnel": recruitment_funnel,
    "disciplinary-cases": disciplinary_cases,
    "policy-acknowledgments": policy_acknowledgments,
}


def report_catalog() -> list[dict[str, str]]:
    return [{"id": name, "name": name} for name in sorted(_RUNNERS)]


async def run_report(actor: Actor, report: str, filters: ReportFilters) -> dict:
    company = policies.require_view(actor)
    policies.require_known(report)
    runner = _RUNNERS[report]
    return await runner(company, _filters(filters))


def _xlsx(table: dict) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "report"
    columns = list(table["columns"])
    sheet.append(columns)
    for row in table["rows"]:
        sheet.append([_cell(row.get(column)) for column in columns])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


async def export_report(actor: Actor, report: str, filters: ReportFilters) -> dict:
    company = policies.require_export(actor)
    policies.require_known(report)
    cleaned = _filters(filters)
    job = ExportJob(
        company_id=company,
        report=report,
        status="pending",
        filters=cleaned.model_dump(),
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await job.insert()
    try:
        table = await _RUNNERS[report](company, cleaned)
        payload = _xlsx(table)
        stored = await save_upload(
            actor,
            filename=f"{report}.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            data=payload,
        )
    except AppError:
        job.status = "failed"
        job.updated_at = utcnow()
        await job.save()
        raise
    job.status = "done"
    job.file_key = stored.key
    job.updated_at = utcnow()
    job.updated_by = actor.user_id
    await job.save()
    return api(job)


async def get_export(actor: Actor, export_id: str) -> dict:
    company = policies.require_view(actor)
    job = await ExportJob.get(export_id)
    if job is None or job.company_id != company:
        raise AppError("not_found", "Export not found", 404)
    return api(job)
