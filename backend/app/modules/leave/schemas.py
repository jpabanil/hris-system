from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class TenureTierWrite(BaseModel):
    years_from: int = Field(ge=0)
    days: str


class LeaveTypeWrite(BaseModel):
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
    tenure_tiers: list[TenureTierWrite] = Field(default_factory=list)


class LeaveBlackoutWrite(BaseModel):
    department_id: str | None = None
    branch_id: str | None = None
    start_date: date
    end_date: date
    reason: str = ""


class LeaveRequestCreate(BaseModel):
    employee_id: str | None = None
    leave_type_id: str
    start_date: date
    end_date: date
    half_day: bool = False
    reason: str = ""
    attachment_key: str | None = None


class BalanceAdjust(BaseModel):
    employee_id: str
    leave_type_id: str
    year: int = Field(ge=2000, le=2100)
    days: str
    reason: str = ""
