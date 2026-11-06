from __future__ import annotations

from datetime import datetime

from beanie import Document
from pymongo import IndexModel

from app.core.models import AuditMixin, TenantMixin


class PrivacyConsent(TenantMixin, Document):
    subject_type: str
    subject_id: str
    purpose: str
    version: str
    given_at: datetime
    withdrawn_at: datetime | None = None

    class Settings:
        name = "privacy_consents"
        indexes = [IndexModel([("company_id", 1), ("subject_type", 1), ("subject_id", 1)])]


class DataSubjectRequest(AuditMixin, TenantMixin, Document):
    type: str
    requester: str
    status: str = "open"
    completed_at: datetime | None = None
    export_key: str | None = None

    class Settings:
        name = "data_subject_requests"
        indexes = [IndexModel([("company_id", 1), ("status", 1)])]


class RetentionPolicy(AuditMixin, TenantMixin, Document):
    record_type: str
    retain_years: int
    action: str = "anonymize"

    class Settings:
        name = "retention_policies"
        indexes = [IndexModel([("company_id", 1), ("record_type", 1)], unique=True)]
