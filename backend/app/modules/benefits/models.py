from __future__ import annotations

from datetime import date

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, SoftMixin, TenantMixin


class BenefitPlan(AuditMixin, TenantMixin, SoftMixin, Document):
    type: str
    provider: str
    plan_name: str
    coverage: str = ""
    employer_share: MoneyField = "0"
    employee_share: MoneyField = "0"
    dependent_cost: MoneyField = "0"

    class Settings:
        name = "benefit_plans"
        indexes = [IndexModel([("company_id", 1), ("plan_name", 1)])]


class BenefitEnrollment(AuditMixin, TenantMixin, Document):
    employee_id: str
    plan_id: str
    covered_dependents: list[str] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None
    card_no: str = ""
    status: str = "active"

    class Settings:
        name = "benefit_enrollments"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]
