from __future__ import annotations

from pydantic import BaseModel, Field


class CompanyWrite(BaseModel):
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
    revision: int | None = None


class BranchWrite(BaseModel):
    name: str
    address: str = ""
    city: str = ""
    region: str = ""
    geofence_lat: float | None = None
    geofence_lng: float | None = None
    geofence_radius_m: int | None = None
    revision: int | None = None


class DepartmentWrite(BaseModel):
    name: str
    code: str
    parent_id: str | None = None
    head_employee_id: str | None = None
    cost_center_id: str | None = None
    revision: int | None = None


class SalaryGradeWrite(BaseModel):
    code: str
    min_salary: str
    mid_salary: str
    max_salary: str
    revision: int | None = None


class PositionWrite(BaseModel):
    title: str
    department_id: str | None = None
    job_level: str = ""
    salary_grade_id: str | None = None
    is_supervisory: bool = False
    headcount_budget: int = 0
    revision: int | None = None


class CostCenterWrite(BaseModel):
    code: str
    name: str
    revision: int | None = None


class PageMeta(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=100)
