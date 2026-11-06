from __future__ import annotations

from datetime import date, datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, SoftMixin, TenantMixin


class Offense(AuditMixin, TenantMixin, SoftMixin, Document):
    offense: str
    category: str = ""
    sanctions_by_count: list[str] = Field(default_factory=list)

    class Settings:
        name = "offenses"
        indexes = [IndexModel([("company_id", 1), ("offense", 1)])]


class IncidentReport(AuditMixin, TenantMixin, Document):
    reported_by: str
    employee_id: str
    date: date
    description: str
    attachment_keys: list[str] = Field(default_factory=list)

    class Settings:
        name = "incident_reports"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class DisciplinaryCase(AuditMixin, TenantMixin, Document):
    employee_id: str
    incident_report_id: str | None = None
    offense_id: str | None = None
    case_no: str
    status: str = "open"
    events: list[dict[str, Any]] = Field(default_factory=list)
    sanction_type: str = ""
    suspension_days: int = 0
    details: str = ""

    class Settings:
        name = "disciplinary_cases"
        indexes = [IndexModel([("company_id", 1), ("case_no", 1)], unique=True)]


class Grievance(AuditMixin, TenantMixin, Document):
    submitted_by: str | None = None
    anonymous: bool = False
    category: str
    assigned_to: str | None = None
    status: str = "open"
    description: str = ""
    resolution: str = ""

    class Settings:
        name = "grievances"
        indexes = [IndexModel([("company_id", 1), ("status", 1)])]


class Policy(AuditMixin, TenantMixin, SoftMixin, Document):
    title: str
    version: int = 1
    file_key: str | None = None
    body: str = ""
    requires_acknowledgment: bool = True
    effective_date: date | None = None

    class Settings:
        name = "policies"
        indexes = [IndexModel([("company_id", 1), ("title", 1), ("version", 1)], unique=True)]


class PolicyAcknowledgment(TenantMixin, Document):
    policy_id: str
    version: int
    employee_id: str
    acknowledged_at: datetime
    ip: str | None = None

    class Settings:
        name = "policy_acknowledgments"
        indexes = [IndexModel([("policy_id", 1), ("employee_id", 1), ("version", 1)], unique=True)]
