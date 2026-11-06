from __future__ import annotations

from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, TenantMixin


class SavedReport(AuditMixin, TenantMixin, Document):
    report: str
    name: str
    filters: dict[str, Any] = Field(default_factory=dict)
    schedule: str = ""

    class Settings:
        name = "saved_reports"
        indexes = [IndexModel([("company_id", 1), ("report", 1)])]


class ExportJob(AuditMixin, TenantMixin, Document):
    report: str
    status: str = "pending"
    file_key: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "export_jobs"
        indexes = [IndexModel([("company_id", 1), ("status", 1)])]
