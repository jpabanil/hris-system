from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

from app.modules.recruitment.policies import parse_money_input, parse_optional_money

MoneyInput = Annotated[str, BeforeValidator(parse_money_input)]
OptionalMoney = Annotated[str | None, BeforeValidator(parse_optional_money)]


class RequisitionWrite(BaseModel):
    department_id: str
    position_id: str
    headcount: int = 1
    reason: str = "new"
    replaced_employee_id: str | None = None
    budget: MoneyInput = "0"
    target_start: date | None = None


class OpeningWrite(BaseModel):
    requisition_id: str | None = None
    title: str
    description: str = ""
    requirements: str = ""
    employment_type: str = "regular"
    location: str = ""
    salary_min: OptionalMoney = None
    salary_max: OptionalMoney = None
    salary_visible: bool = False
    is_public: bool = True
    status: str = "open"
    closes_at: date | None = None


class ApplicantWrite(BaseModel):
    job_opening_id: str
    name: str
    email: str
    mobile: str = ""
    resume_key: str | None = None
    source: str = ""
    referred_by_employee_id: str | None = None
    stage: str = "applied"
    rating: int | None = None


class PublicApplication(BaseModel):
    name: str
    email: str
    mobile: str = ""
    resume_key: str | None = None
    source: str = "public"


class StageWrite(BaseModel):
    stage: str
    note: str = ""


class ScorecardWrite(BaseModel):
    criteria: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    interviewer_id: str | None = None


class OfferWrite(BaseModel):
    applicant_id: str
    salary: MoneyInput
    start_date: date
    generated_document_id: str | None = None
    status: str = "draft"
