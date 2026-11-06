from __future__ import annotations

from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, TenantMixin


class HrTicket(AuditMixin, TenantMixin, Document):
    employee_id: str
    category: str
    subject: str
    body: str
    attachment_keys: list[str] = Field(default_factory=list)
    assigned_to: str | None = None
    priority: str = "normal"
    status: str = "open"
    sla_due: datetime | None = None
    comments: list[dict[str, Any]] = Field(default_factory=list)

    class Settings:
        name = "hr_tickets"
        indexes = [IndexModel([("company_id", 1), ("status", 1), ("sla_due", 1)])]
