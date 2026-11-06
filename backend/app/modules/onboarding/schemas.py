from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateTaskWrite(BaseModel):
    task: str
    owner_role: str = "HR Staff"
    due_offset_days: int = 0


class TemplateWrite(BaseModel):
    name: str
    tasks: list[TemplateTaskWrite] = Field(default_factory=list)


class TaskPatch(BaseModel):
    status: str
    assignee_id: str | None = None
