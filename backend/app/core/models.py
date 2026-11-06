"""Shared document fields. Mixins are BaseModels; documents still extend Document."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

from app.core.clock import utcnow
from app.core.money import money


def _money_in(value: object) -> Decimal:
    return money(value)


MoneyField = Annotated[
    Decimal,
    BeforeValidator(_money_in),
    PlainSerializer(lambda value: format(money(value), "f"), return_type=str, when_used="json"),
]


class AuditMixin(BaseModel):
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    created_by: str | None = None
    updated_by: str | None = None


class SoftMixin(BaseModel):
    deleted_at: datetime | None = None


class RevisionMixin(BaseModel):
    revision: int = 1


class TenantMixin(BaseModel):
    company_id: str
