from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class OffenseWrite(BaseModel):
    offense: str
    category: str = ""
    sanctions_by_count: list[str] = Field(default_factory=list)


class IncidentWrite(BaseModel):
    reported_by: str
    employee_id: str
    date: date
    description: str
    attachment_keys: list[str] = Field(default_factory=list)


class CaseWrite(BaseModel):
    employee_id: str
    incident_report_id: str | None = None
    offense_id: str | None = None
    case_no: str | None = None
    status: str | None = None
    sanction_type: str = ""
    suspension_days: int = 0
    details: str | None = None


class NteBody(BaseModel):
    details: str = ""


class ExplanationBody(BaseModel):
    explanation: str = ""


class HearingBody(BaseModel):
    schedule: str = ""
    notes: str = ""


class DecisionBody(BaseModel):
    sanction_type: str
    suspension_days: int = 0
    notes: str = ""


class GrievanceWrite(BaseModel):
    submitted_by: str | None = None
    anonymous: bool = False
    category: str
    assigned_to: str | None = None
    status: str = "open"
    description: str = ""
    resolution: str = ""


class PolicyWrite(BaseModel):
    title: str
    version: int = 1
    file_key: str | None = None
    body: str = ""
    requires_acknowledgment: bool = True
    effective_date: date | None = None
