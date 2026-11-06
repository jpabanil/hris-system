"""Monthly leave accrual, carry expiry, and the January year-end close."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.modules.leave.service import (
    close_leave_year,
    expire_carried_leave,
)
from app.modules.leave.service import (
    run_monthly_accrual as _run_monthly_accrual,
)
from app.modules.organization.models import Company


async def run_monthly_accrual() -> None:
    await _run_monthly_accrual()
    await expire_carried_leave()
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    if today.month != 1:
        return
    companies = await Company.find({"deleted_at": None, "is_active": True}).to_list()
    for company in companies:
        await close_leave_year(str(company.id), today.year - 1)
