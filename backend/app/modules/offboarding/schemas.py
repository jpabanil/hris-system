from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

from app.modules.offboarding.policies import parse_money_input, parse_optional_money

MoneyInput = Annotated[str, BeforeValidator(parse_money_input)]
OptionalMoney = Annotated[str | None, BeforeValidator(parse_optional_money)]


class ResignationWrite(BaseModel):
    employee_id: str
    filed_at: date
    last_working_day: date
    reason: str = ""


class ExitInterviewWrite(BaseModel):
    employee_id: str
    answers: list[dict[str, Any]] = Field(default_factory=list)


class ClearancePatch(BaseModel):
    remarks: str | None = None


class FinalPayRequest(BaseModel):
    unpaid_salary: OptionalMoney = None
    remaining_days: int | None = None
    leave_conversion: MoneyInput = "0"
    annualization_refund_or_payable: MoneyInput = "0"
