"""Payroll request bodies. Money fields reject floats."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.money import Money

_ZERO = Decimal("0.00")


class PayGroupWrite(BaseModel):
    name: str
    frequency: str
    cutoff_rules: dict[str, Any] = Field(default_factory=dict)
    pay_day_rules: dict[str, Any] = Field(default_factory=dict)


class PayrollPeriodWrite(BaseModel):
    pay_group_id: str
    start: date
    end: date
    attendance_cutoff: date
    pay_date: date
    type: str = "regular"
    period_index: int = 1
    periods_in_month: int = 1


class LoanWrite(BaseModel):
    employee_id: str
    type: str
    reference_no: str = ""
    principal: Money
    amortization: Money
    balance: Money | None = None
    start_period_id: str | None = None
    end_period_id: str | None = None
    status: str = "active"
    can_pause: bool = False


class RecurringDeductionWrite(BaseModel):
    employee_id: str
    type: str
    label: str = ""
    amount: Money
    frequency: str = "every_period"
    until: date | None = None


class AdjustmentWrite(BaseModel):
    employee_id: str
    period_id: str
    type: str
    label: str
    amount: Money
    is_taxable: bool = True
    approval_request_id: str | None = None


class ContributionBracketWrite(BaseModel):
    range_from: Money
    range_to: Money
    ee: Money
    er: Money
    ec: Money = _ZERO
    mpf: Money = _ZERO
    mpf_er: Money = _ZERO


class ContributionTableWrite(BaseModel):
    agency: str
    effective_from: date
    effective_to: date | None = None
    brackets: list[ContributionBracketWrite] = Field(default_factory=list)


class TaxBracketWrite(BaseModel):
    start: Money
    base_tax: Money
    rate: Money


class TaxTableWrite(BaseModel):
    effective_from: date
    frequency: str
    brackets: list[TaxBracketWrite] = Field(default_factory=list)
