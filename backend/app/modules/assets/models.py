from __future__ import annotations

from datetime import date, datetime

from beanie import Document
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, SoftMixin, TenantMixin


class AssetCategory(AuditMixin, TenantMixin, SoftMixin, Document):
    name: str

    class Settings:
        name = "asset_categories"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class Asset(AuditMixin, TenantMixin, SoftMixin, Document):
    tag: str
    name: str
    serial_no: str = ""
    category_id: str | None = None
    purchase_date: date | None = None
    cost: MoneyField = "0"
    status: str = "available"

    class Settings:
        name = "assets"
        indexes = [IndexModel([("company_id", 1), ("tag", 1)], unique=True)]


class AssetAssignment(AuditMixin, TenantMixin, Document):
    asset_id: str
    employee_id: str
    issued_at: datetime
    returned_at: datetime | None = None
    condition_out: str = ""
    condition_in: str = ""
    acknowledgment_key: str | None = None

    class Settings:
        name = "asset_assignments"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("returned_at", 1)])]
