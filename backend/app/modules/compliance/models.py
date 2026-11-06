from __future__ import annotations

from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, TenantMixin


class TaxAnnualization(AuditMixin, TenantMixin, Document):
    employee_id: str
    year: int
    annual_taxable: MoneyField
    annual_tax_due: MoneyField
    total_withheld: MoneyField
    refund_or_payable: MoneyField
    applied_in_period_id: str | None = None

    class Settings:
        name = "tax_annualizations"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("year", 1)], unique=True)]


class Bir2316(AuditMixin, TenantMixin, Document):
    employee_id: str
    year: int
    data: dict[str, Any] = Field(default_factory=dict)
    file_key: str | None = None

    class Settings:
        name = "bir_2316"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("year", 1)], unique=True)]


class AlphalistExport(AuditMixin, TenantMixin, Document):
    year: int
    type: str
    file_key: str

    class Settings:
        name = "alphalist_exports"
        indexes = [IndexModel([("company_id", 1), ("year", 1)])]


class Remittance(AuditMixin, TenantMixin, Document):
    agency: str
    month: str
    ee_total: MoneyField
    er_total: MoneyField
    reference_no: str = ""
    paid_at: datetime | None = None
    proof_key: str | None = None

    class Settings:
        name = "remittances"
        indexes = [IndexModel([("company_id", 1), ("agency", 1), ("month", 1)], unique=True)]


class ThirteenthMonthRun(AuditMixin, TenantMixin, Document):
    year: int
    status: str = "draft"
    total: MoneyField = "0"
    computed_at: datetime | None = None

    class Settings:
        name = "thirteenth_month_runs"
        indexes = [IndexModel([("company_id", 1), ("year", 1)], unique=True)]


class ThirteenthMonthLine(AuditMixin, TenantMixin, Document):
    run_id: str
    employee_id: str
    basic_earned: MoneyField
    amount: MoneyField
    taxable_excess: MoneyField = "0"

    class Settings:
        name = "thirteenth_month_lines"
        indexes = [IndexModel([("company_id", 1), ("run_id", 1), ("employee_id", 1)], unique=True)]
