"""Collections owned by the shared engines."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from beanie import Document, Indexed
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, SoftMixin, TenantMixin


class FlowCondition(BaseModel):
    field: str
    op: str
    value: str


class FlowStep(BaseModel):
    order: int
    approver_type: str
    approver_value: str | None = None
    mode: str = "any"


class ApprovalFlow(AuditMixin, TenantMixin, SoftMixin, Document):
    module: str
    name: str
    conditions: list[FlowCondition] = Field(default_factory=list)
    is_active: bool = True
    steps: list[FlowStep] = Field(default_factory=list)

    class Settings:
        name = "approval_flows"
        indexes = [IndexModel([("company_id", 1), ("module", 1)])]


class ApprovalAction(BaseModel):
    step: int
    actor_id: str
    action: str
    remarks: str = ""
    acted_at: datetime


class ApprovalRequest(AuditMixin, TenantMixin, Document):
    module: str
    subject_type: str
    subject_id: str
    flow_id: str | None = None
    current_step: int = 1
    status: str = "pending"
    requester_id: str
    context: dict[str, Any] = Field(default_factory=dict)
    actions: list[ApprovalAction] = Field(default_factory=list)
    pending_approver_ids: list[str] = Field(default_factory=list)

    class Settings:
        name = "approval_requests"
        indexes = [
            IndexModel([("company_id", 1), ("status", 1)]),
            IndexModel([("company_id", 1), ("subject_type", 1), ("subject_id", 1)]),
        ]


class ApprovalDelegation(AuditMixin, TenantMixin, Document):
    approver_id: str
    delegate_id: str
    starts_on: datetime
    ends_on: datetime

    class Settings:
        name = "approval_delegations"
        indexes = [IndexModel([("company_id", 1), ("approver_id", 1)])]


class AuditLog(Document):
    company_id: str | None = None
    actor_id: str | None = None
    action: str
    entity_type: str
    entity_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip: str | None = None
    user_agent: str | None = None
    at: datetime

    class Settings:
        name = "audit_logs"
        indexes = [IndexModel([("company_id", 1), ("entity_type", 1), ("at", -1)])]


class Counter(Document):
    company_id: Indexed(str)
    key: str
    value: int = 0

    class Settings:
        name = "counters"
        indexes = [IndexModel([("company_id", 1), ("key", 1)], unique=True)]


class SettingDoc(AuditMixin, TenantMixin, Document):
    module: str
    values: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "settings"
        indexes = [IndexModel([("company_id", 1), ("module", 1)], unique=True)]


class IdempotencyKey(Document):
    company_id: str
    actor_id: str
    scope: str
    key: str
    response: dict[str, Any]
    created_at: datetime

    class Settings:
        name = "idempotency_keys"
        indexes = [
            IndexModel([("company_id", 1), ("scope", 1), ("key", 1)], unique=True),
            IndexModel([("created_at", 1)], expireAfterSeconds=60 * 60 * 24),
        ]


class StoredFile(AuditMixin, TenantMixin, Document):
    key: Indexed(str, unique=True)
    filename: str
    content_type: str
    size: int
    confidential: bool = False

    class Settings:
        name = "files"


class DocumentTemplate(AuditMixin, TenantMixin, SoftMixin, Document):
    type: str
    name: str
    body: str
    is_active: bool = True

    class Settings:
        name = "document_templates"
        indexes = [IndexModel([("company_id", 1), ("type", 1)])]


class GeneratedDocument(AuditMixin, TenantMixin, Document):
    template_id: str | None = None
    employee_id: str | None = None
    doc_type: str
    file_key: str
    verification_code: Indexed(str, unique=True)
    sequence_no: str

    class Settings:
        name = "generated_documents"


class NotificationTemplate(AuditMixin, TenantMixin, Document):
    event_key: str
    channel: str
    subject: str
    body: str
    is_active: bool = True

    class Settings:
        name = "notification_templates"
        indexes = [IndexModel([("company_id", 1), ("event_key", 1), ("channel", 1)])]


class Notification(TenantMixin, Document):
    user_id: str
    event_key: str
    title: str
    body: str
    read_at: datetime | None = None
    created_at: datetime

    class Settings:
        name = "notifications"
        indexes = [IndexModel([("company_id", 1), ("user_id", 1), ("read_at", 1)])]


class NotificationPreference(TenantMixin, Document):
    user_id: str
    event_key: str
    in_app: bool = True
    email: bool = True

    class Settings:
        name = "notification_preferences"
        indexes = [IndexModel([("company_id", 1), ("user_id", 1), ("event_key", 1)], unique=True)]
