from __future__ import annotations

from datetime import date
from typing import Any

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.core.models import AuditMixin, TenantMixin


class Criterion(BaseModel):
    name: str
    weight: str


class ReviewCycle(AuditMixin, TenantMixin, Document):
    name: str
    start: date
    end: date
    status: str = "open"

    class Settings:
        name = "review_cycles"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class ReviewTemplate(AuditMixin, TenantMixin, Document):
    name: str
    criteria: list[Criterion] = Field(default_factory=list)
    rating_scale: int = 5

    class Settings:
        name = "review_templates"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class PerformanceReview(AuditMixin, TenantMixin, Document):
    cycle_id: str
    employee_id: str
    template_id: str | None = None
    self_ratings: list[dict[str, Any]] = Field(default_factory=list)
    manager_ratings: list[dict[str, Any]] = Field(default_factory=list)
    peer_ratings: list[dict[str, Any]] = Field(default_factory=list)
    final_score: str | None = None
    calibration_notes: str = ""
    status: str = "draft"

    class Settings:
        name = "performance_reviews"
        indexes = [
            IndexModel(
                [("company_id", 1), ("cycle_id", 1), ("employee_id", 1)],
                unique=True,
            )
        ]


class Goal(AuditMixin, TenantMixin, Document):
    employee_id: str
    cycle_id: str | None = None
    title: str
    weight: str = "0"
    target: str = ""
    actual: str = ""
    progress: int = 0

    class Settings:
        name = "goals"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class ProbationEvaluation(AuditMixin, TenantMixin, Document):
    employee_id: str
    outcome: str = "pending"
    notes: str = ""
    status: str = "draft"

    class Settings:
        name = "probation_evaluations"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class OneOnOne(AuditMixin, TenantMixin, Document):
    manager_id: str
    employee_id: str
    date: date
    notes: str = ""
    action_items: list[str] = Field(default_factory=list)

    class Settings:
        name = "one_on_ones"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("date", -1)])]
