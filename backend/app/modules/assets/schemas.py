"""Request bodies for assets and assignments. Cost is Decimal, never float."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.money import money


def parse_money(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("float is not allowed")
    try:
        return money(value)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValueError("invalid amount") from exc


class AssetWrite(BaseModel):
    tag: str
    name: str
    serial_no: str = ""
    category_id: str | None = None
    purchase_date: date | None = None
    cost: Decimal = Field(default_factory=lambda: Decimal("0"))
    status: str = "available"

    @field_validator("cost", mode="before")
    @classmethod
    def _money(cls, value: object) -> Decimal:
        if value is None:
            return Decimal("0")
        return parse_money(value)


class AssignmentCreate(BaseModel):
    asset_id: str
    employee_id: str
    issued_at: datetime | None = None
    condition_out: str = ""
    acknowledgment_key: str | None = None


class AssignmentUpdate(BaseModel):
    condition_out: str | None = None
    condition_in: str | None = None
    acknowledgment_key: str | None = None


class AssignmentReturn(BaseModel):
    returned_at: datetime | None = None
    condition_in: str = ""
