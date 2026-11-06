"""Request bodies for the employee API. Money is Decimal, never float."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.money import money


def parse_money(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("float is not allowed")
    try:
        return money(value)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValueError("invalid amount") from exc


class NameWrite(BaseModel):
    first: str
    middle: str = ""
    last: str
    suffix: str = ""
    nickname: str = ""


class BankAccountWrite(BaseModel):
    bank_name: str = ""
    account_name: str = ""
    account_no: str = ""
    is_primary: bool = False


class SensitiveWrite(BaseModel):
    tin: str | None = None
    sss_no: str | None = None
    philhealth_no: str | None = None
    pagibig_no: str | None = None
    bank_accounts: list[BankAccountWrite] | None = None


class EmployeeCreate(BaseModel):
    name: NameWrite
    employee_no: str | None = None
    user_id: str | None = None
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
    sensitive: SensitiveWrite | None = None


class EmployeeUpdate(BaseModel):
    revision: int | None = None
    name: NameWrite | None = None
    employee_no: str | None = None
    user_id: str | None = None
    birth_date: date | None = None
    birth_place: str | None = None
    gender: str | None = None
    civil_status: str | None = None
    nationality: str | None = None
    blood_type: str | None = None
    contact: dict[str, Any] | None = None
    present_address: str | None = None
    permanent_address: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    position_id: str | None = None
    cost_center_id: str | None = None
    reports_to: str | None = None
    pay_group_id: str | None = None
    employment_type: str | None = None
    employment_status: str | None = None
    date_hired: date | None = None
    probation_end_date: date | None = None
    regularization_date: date | None = None
    contract_end_date: date | None = None
    separation_date: date | None = None
    separation_reason: str | None = None
    is_minimum_wage_earner: bool | None = None
    photo_key: str | None = None
    signature_key: str | None = None
    emergency_contacts: list[dict[str, Any]] | None = None
    dependents: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    work_history: list[dict[str, Any]] | None = None
    skills: list[str] | None = None
    licenses: list[dict[str, Any]] | None = None


class CompensationWrite(BaseModel):
    basic_salary: Decimal
    pay_basis: str
    effective_date: date
    reason: str = ""
    approval_request_id: str | None = None

    @field_validator("basic_salary", mode="before")
    @classmethod
    def _money(cls, value: object) -> Decimal:
        return parse_money(value)


class MovementWrite(BaseModel):
    type: str
    from_value: dict[str, Any] = Field(default_factory=dict)
    to_value: dict[str, Any] = Field(default_factory=dict)
    effective_date: date
    approval_request_id: str | None = None


class DocumentWrite(BaseModel):
    document_type: str
    file_key: str
    expires_at: date | None = None
    is_confidential: bool = False


class ProfileUpdateWrite(BaseModel):
    employee_id: str | None = None
    changes: dict[str, Any] = Field(default_factory=dict)


class ProfileUpdateEdit(BaseModel):
    changes: dict[str, Any] = Field(default_factory=dict)
