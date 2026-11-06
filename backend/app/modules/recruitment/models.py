from __future__ import annotations

from datetime import date, datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, SoftMixin, TenantMixin


class ManpowerRequisition(AuditMixin, TenantMixin, Document):
    department_id: str
    position_id: str
    headcount: int = 1
    reason: str = "new"
    replaced_employee_id: str | None = None
    budget: MoneyField = "0"
    target_start: date | None = None
    status: str = "pending"
    approval_request_id: str | None = None

    class Settings:
        name = "manpower_requisitions"
        indexes = [IndexModel([("company_id", 1), ("status", 1)])]


class JobOpening(AuditMixin, TenantMixin, SoftMixin, Document):
    requisition_id: str | None = None
    title: str
    description: str = ""
    requirements: str = ""
    employment_type: str = "regular"
    location: str = ""
    salary_min: MoneyField | None = None
    salary_max: MoneyField | None = None
    salary_visible: bool = False
    is_public: bool = True
    status: str = "open"
    closes_at: date | None = None

    class Settings:
        name = "job_openings"
        indexes = [IndexModel([("company_id", 1), ("status", 1), ("is_public", 1)])]


class Applicant(AuditMixin, TenantMixin, Document):
    job_opening_id: str
    name: str
    email: str
    mobile: str = ""
    resume_key: str | None = None
    source: str = ""
    referred_by_employee_id: str | None = None
    stage: str = "applied"
    rating: int | None = None
    consent_given_at: datetime | None = None
    activities: list[dict[str, Any]] = Field(default_factory=list)
    scorecards: list[dict[str, Any]] = Field(default_factory=list)

    class Settings:
        name = "applicants"
        indexes = [IndexModel([("company_id", 1), ("job_opening_id", 1), ("stage", 1)])]


class JobOffer(AuditMixin, TenantMixin, Document):
    applicant_id: str
    salary: MoneyField
    start_date: date
    generated_document_id: str | None = None
    status: str = "draft"

    class Settings:
        name = "job_offers"
        indexes = [IndexModel([("company_id", 1), ("applicant_id", 1)])]
