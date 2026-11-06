from __future__ import annotations

from pydantic import BaseModel, Field


class TicketWrite(BaseModel):
    employee_id: str | None = None
    category: str
    subject: str = Field(min_length=1)
    body: str
    attachment_keys: list[str] = Field(default_factory=list)
    assigned_to: str | None = None
    priority: str = "normal"
    status: str = "open"


class TicketUpdate(BaseModel):
    category: str | None = None
    subject: str | None = None
    body: str | None = None
    attachment_keys: list[str] | None = None
    assigned_to: str | None = None
    priority: str | None = None
    status: str | None = None


class CommentWrite(BaseModel):
    body: str = Field(min_length=1)
