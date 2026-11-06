"""Benefit request bodies."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.money import Money

_ZERO = Decimal("0.00")


class BenefitPlanWrite(BaseModel):
    type: str
    provider: str
    plan_name: str
    coverage: str = ""
    employer_share: Money = _ZERO
    employee_share: Money = _ZERO
    dependent_cost: Money = _ZERO


class BenefitEnrollmentWrite(BaseModel):
    employee_id: str
    plan_id: str
    covered_dependents: list[str] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None
    card_no: str = ""
    status: str = "active"
