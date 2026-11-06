from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class CycleWrite(BaseModel):
    name: str
    start: date
    end: date
    status: str = "open"


class CriterionWrite(BaseModel):
    name: str
    weight: str


class TemplateWrite(BaseModel):
    name: str
    criteria: list[CriterionWrite] = Field(default_factory=list)
    rating_scale: int = 5


class ReviewWrite(BaseModel):
    cycle_id: str
    employee_id: str
    template_id: str | None = None
    self_ratings: list[dict[str, Any]] = Field(default_factory=list)
    manager_ratings: list[dict[str, Any]] = Field(default_factory=list)
    peer_ratings: list[dict[str, Any]] = Field(default_factory=list)
    final_score: str | None = None
    calibration_notes: str = ""
    status: str = "draft"


class GoalWrite(BaseModel):
    employee_id: str
    cycle_id: str | None = None
    title: str
    weight: str = "0"
    target: str = ""
    actual: str = ""
    progress: int = 0


class ProbationWrite(BaseModel):
    employee_id: str
    outcome: str = "pending"
    notes: str = ""
    status: str = "draft"


class OneOnOneWrite(BaseModel):
    manager_id: str
    employee_id: str
    date: date
    notes: str = ""
    action_items: list[str] = Field(default_factory=list)
