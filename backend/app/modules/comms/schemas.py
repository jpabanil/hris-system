from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AnnouncementWrite(BaseModel):
    title: str
    body: str
    audience: str = "all"
    audience_id: str | None = None
    pinned: bool = False
    publish_at: datetime | None = None
    expire_at: datetime | None = None
