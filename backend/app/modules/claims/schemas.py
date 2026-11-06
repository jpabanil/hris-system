"""Claim request bodies."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.core.money import Money


class ClaimTypeWrite(BaseModel):
    name: str
    requires_receipt: bool = True
    monthly_limit: Money | None = None
    taxability: str = "non_taxable"
    gl_account: str = ""


class ClaimWrite(BaseModel):
    employee_id: str
    claim_type_id: str
    date: date
    amount: Money
    description: str = ""
    receipt_keys: list[str] = Field(default_factory=list)
    paid_via: str = "payroll"


class CashAdvanceWrite(BaseModel):
    employee_id: str
    amount: Money
    purpose: str = ""
    balance: Money | None = None
    status: str = "open"


class LiquidationWrite(BaseModel):
    amount: Money
    remarks: str = ""
    at: date | None = None
