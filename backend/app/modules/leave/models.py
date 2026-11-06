from __future__ import annotations

from datetime import date, datetime

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, SoftMixin, TenantMixin


class TenureTier(BaseModel):
    years_from: int
    days: str


class LeaveType(AuditMixin, TenantMixin, SoftMixin, Document):
    code: str
    name: str
    is_paid: bool = True
    annual_entitlement: str = "0"
    accrual_method: str = "upfront"
    eligibility_after_months: int = 0
    carry_over_max: str = "0"
    carry_over_expiry_months: int = 12
    convertible_to_cash: bool = False
    max_conversion_days: str = "0"
    attachment_required_after_days: str = "0"
    gender_restriction: str = ""
    civil_status_restriction: str = ""
    min_notice_days: int = 0
    allow_negative_balance: bool = False
    counts_weekends: bool = False
    tenure_tiers: list[TenureTier] = Field(default_factory=list)

    class Settings:
        name = "leave_types"
        indexes = [IndexModel([("company_id", 1), ("code", 1)], unique=True)]


class LeaveBalance(TenantMixin, Document):
    employee_id: str
    leave_type_id: str
    year: int
    entitled: str = "0"
    accrued: str = "0"
    used: str = "0"
    carried_over: str = "0"
    adjusted: str = "0"

    class Settings:
        name = "leave_balances"
        indexes = [
            IndexModel(
                [("employee_id", 1), ("leave_type_id", 1), ("year", 1)],
                unique=True,
            )
        ]


class LeaveLedger(TenantMixin, Document):
    employee_id: str
    leave_type_id: str
    year: int
    entry_type: str
    days: str
    ref: str = ""
    at: datetime

    class Settings:
        name = "leave_ledger"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("year", 1)])]


class LeaveRequest(AuditMixin, TenantMixin, Document):
    employee_id: str
    leave_type_id: str
    start_date: date
    end_date: date
    half_day: bool = False
    days: str
    reason: str = ""
    attachment_key: str | None = None
    status: str = "pending"
    approval_request_id: str | None = None

    class Settings:
        name = "leave_requests"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("start_date", 1)])]


class LeaveBlackout(AuditMixin, TenantMixin, SoftMixin, Document):
    department_id: str | None = None
    branch_id: str | None = None
    start_date: date
    end_date: date
    reason: str = ""

    class Settings:
        name = "leave_blackouts"
        indexes = [IndexModel([("company_id", 1), ("start_date", 1)])]


class LeaveLiability(BaseModel):
    """Not a collection. Reports use this shape."""

    amount: MoneyField
    days: str
    note: str = ""
