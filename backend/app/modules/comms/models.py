from __future__ import annotations

from datetime import datetime

from beanie import Document
from pymongo import IndexModel

from app.core.models import AuditMixin, SoftMixin, TenantMixin


class Announcement(AuditMixin, TenantMixin, SoftMixin, Document):
    title: str
    body: str
    audience: str = "all"
    audience_id: str | None = None
    pinned: bool = False
    publish_at: datetime | None = None
    expire_at: datetime | None = None

    class Settings:
        name = "announcements"
        indexes = [IndexModel([("company_id", 1), ("publish_at", -1)])]


class AnnouncementRead(TenantMixin, Document):
    announcement_id: str
    user_id: str
    read_at: datetime

    class Settings:
        name = "announcement_reads"
        indexes = [IndexModel([("announcement_id", 1), ("user_id", 1)], unique=True)]
