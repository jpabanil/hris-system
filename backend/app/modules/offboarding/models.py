from __future__ import annotations

from datetime import date, datetime
from typing import Any

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, TenantMixin


class ClearanceItem(BaseModel):
    department: str
    item: str
    cleared_by: str | None = None
    cleared_at: datetime | None = None
    remarks: str = ""
    blocking: bool = False


class Resignation(AuditMixin, TenantMixin, Document):
    employee_id: str
    filed_at: date
    last_working_day: date
    reason: str = ""
    status: str = "pending"
    approval_request_id: str | None = None

    class Settings:
        name = "resignations"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class Clearance(AuditMixin, TenantMixin, Document):
    employee_id: str
    items: list[ClearanceItem] = Field(default_factory=list)
    status: str = "open"

    class Settings:
        name = "clearances"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)], unique=True)]


class ExitInterview(AuditMixin, TenantMixin, Document):
    employee_id: str
    answers: list[dict[str, Any]] = Field(default_factory=list)

    class Settings:
        name = "exit_interviews"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)], unique=True)]


class FinalPay(AuditMixin, TenantMixin, Document):
    employee_id: str
    components: list[dict[str, Any]] = Field(default_factory=list)
    net: MoneyField = "0"
    status: str = "draft"
    target_release_date: date | None = None

    class Settings:
        name = "final_pay"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)], unique=True)]
