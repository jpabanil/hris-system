from __future__ import annotations

from pydantic import BaseModel, Field


class ConsentWrite(BaseModel):
    subject_type: str
    subject_id: str
    purpose: str
    version: str


class DataSubjectWrite(BaseModel):
    type: str
    requester: str
    status: str = "open"


class RetentionWrite(BaseModel):
    record_type: str
    retain_years: int = Field(ge=0)
    action: str = "anonymize"
