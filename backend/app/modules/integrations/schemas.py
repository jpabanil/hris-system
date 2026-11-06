from __future__ import annotations

from pydantic import BaseModel


class WebhookWrite(BaseModel):
    event: str
    url: str
    secret: str
    is_active: bool = True


class WebhookUpdate(BaseModel):
    event: str | None = None
    url: str | None = None
    secret: str | None = None
    is_active: bool | None = None
