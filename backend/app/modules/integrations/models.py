from __future__ import annotations

from datetime import datetime

from beanie import Document
from pymongo import IndexModel

from app.core.models import AuditMixin, TenantMixin


class Webhook(AuditMixin, TenantMixin, Document):
    event: str
    url: str
    secret: str
    is_active: bool = True

    class Settings:
        name = "webhooks"
        indexes = [IndexModel([("company_id", 1), ("event", 1)])]


class WebhookDelivery(TenantMixin, Document):
    webhook_id: str
    event: str
    status: str = "pending"
    attempts: int = 0
    response: str = ""
    created_at: datetime

    class Settings:
        name = "webhook_deliveries"
        indexes = [IndexModel([("company_id", 1), ("webhook_id", 1), ("created_at", -1)])]
