"""Payslips and attendance logs for the portal and for payroll viewers."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.errors import AppError
from app.core.repository import TenantRepo
from app.modules.attendance.models import AttendanceLog
from app.modules.payroll.models import PayrollPeriod, Payslip


def _company(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def _scope(actor: Actor, *, view: str) -> dict:
    """Company-wide for the view permission, otherwise the signed-in employee."""
    if actor.has(view):
        return {}
    if actor.has("self.service") and actor.employee_id:
        extra = {"employee_id": actor.employee_id}
        if view == "payroll.view":
            extra["is_published"] = True
        return extra
    raise AppError("forbidden", "You do not have access to this action", 403)


async def list_payslips(actor: Actor, page: int, page_size: int) -> dict:
    company_id = _company(actor)
    result = await TenantRepo(Payslip, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields={"created_at"},
        q=None,
        sort="-created_at",
        extra=_scope(actor, view="payroll.view"),
    )
    periods = await PayrollPeriod.find({"company_id": company_id}).to_list()
    pay_dates = {str(period.id): period.pay_date.isoformat() for period in periods}
    for item in result["items"]:
        item["pay_date"] = pay_dates.get(str(item.get("period_id")), "")
    return result


async def list_attendance_logs(actor: Actor, page: int, page_size: int) -> dict:
    _company(actor)
    return await TenantRepo(AttendanceLog, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields={"logged_at"},
        q=None,
        sort="-logged_at",
        extra=_scope(actor, view="attendance.view"),
    )
