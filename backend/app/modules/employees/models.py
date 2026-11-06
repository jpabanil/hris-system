"""Employee 201 file. Sensitive identifiers live in a separate collection."""

from __future__ import annotations

from datetime import date
from typing import Any

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, RevisionMixin, SoftMixin, TenantMixin


class PersonName(BaseModel):
    first: str
    middle: str = ""
    last: str
    suffix: str = ""
    nickname: str = ""

    @property
    def full_name(self) -> str:
        parts = [self.first, self.middle, self.last, self.suffix]
        return " ".join(part for part in parts if part).strip()


class CompensationSnapshot(BaseModel):
    basic_salary: MoneyField
    pay_basis: str
    daily_rate: MoneyField
    hourly_rate: MoneyField


class Employee(AuditMixin, TenantMixin, SoftMixin, RevisionMixin, Document):
    user_id: str | None = None
    employee_no: str
    name: PersonName
    birth_date: date | None = None
    birth_place: str = ""
    gender: str = ""
    civil_status: str = ""
    nationality: str = "Filipino"
    blood_type: str = ""
    contact: dict[str, Any] = Field(default_factory=dict)
    present_address: str = ""
    permanent_address: str = ""
    branch_id: str | None = None
    department_id: str | None = None
    position_id: str | None = None
    cost_center_id: str | None = None
    reports_to: str | None = None
    manager_chain: list[str] = Field(default_factory=list)
    pay_group_id: str | None = None
    employment_type: str = "regular"
    employment_status: str = "active"
    date_hired: date | None = None
    probation_end_date: date | None = None
    regularization_date: date | None = None
    contract_end_date: date | None = None
    separation_date: date | None = None
    separation_reason: str = ""
    is_minimum_wage_earner: bool = False
    photo_key: str | None = None
    signature_key: str | None = None
    emergency_contacts: list[dict[str, Any]] = Field(default_factory=list)
    dependents: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    work_history: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    licenses: list[dict[str, Any]] = Field(default_factory=list)
    current_compensation: CompensationSnapshot | None = None

    class Settings:
        name = "employees"
        indexes = [
            IndexModel([("company_id", 1), ("employee_no", 1)], unique=True),
            IndexModel([("company_id", 1), ("department_id", 1)]),
            IndexModel([("company_id", 1), ("manager_chain", 1)]),
        ]


class EmployeeSensitive(TenantMixin, Document):
    employee_id: str
    tin: str = ""
    sss_no: str = ""
    philhealth_no: str = ""
    pagibig_no: str = ""
    bank_accounts: list[dict[str, Any]] = Field(default_factory=list)

    class Settings:
        name = "employee_sensitive"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)], unique=True)]


class CompensationHistory(AuditMixin, TenantMixin, Document):
    employee_id: str
    basic_salary: MoneyField
    pay_basis: str
    daily_rate: MoneyField
    hourly_rate: MoneyField
    factor_days_per_year: int = 261
    effective_date: date
    reason: str = ""
    approval_request_id: str | None = None

    class Settings:
        name = "compensation_history"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("effective_date", -1)])]


class AllowanceType(AuditMixin, TenantMixin, SoftMixin, Document):
    code: str
    name: str
    default_taxability: str = "taxable"
    de_minimis_category: str | None = None
    annual_ceiling: MoneyField | None = None

    class Settings:
        name = "allowance_types"
        indexes = [IndexModel([("company_id", 1), ("code", 1)], unique=True)]


class EmployeeAllowance(AuditMixin, TenantMixin, Document):
    employee_id: str
    allowance_type_id: str
    amount: MoneyField
    taxability: str = "taxable"
    frequency: str = "every_period"
    prorate_on_absence: bool = False
    effective_from: date
    effective_to: date | None = None

    class Settings:
        name = "employee_allowances"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class EmployeeDocument(AuditMixin, TenantMixin, SoftMixin, Document):
    employee_id: str
    document_type: str
    file_key: str
    expires_at: date | None = None
    is_confidential: bool = False

    class Settings:
        name = "employee_documents"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class EmployeeMovement(AuditMixin, TenantMixin, Document):
    employee_id: str
    type: str
    from_value: dict[str, Any] = Field(default_factory=dict)
    to_value: dict[str, Any] = Field(default_factory=dict)
    effective_date: date
    approval_request_id: str | None = None

    class Settings:
        name = "employee_movements"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("effective_date", -1)])]


class ProfileUpdateRequest(AuditMixin, TenantMixin, Document):
    employee_id: str
    changes: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    approval_request_id: str | None = None

    class Settings:
        name = "profile_update_requests"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("status", 1)])]
