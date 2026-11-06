from __future__ import annotations

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, RevisionMixin, SoftMixin, TenantMixin


class GeoFence(BaseModel):
    lat: float
    lng: float
    radius_m: int = 150


class Company(AuditMixin, SoftMixin, RevisionMixin, Document):
    name: str
    slug: str
    trade_name: str = ""
    tin: str = ""
    rdo_code: str = ""
    sss_employer_no: str = ""
    philhealth_employer_no: str = ""
    pagibig_employer_no: str = ""
    address: str = ""
    zip: str = ""
    timezone: str = "Asia/Manila"
    currency: str = "PHP"
    logo_key: str | None = None
    is_active: bool = True

    class Settings:
        name = "companies"
        indexes = [IndexModel([("slug", 1)], unique=True)]


class Branch(AuditMixin, TenantMixin, SoftMixin, RevisionMixin, Document):
    name: str
    address: str = ""
    city: str = ""
    region: str = ""
    geofence: GeoFence | None = None

    class Settings:
        name = "branches"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class Department(AuditMixin, TenantMixin, SoftMixin, RevisionMixin, Document):
    name: str
    code: str
    parent_id: str | None = None
    ancestors: list[str] = Field(default_factory=list)
    head_employee_id: str | None = None
    cost_center_id: str | None = None

    class Settings:
        name = "departments"
        indexes = [IndexModel([("company_id", 1), ("code", 1)], unique=True)]


class SalaryGrade(AuditMixin, TenantMixin, SoftMixin, RevisionMixin, Document):
    code: str
    min_salary: MoneyField
    mid_salary: MoneyField
    max_salary: MoneyField

    class Settings:
        name = "salary_grades"
        indexes = [IndexModel([("company_id", 1), ("code", 1)], unique=True)]


class Position(AuditMixin, TenantMixin, SoftMixin, RevisionMixin, Document):
    title: str
    department_id: str | None = None
    job_level: str = ""
    salary_grade_id: str | None = None
    is_supervisory: bool = False
    headcount_budget: int = 0

    class Settings:
        name = "positions"
        indexes = [IndexModel([("company_id", 1), ("title", 1)])]


class CostCenter(AuditMixin, TenantMixin, SoftMixin, RevisionMixin, Document):
    code: str
    name: str

    class Settings:
        name = "cost_centers"
        indexes = [IndexModel([("company_id", 1), ("code", 1)], unique=True)]
