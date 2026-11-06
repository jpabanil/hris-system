from __future__ import annotations

from datetime import date, datetime

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, SoftMixin, TenantMixin


class TemplateTask(BaseModel):
    task: str
    owner_role: str = "HR Staff"
    due_offset_days: int = 0


class ChecklistTask(BaseModel):
    task: str
    assignee_id: str | None = None
    due_date: date | None = None
    status: str = "open"
    completed_at: datetime | None = None


class OnboardingTemplate(AuditMixin, TenantMixin, SoftMixin, Document):
    name: str
    tasks: list[TemplateTask] = Field(default_factory=list)

    class Settings:
        name = "onboarding_templates"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class OnboardingChecklist(AuditMixin, TenantMixin, Document):
    employee_id: str
    template_id: str | None = None
    tasks: list[ChecklistTask] = Field(default_factory=list)

    class Settings:
        name = "onboarding_checklists"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)], unique=True)]
