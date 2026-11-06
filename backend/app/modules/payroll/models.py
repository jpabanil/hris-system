from __future__ import annotations

from datetime import date, datetime
from typing import Any

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, SoftMixin, TenantMixin


class PayGroup(AuditMixin, TenantMixin, SoftMixin, Document):
    name: str
    frequency: str
    cutoff_rules: dict[str, Any] = Field(default_factory=dict)
    pay_day_rules: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "pay_groups"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class PayrollPeriod(AuditMixin, TenantMixin, Document):
    pay_group_id: str
    start: date
    end: date
    attendance_cutoff: date
    pay_date: date
    type: str = "regular"
    status: str = "draft"
    period_index: int = 1
    periods_in_month: int = 1

    class Settings:
        name = "payroll_periods"
        indexes = [IndexModel([("company_id", 1), ("pay_group_id", 1), ("start", 1)])]


class PayrollRun(AuditMixin, TenantMixin, Document):
    period_id: str
    version: int = 1
    computed_by: str | None = None
    computed_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    progress_done: int = 0
    progress_total: int = 0
    notes: str = ""
    status: str = "draft"

    class Settings:
        name = "payroll_runs"
        indexes = [IndexModel([("company_id", 1), ("period_id", 1)])]


class PayslipLine(BaseModel):
    type: str
    code: str
    label: str
    quantity: MoneyField = "0"
    rate: MoneyField = "0"
    amount: MoneyField
    is_taxable: bool = False
    deferred: bool = False
    cost_center_id: str | None = None
    ref_id: str | None = None


class Payslip(AuditMixin, TenantMixin, Document):
    run_id: str
    period_id: str
    employee_id: str
    basic_pay: MoneyField
    gross: MoneyField
    taxable_income: MoneyField
    non_taxable_income: MoneyField
    withholding_tax: MoneyField
    total_deductions: MoneyField
    net_pay: MoneyField
    lines: list[PayslipLine] = Field(default_factory=list)
    ytd: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    is_published: bool = False
    emailed_at: datetime | None = None
    viewed_at: datetime | None = None
    has_deferrals: bool = False

    class Settings:
        name = "payslips"
        indexes = [IndexModel([("run_id", 1), ("employee_id", 1)], unique=True)]


class ContributionBracket(BaseModel):
    range_from: MoneyField
    range_to: MoneyField
    ee: MoneyField
    er: MoneyField
    ec: MoneyField = "0"
    mpf: MoneyField = "0"
    mpf_er: MoneyField = "0"


class ContributionTable(AuditMixin, TenantMixin, Document):
    agency: str
    effective_from: date
    effective_to: date | None = None
    brackets: list[ContributionBracket] = Field(default_factory=list)

    class Settings:
        name = "contribution_tables"
        indexes = [IndexModel([("company_id", 1), ("agency", 1), ("effective_from", -1)])]


class TaxBracketRow(BaseModel):
    start: MoneyField
    base_tax: MoneyField
    rate: MoneyField


class TaxTable(AuditMixin, TenantMixin, Document):
    effective_from: date
    frequency: str
    brackets: list[TaxBracketRow] = Field(default_factory=list)

    class Settings:
        name = "tax_tables"
        indexes = [IndexModel([("company_id", 1), ("frequency", 1), ("effective_from", -1)])]


class Loan(AuditMixin, TenantMixin, Document):
    employee_id: str
    type: str
    reference_no: str = ""
    principal: MoneyField
    amortization: MoneyField
    balance: MoneyField
    start_period_id: str | None = None
    end_period_id: str | None = None
    status: str = "active"
    can_pause: bool = False

    class Settings:
        name = "loans"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("status", 1)])]


class LoanPayment(TenantMixin, Document):
    loan_id: str
    payslip_id: str
    amount: MoneyField
    at: datetime

    class Settings:
        name = "loan_payments"
        indexes = [IndexModel([("company_id", 1), ("loan_id", 1)])]


class RecurringDeduction(AuditMixin, TenantMixin, Document):
    employee_id: str
    type: str
    label: str = ""
    amount: MoneyField
    frequency: str = "every_period"
    until: date | None = None

    class Settings:
        name = "recurring_deductions"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class Adjustment(AuditMixin, TenantMixin, Document):
    employee_id: str
    period_id: str
    type: str
    label: str
    amount: MoneyField
    is_taxable: bool = True
    approval_request_id: str | None = None

    class Settings:
        name = "adjustments"
        indexes = [IndexModel([("company_id", 1), ("period_id", 1)])]


class RetroAdjustment(AuditMixin, TenantMixin, Document):
    employee_id: str
    period_id: str
    amount: MoneyField
    reason: str = ""

    class Settings:
        name = "retro_adjustments"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class YtdOpening(TenantMixin, Document):
    employee_id: str
    year: int
    gross: MoneyField = "0"
    taxable: MoneyField = "0"
    non_taxable: MoneyField = "0"
    contributions: MoneyField = "0"
    tax_withheld: MoneyField = "0"
    thirteenth_and_other_benefits: MoneyField = "0"
    basic: MoneyField = "0"

    class Settings:
        name = "ytd_openings"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("year", 1)], unique=True)]


class PreviousEmployerIncome(TenantMixin, Document):
    employee_id: str
    year: int
    taxable: MoneyField = "0"
    tax_withheld: MoneyField = "0"
    non_taxable: MoneyField = "0"

    class Settings:
        name = "previous_employer_income"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("year", 1)], unique=True)]
