"""Remittance request bodies."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.money import Money


class RemittanceWrite(BaseModel):
    agency: str
    month: str
    ee_total: Money
    er_total: Money
    reference_no: str = ""
    paid_at: datetime | None = None
    proof_key: str | None = None
