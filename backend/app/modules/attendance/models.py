from __future__ import annotations

from datetime import date, datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.core.models import AuditMixin, RevisionMixin, SoftMixin, TenantMixin


class WorkSchedule(AuditMixin, TenantMixin, SoftMixin, RevisionMixin, Document):
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

    class Settings:
        name = "work_schedules"
        indexes = [IndexModel([("company_id", 1), ("name", 1)])]


class Shift(AuditMixin, TenantMixin, SoftMixin, Document):
    code: str
    start: str
    end: str
    break_minutes: int = 60
    crosses_midnight: bool = False

    class Settings:
        name = "shifts"
        indexes = [IndexModel([("company_id", 1), ("code", 1)], unique=True)]


class RosterEntry(AuditMixin, TenantMixin, Document):
    employee_id: str
    date: date
    shift_id: str

    class Settings:
        name = "roster_entries"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("date", 1)], unique=True)]


class EmployeeSchedule(AuditMixin, TenantMixin, Document):
    employee_id: str
    work_schedule_id: str
    effective_from: date
    effective_to: date | None = None

    class Settings:
        name = "employee_schedules"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("effective_from", -1)])]


class Holiday(AuditMixin, TenantMixin, SoftMixin, Document):
    date: date
    name: str
    type: str
    scope: str = "nationwide"
    branch_ids: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)

    class Settings:
        name = "holidays"
        indexes = [IndexModel([("company_id", 1), ("date", 1)])]


class AttendanceLog(TenantMixin, Document):
    employee_id: str
    logged_at: datetime
    type: str
    source: str
    ip: str | None = None
    location: dict[str, Any] | None = None
    selfie_key: str | None = None
    device_info: str = ""
    within_geofence: bool | None = None

    class Settings:
        name = "attendance_logs"
        indexes = [IndexModel([("employee_id", 1), ("logged_at", -1)])]


class AttendanceDay(TenantMixin, Document):
    employee_id: str
    date: date
    schedule_snapshot: dict[str, Any] = Field(default_factory=dict)
    first_in: datetime | None = None
    last_out: datetime | None = None
    hours_worked: str = "0"
    late_minutes: int = 0
    undertime_minutes: int = 0
    overtime_minutes: int = 0
    night_diff_minutes: int = 0
    is_rest_day: bool = False
    holiday_type: str = "none"
    status: str = "absent"
    is_locked: bool = False
    portions: list[dict[str, Any]] = Field(default_factory=list)

    class Settings:
        name = "attendance_days"
        indexes = [IndexModel([("employee_id", 1), ("date", 1)], unique=True)]


class OvertimeRequest(AuditMixin, TenantMixin, Document):
    employee_id: str
    date: date
    minutes: int
    status: str = "pending"
    approval_request_id: str | None = None
    reason: str = ""

    class Settings:
        name = "overtime_requests"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1), ("date", 1)])]


class AttendanceCorrection(AuditMixin, TenantMixin, Document):
    employee_id: str
    date: date
    proposed_in: datetime | None = None
    proposed_out: datetime | None = None
    status: str = "pending"
    approval_request_id: str | None = None
    reason: str = ""

    class Settings:
        name = "attendance_corrections"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class OfficialBusiness(AuditMixin, TenantMixin, Document):
    employee_id: str
    start_date: date
    end_date: date
    location: str = ""
    status: str = "pending"
    approval_request_id: str | None = None
    reason: str = ""

    class Settings:
        name = "official_business"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class WfhRequest(AuditMixin, TenantMixin, Document):
    employee_id: str
    start_date: date
    end_date: date
    status: str = "pending"
    approval_request_id: str | None = None
    reason: str = ""

    class Settings:
        name = "wfh_requests"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]


class ShiftSwapRequest(AuditMixin, TenantMixin, Document):
    requester_id: str
    counterpart_id: str
    dates: list[date] = Field(default_factory=list)
    status: str = "pending"
    approval_request_id: str | None = None

    class Settings:
        name = "shift_swap_requests"
        indexes = [IndexModel([("company_id", 1), ("requester_id", 1)])]
