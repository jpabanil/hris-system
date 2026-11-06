from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

HolidayKind = Literal[
    "regular",
    "special_non_working",
    "special_working",
    "local",
    "double_regular",
    "local_regular",
    "local_special",
]
HolidayScope = Literal["nationwide", "branch", "city"]
PunchType = Literal["in", "out"]


class WorkScheduleWrite(BaseModel):
    name: str
    time_in: str
    time_out: str
    break_minutes: int = 60
    grace_minutes: int = 5
    rest_days: list[int] = Field(default_factory=lambda: [5, 6])
    is_flexible: bool = False
    core_hours: str = ""
    is_night_shift: bool = False
    required_hours: str = "8"
    revision: int | None = None


class ShiftWrite(BaseModel):
    code: str
    start: str
    end: str
    break_minutes: int = 60
    crosses_midnight: bool = False


class RosterEntryWrite(BaseModel):
    employee_id: str
    date: date
    shift_id: str


class EmployeeScheduleWrite(BaseModel):
    employee_id: str
    work_schedule_id: str
    effective_from: date
    effective_to: date | None = None


class HolidayWrite(BaseModel):
    date: date
    name: str
    type: HolidayKind
    scope: HolidayScope = "nationwide"
    branch_ids: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)


class ClockIn(BaseModel):
    type: PunchType
    source: str
    lat: float | None = None
    lng: float | None = None
    selfie_key: str | None = None


class ImportPunch(BaseModel):
    employee_no: str
    logged_at: datetime
    type: PunchType


class ComputeDayBody(BaseModel):
    employee_id: str
    date: date


class OvertimeWrite(BaseModel):
    employee_id: str | None = None
    date: date
    minutes: int = Field(gt=0, le=24 * 60)
    reason: str = ""


class CorrectionWrite(BaseModel):
    employee_id: str | None = None
    date: date
    proposed_in: datetime | None = None
    proposed_out: datetime | None = None
    reason: str = ""


class OfficialBusinessWrite(BaseModel):
    employee_id: str | None = None
    start_date: date
    end_date: date
    location: str = ""
    reason: str = ""


class WfhWrite(BaseModel):
    employee_id: str | None = None
    start_date: date
    end_date: date
    reason: str = ""


class ShiftSwapWrite(BaseModel):
    requester_id: str | None = None
    counterpart_id: str
    dates: list[date] = Field(min_length=1)
