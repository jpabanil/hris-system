from __future__ import annotations

from datetime import date

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, SoftMixin, TenantMixin


class ClaimType(AuditMixin, TenantMixin, SoftMixin, Document):
    name: str
    requires_receipt: bool = True
    monthly_limit: MoneyField | None = None
    taxability: str = "non_taxable"
    gl_account: str = ""

    class Settings:
        name = "claim_types"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class Claim(AuditMixin, TenantMixin, Document):
    employee_id: str
    claim_type_id: str
    date: date
    amount: MoneyField
    description: str = ""
    receipt_keys: list[str] = Field(default_factory=list)
    status: str = "pending"
    paid_via: str = "payroll"
    period_id: str | None = None
    approval_request_id: str | None = None

    class Settings:
        name = "claims"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("status", 1)])]


class CashAdvance(AuditMixin, TenantMixin, Document):
    employee_id: str
    amount: MoneyField
    purpose: str = ""
    liquidations: list[dict] = Field(default_factory=list)
    balance: MoneyField
    status: str = "open"

    class Settings:
        name = "cash_advances"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("status", 1)])]
