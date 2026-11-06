from __future__ import annotations

from datetime import date as Date
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

from app.modules.training.policies import parse_money_input

MoneyInput = Annotated[str, BeforeValidator(parse_money_input)]


class TrainingWrite(BaseModel):
    title: str
    provider: str = ""
    type: str = "internal"
    date: Date | None = None
    hours: str = "0"
    cost: MoneyInput = "0"


class AttendeeWrite(BaseModel):
    training_id: str
    employee_id: str
    status: str = "enrolled"
    certificate_key: str | None = None


class BondWrite(BaseModel):
    employee_id: str
    training_id: str
    amount: MoneyInput
    bond_until: Date
