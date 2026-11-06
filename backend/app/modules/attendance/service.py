"""Attendance use cases. No FastAPI imports."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from beanie.odm.enums import SortDirection
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import DuplicateKeyError

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.errors import AppError
from app.core.money import D, money_str
from app.core.repository import TenantRepo, api
from app.domain.attendance import (
    AttendanceRules,
    Punch,
    ScheduleSnap,
    compute_day,
    holiday_applies,
)
from app.domain.leave import ranges_overlap
from app.modules.attendance.models import (
    AttendanceCorrection,
    AttendanceDay,
    AttendanceLog,
    EmployeeSchedule,
    Holiday,
    OfficialBusiness,
    OvertimeRequest,
    RosterEntry,
    Shift,
    ShiftSwapRequest,
    WfhRequest,
    WorkSchedule,
)
from app.modules.attendance.policies import (
    assert_can_touch,
    employee_scope,
    require_clock,
    require_company,
    require_reader,
    resolve_filer,
    subject_employee_id,
)
from app.modules.attendance.schemas import (
    ClockIn,
    CorrectionWrite,
    EmployeeScheduleWrite,
    HolidayWrite,
    ImportPunch,
    OfficialBusinessWrite,
    OvertimeWrite,
    RosterEntryWrite,
    ShiftSwapWrite,
    ShiftWrite,
    WfhWrite,
    WorkScheduleWrite,
)
from app.modules.employees.models import Employee
from app.modules.leave.models import LeaveRequest
from app.modules.organization.models import Branch, Company
from app.shared.approvals import handles, start_request
from app.shared.audit import write_audit
from app.shared.models import ApprovalRequest, IdempotencyKey
from app.shared.settings_store import AttendanceSettings, get_settings_model

logger = logging.getLogger("hris.attendance")

_LEAD = timedelta(hours=3)
_TAIL = timedelta(hours=4)
_HOLIDAY_RANK = {
    "double_regular": 50,
    "regular": 40,
    "local_regular": 35,
    "special_non_working": 30,
    "local_special": 25,
    "local": 20,
    "special_working": 10,
}
_CATALOG_SORTS = {"name", "code", "created_at", "date"}


@dataclass(frozen=True)
class _Span:
    day: date
    start: datetime
    end: datetime


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "Asia/Manila")
    except Exception:
        return ZoneInfo("Asia/Manila")


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _hhmm(value: str) -> int:
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise AppError("bad_time", "Time must be HH:MM", 400)
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise AppError("bad_time", "Time must be HH:MM", 400) from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise AppError("bad_time", "Time must be HH:MM", 400)
    return hour * 60 + minute


def _minutes_from_hours(value: str) -> int:
    quant = (D(value) * Decimal(60)).to_integral_value(rounding=ROUND_HALF_UP)
    return int(quant)


def _at(day: date, minute: int, tz: ZoneInfo) -> datetime:
    hour, mins = divmod(minute, 60)
    extra, hour = divmod(hour, 24)
    base = day + timedelta(days=extra)
    return datetime(base.year, base.month, base.day, hour, mins, tzinfo=tz)


def _aware(moment: datetime, tz: ZoneInfo) -> datetime:
    # Naive punches are treated as UTC. Clock and import always store aware UTC.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC).astimezone(tz)
    return moment.astimezone(tz)


def _meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    chord = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(chord))


def owning_day(moment: datetime, spans: list[_Span]) -> date | None:
    """Shift start date for a punch. Midnight shifts keep hours until they end."""
    ordered = sorted(spans, key=lambda span: span.start)
    cores = [span for span in ordered if span.start <= moment < span.end]
    if cores:
        return min(cores, key=lambda span: span.start).day
    windows: list[_Span] = []
    for index, span in enumerate(ordered):
        nxt = ordered[index + 1] if index + 1 < len(ordered) else None
        begin = span.start - _LEAD
        finish = span.end + _TAIL
        if nxt is not None and nxt.start > span.start:
            finish = min(finish, max(span.end, nxt.start - _LEAD))
        if begin <= moment < finish:
            windows.append(span)
    if not windows:
        return None
    best = windows[0]
    for span in windows[1:]:
        if abs(span.start - moment) < abs(best.start - moment):
            best = span
    return best.day


def _calendar_span(day: date, tz: ZoneInfo) -> _Span:
    start = datetime.combine(day, time.min, tzinfo=tz)
    return _Span(day, start, start + timedelta(days=1))


def _shift_span(day: date, snap: ScheduleSnap, tz: ZoneInfo) -> _Span:
    start = _at(day, snap.start_minute, tz)
    if snap.crosses_midnight:
        end = _at(day + timedelta(days=1), snap.end_minute, tz)
    else:
        end = _at(day, snap.end_minute, tz)
    if end <= start:
        end = end + timedelta(days=1)
    return _Span(day, start, end)


def _check_rest(days: list[int]) -> None:
    for day in days:
        if day < 0 or day > 6:
            raise AppError("bad_rest_day", "Rest days must be 0 (Monday) through 6 (Sunday)", 400)


def _check_non_negative(value: int, label: str) -> None:
    if value < 0:
        raise AppError("bad_request", f"{label} cannot be negative", 400)


def _snap_dict(snap: ScheduleSnap) -> dict[str, Any]:
    return {
        "start_minute": snap.start_minute,
        "end_minute": snap.end_minute,
        "break_minutes": snap.break_minutes,
        "grace_minutes": snap.grace_minutes,
        "rest_days": list(snap.rest_days),
        "crosses_midnight": snap.crosses_midnight,
        "required_minutes": snap.required_minutes,
    }


def _snap_work(work: WorkSchedule) -> ScheduleSnap:
    start = _hhmm(work.time_in)
    end = _hhmm(work.time_out)
    crosses = work.is_night_shift or end <= start
    return ScheduleSnap(
        start_minute=start,
        end_minute=end,
        break_minutes=work.break_minutes,
        grace_minutes=work.grace_minutes,
        rest_days=tuple(int(day) for day in work.rest_days),
        crosses_midnight=crosses,
        required_minutes=_minutes_from_hours(work.required_hours),
    )


def _snap_shift(shift: Shift, rest: tuple[int, ...], grace: int) -> ScheduleSnap:
    start = _hhmm(shift.start)
    end = _hhmm(shift.end)
    crosses = shift.crosses_midnight or end <= start
    span = (24 * 60 - start) + end if crosses else end - start
    return ScheduleSnap(
        start_minute=start,
        end_minute=end,
        break_minutes=shift.break_minutes,
        grace_minutes=grace,
        rest_days=rest,
        crosses_midnight=crosses,
        required_minutes=max(0, span - shift.break_minutes),
    )


def _rules(settings: AttendanceSettings) -> AttendanceRules:
    return AttendanceRules(
        late_counts_from_schedule_if_beyond_grace=settings.late_counts_from_schedule_if_beyond_grace,
        night_start_minute=_hhmm(settings.night_start),
        night_end_minute=_hhmm(settings.night_end),
        ot_rounding_minutes=settings.ot_rounding_minutes,
        ot_requires_approval=settings.ot_requires_approval,
        daily_ot_cap_minutes=settings.daily_ot_cap_minutes,
    )


def _holiday_type(
    holidays: list[Holiday],
    day: date,
    branch_id: str | None,
    city: str | None,
) -> str:
    matched: list[str] = []
    for holiday in holidays:
        if holiday.deleted_at is not None or _as_date(holiday.date) != day:
            continue
        applies = holiday_applies(
            holiday.scope,
            branch_id=branch_id,
            branch_city=city,
            branch_ids=tuple(holiday.branch_ids),
            cities=tuple(holiday.cities),
        )
        if applies:
            matched.append(holiday.type)
    regulars = sum(1 for item in matched if item in {"regular", "local_regular"})
    if regulars >= 2:
        return "double_regular"
    if not matched:
        return "none"
    return max(matched, key=lambda item: _HOLIDAY_RANK.get(item, 0))


async def _settings(company_id: str) -> AttendanceSettings:
    raw = await get_settings_model(company_id, "attendance")
    if isinstance(raw, AttendanceSettings):
        return raw
    return AttendanceSettings.model_validate(raw.model_dump())


async def _employee(company_id: str, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if employee is None or employee.company_id != company_id or employee.deleted_at is not None:
        raise AppError("not_found", "Employee not found", 404)
    return employee


async def _assignment(company_id: str, employee_id: str, day: date) -> EmployeeSchedule | None:
    rows = (
        await EmployeeSchedule.find(
            {"company_id": company_id, "employee_id": employee_id, "effective_from": {"$lte": day}}
        )
        .sort([("effective_from", SortDirection.DESCENDING)])
        .to_list()
    )
    for row in rows:
        if row.effective_to is None or _as_date(row.effective_to) >= day:
            return row
    return None


async def _resolved(
    company_id: str,
    employee_id: str,
    day: date,
    grace: int,
) -> tuple[ScheduleSnap | None, dict[str, Any]]:
    rest: tuple[int, ...] = (5, 6)
    work_id: str | None = None
    work_snap: ScheduleSnap | None = None
    assignment = await _assignment(company_id, employee_id, day)
    if assignment is not None:
        work = await WorkSchedule.get(assignment.work_schedule_id)
        if work is not None and work.company_id == company_id and work.deleted_at is None:
            rest = tuple(int(item) for item in work.rest_days)
            work_id = str(work.id)
            work_snap = _snap_work(work)
    roster = await RosterEntry.find_one(
        {"company_id": company_id, "employee_id": employee_id, "date": day}
    )
    if roster is not None:
        shift = await Shift.get(roster.shift_id)
        if shift is not None and shift.company_id == company_id and shift.deleted_at is None:
            snap = _snap_shift(shift, rest, grace)
            snapshot = {"shift_id": str(shift.id), "work_schedule_id": work_id, **_snap_dict(snap)}
            return snap, snapshot
    if work_snap is not None:
        snapshot = {"shift_id": None, "work_schedule_id": work_id, **_snap_dict(work_snap)}
        return work_snap, snapshot
    return None, {}


async def _list(
    actor: Actor,
    model: type,
    search: tuple[str, ...],
    page: int,
    page_size: int,
    q: str | None,
    sort: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_company(actor)
    return await TenantRepo(model, actor).list(
        page=page,
        page_size=page_size,
        search_fields=search,
        sort_fields=_CATALOG_SORTS,
        q=q,
        sort=sort,
        extra=extra,
    )


async def _conflict(awaitable: Any) -> Any:
    try:
        return await awaitable
    except DuplicateKeyError as exc:
        raise AppError("conflict", "That record already exists", 409) from exc


def _check_schedule(body: WorkScheduleWrite) -> None:
    _hhmm(body.time_in)
    _hhmm(body.time_out)
    _check_non_negative(body.break_minutes, "Break")
    _check_non_negative(body.grace_minutes, "Grace")
    _check_rest(body.rest_days)
    if D(body.required_hours) < 0:
        raise AppError("bad_hours", "Required hours cannot be negative", 400)


def _check_shift(body: ShiftWrite) -> None:
    _hhmm(body.start)
    _hhmm(body.end)
    _check_non_negative(body.break_minutes, "Break")


def _check_holiday(body: HolidayWrite) -> None:
    if body.scope == "branch" and not body.branch_ids:
        raise AppError("bad_scope", "A branch holiday needs at least one branch", 400)
    if body.scope == "city" and not body.cities:
        raise AppError("bad_scope", "A city holiday needs at least one city", 400)


async def list_work_schedules(
    actor: Actor, page: int, page_size: int, q: str | None, sort: str | None
) -> dict[str, Any]:
    require_reader(actor)
    return await _list(actor, WorkSchedule, ("name",), page, page_size, q, sort or "name")


async def get_work_schedule(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await TenantRepo(WorkSchedule, actor).get(doc_id))


async def create_work_schedule(actor: Actor, body: WorkScheduleWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    _check_schedule(body)
    doc = await _conflict(TenantRepo(WorkSchedule, actor).create(body))
    return api(doc)


async def update_work_schedule(
    actor: Actor, doc_id: str, body: WorkScheduleWrite
) -> dict[str, Any]:
    actor.require("attendance.manage")
    _check_schedule(body)
    doc = await _conflict(TenantRepo(WorkSchedule, actor).update(doc_id, body))
    return api(doc)


async def delete_work_schedule(actor: Actor, doc_id: str) -> None:
    actor.require("attendance.manage")
    require_company(actor)
    await TenantRepo(WorkSchedule, actor).soft_delete(doc_id)


async def list_shifts(
    actor: Actor, page: int, page_size: int, q: str | None, sort: str | None
) -> dict[str, Any]:
    require_reader(actor)
    return await _list(actor, Shift, ("code",), page, page_size, q, sort or "code")


async def get_shift(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await TenantRepo(Shift, actor).get(doc_id))


async def create_shift(actor: Actor, body: ShiftWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    _check_shift(body)
    return api(await _conflict(TenantRepo(Shift, actor).create(body)))


async def update_shift(actor: Actor, doc_id: str, body: ShiftWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    _check_shift(body)
    return api(await _conflict(TenantRepo(Shift, actor).update(doc_id, body)))


async def delete_shift(actor: Actor, doc_id: str) -> None:
    actor.require("attendance.manage")
    require_company(actor)
    await TenantRepo(Shift, actor).soft_delete(doc_id)


async def list_roster(
    actor: Actor,
    page: int,
    page_size: int,
    employee_id: str | None,
    start: date | None,
    end: date | None,
) -> dict[str, Any]:
    require_reader(actor)
    extra = await employee_scope(actor, employee_id)
    window: dict[str, date] = {}
    if start is not None:
        window["$gte"] = start
    if end is not None:
        window["$lte"] = end
    if window:
        extra["date"] = window
    return await _list(actor, RosterEntry, (), page, page_size, None, "date", extra)


async def create_roster(actor: Actor, body: RosterEntryWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    company_id = require_company(actor)
    await _employee(company_id, body.employee_id)
    shift = await TenantRepo(Shift, actor).get(body.shift_id)
    if shift.company_id != company_id:
        raise AppError("not_found", "Record not found", 404)
    return api(await _conflict(TenantRepo(RosterEntry, actor).create(body)))


async def update_roster(actor: Actor, doc_id: str, body: RosterEntryWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    company_id = require_company(actor)
    await _employee(company_id, body.employee_id)
    await TenantRepo(Shift, actor).get(body.shift_id)
    return api(await _conflict(TenantRepo(RosterEntry, actor).update(doc_id, body)))


async def delete_roster(actor: Actor, doc_id: str) -> None:
    actor.require("attendance.manage")
    require_company(actor)
    repo = TenantRepo(RosterEntry, actor)
    doc = await repo.get(doc_id)
    before = api(doc)
    await doc.delete()
    await write_audit(
        company_id=actor.company_id,
        actor_id=actor.user_id,
        action="delete",
        entity_type="roster_entries",
        entity_id=doc_id,
        before=before,
        after=None,
    )


async def list_employee_schedules(
    actor: Actor, page: int, page_size: int, employee_id: str | None
) -> dict[str, Any]:
    require_reader(actor)
    extra = await employee_scope(actor, employee_id)
    return await _list(actor, EmployeeSchedule, (), page, page_size, None, "-created_at", extra)


async def create_employee_schedule(actor: Actor, body: EmployeeScheduleWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    company_id = require_company(actor)
    await _employee(company_id, body.employee_id)
    await TenantRepo(WorkSchedule, actor).get(body.work_schedule_id)
    if body.effective_to is not None and body.effective_to < body.effective_from:
        raise AppError("bad_dates", "Effective end is before the start", 400)
    return api(await _conflict(TenantRepo(EmployeeSchedule, actor).create(body)))


async def update_employee_schedule(
    actor: Actor, doc_id: str, body: EmployeeScheduleWrite
) -> dict[str, Any]:
    actor.require("attendance.manage")
    company_id = require_company(actor)
    await _employee(company_id, body.employee_id)
    await TenantRepo(WorkSchedule, actor).get(body.work_schedule_id)
    if body.effective_to is not None and body.effective_to < body.effective_from:
        raise AppError("bad_dates", "Effective end is before the start", 400)
    return api(await _conflict(TenantRepo(EmployeeSchedule, actor).update(doc_id, body)))


async def delete_employee_schedule(actor: Actor, doc_id: str) -> None:
    actor.require("attendance.manage")
    require_company(actor)
    repo = TenantRepo(EmployeeSchedule, actor)
    doc = await repo.get(doc_id)
    before = api(doc)
    await doc.delete()
    await write_audit(
        company_id=actor.company_id,
        actor_id=actor.user_id,
        action="delete",
        entity_type="employee_schedules",
        entity_id=doc_id,
        before=before,
        after=None,
    )


async def list_holidays(
    actor: Actor, page: int, page_size: int, q: str | None, sort: str | None
) -> dict[str, Any]:
    require_reader(actor)
    return await _list(actor, Holiday, ("name",), page, page_size, q, sort or "date")


async def get_holiday(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await TenantRepo(Holiday, actor).get(doc_id))


async def create_holiday(actor: Actor, body: HolidayWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    _check_holiday(body)
    return api(await _conflict(TenantRepo(Holiday, actor).create(body)))


async def update_holiday(actor: Actor, doc_id: str, body: HolidayWrite) -> dict[str, Any]:
    actor.require("attendance.manage")
    _check_holiday(body)
    return api(await _conflict(TenantRepo(Holiday, actor).update(doc_id, body)))


async def delete_holiday(actor: Actor, doc_id: str) -> None:
    actor.require("attendance.manage")
    require_company(actor)
    await TenantRepo(Holiday, actor).soft_delete(doc_id)


def _idempotency_query(company_id: str, key: str) -> dict[str, str]:
    return {"company_id": company_id, "scope": "clock", "key": key}


async def clock_in(
    actor: Actor, body: ClockIn, idempotency_key: str, ip: str | None
) -> dict[str, Any]:
    require_clock(actor)
    company_id = require_company(actor)
    key = idempotency_key.strip()
    if not key:
        raise AppError("idempotency_key_required", "Idempotency-Key header is required", 400)
    existing = await IdempotencyKey.find_one(_idempotency_query(company_id, key))
    if existing is not None:
        return existing.response
    if not actor.employee_id:
        raise AppError("employee_required", "Your user is not linked to an employee", 400)
    employee = await _employee(company_id, actor.employee_id)
    settings = await _settings(company_id)
    if body.source not in settings.allowed_sources:
        raise AppError("source_not_allowed", "That clock source is not allowed", 400)
    if settings.selfie_required and not (body.selfie_key and body.selfie_key.strip()):
        raise AppError("selfie_required", "A selfie is required to clock", 400)
    within: bool | None = None
    if settings.geofence_required:
        within = await _inside_geofence(company_id, employee, body)
    location = None
    if body.lat is not None and body.lng is not None:
        location = {"lat": body.lat, "lng": body.lng}
    try:
        async with transaction() as session:
            raced = await IdempotencyKey.find_one(
                _idempotency_query(company_id, key), session=session
            )
            if raced is not None:
                return raced.response
            log = AttendanceLog(
                company_id=company_id,
                employee_id=str(employee.id),
                logged_at=utcnow(),
                type=body.type,
                source=body.source,
                ip=ip,
                location=location,
                selfie_key=body.selfie_key,
                device_info="",
                within_geofence=within,
            )
            await log.insert(session=session)
            payload = api(log)
            await IdempotencyKey(
                company_id=company_id,
                actor_id=actor.user_id,
                scope="clock",
                key=key,
                response=payload,
                created_at=utcnow(),
            ).insert(session=session)
            return payload
    except DuplicateKeyError:
        raced = await IdempotencyKey.find_one(_idempotency_query(company_id, key))
        if raced is not None:
            return raced.response
        raise


async def _inside_geofence(company_id: str, employee: Employee, body: ClockIn) -> bool:
    if body.lat is None or body.lng is None:
        raise AppError("location_required", "Location is required to clock", 400)
    if not employee.branch_id:
        raise AppError("geofence_missing", "Your branch has no geofence", 400)
    branch = await Branch.get(employee.branch_id)
    if (
        branch is None
        or branch.company_id != company_id
        or branch.deleted_at is not None
        or branch.geofence is None
    ):
        raise AppError("geofence_missing", "Your branch has no geofence", 400)
    distance = _meters(body.lat, body.lng, branch.geofence.lat, branch.geofence.lng)
    if distance > branch.geofence.radius_m:
        raise AppError(
            "outside_geofence",
            "You are outside the branch geofence",
            400,
            {"distance_m": int(distance), "radius_m": branch.geofence.radius_m},
        )
    return True


async def import_punches(actor: Actor, rows: list[ImportPunch]) -> dict[str, Any]:
    actor.require("attendance.manage")
    company_id = require_company(actor)
    if len(rows) > 2000:
        raise AppError("too_large", "Import at most 2000 punches at a time", 400)
    settings = await _settings(company_id)
    if "biometric_import" not in settings.allowed_sources:
        raise AppError("source_not_allowed", "Biometric import is not an allowed source", 400)
    created: list[dict[str, Any]] = []
    async with transaction() as session:
        for row in rows:
            employee = await Employee.find_one(
                {"company_id": company_id, "employee_no": row.employee_no, "deleted_at": None},
                session=session,
            )
            if employee is None:
                raise AppError("not_found", f"Employee {row.employee_no} was not found", 404)
            moment = row.logged_at if row.logged_at.tzinfo else row.logged_at.replace(tzinfo=UTC)
            log = AttendanceLog(
                company_id=company_id,
                employee_id=str(employee.id),
                logged_at=moment.astimezone(UTC),
                type=row.type,
                source="biometric_import",
                ip=None,
                location=None,
                selfie_key=None,
                device_info="",
                within_geofence=None,
            )
            await log.insert(session=session)
            created.append(api(log))
    return {"items": created, "total": len(created)}


async def list_days(
    actor: Actor,
    employee_id: str | None,
    start: date | None,
    end: date | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    require_reader(actor)
    extra = await employee_scope(actor, employee_id)
    window: dict[str, date] = {}
    if start is not None:
        window["$gte"] = start
    if end is not None:
        window["$lte"] = end
    if window:
        extra["date"] = window
    return await TenantRepo(AttendanceDay, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields={"date", "employee_id"},
        q=None,
        sort="date",
        extra=extra,
    )


def _context_for(doc: Any) -> dict[str, Any]:
    if isinstance(doc, OvertimeRequest):
        return {"employee_id": doc.employee_id, "minutes": doc.minutes}
    if isinstance(doc, AttendanceCorrection):
        return {"employee_id": doc.employee_id, "days": 1}
    if isinstance(doc, (OfficialBusiness, WfhRequest)):
        days = (_as_date(doc.end_date) - _as_date(doc.start_date)).days + 1
        return {"employee_id": doc.employee_id, "days": days}
    if isinstance(doc, ShiftSwapRequest):
        return {"employee_id": doc.requester_id, "days": len(doc.dates)}
    employee_id = getattr(doc, "employee_id", "") or getattr(doc, "requester_id", "")
    return {"employee_id": employee_id, "days": 1}


async def _attach_approval(
    actor: Actor,
    doc: Any,
    module: str,
    subject_type: str,
    context: dict[str, Any],
    session: AsyncClientSession,
) -> Any:
    approval = await start_request(
        actor=actor,
        module=module,
        subject_type=subject_type,
        subject_id=str(doc.id),
        context=context,
        session=session,
    )
    fresh = await type(doc).get(doc.id, session=session)
    if fresh is None:
        raise AppError("not_found", "Record not found", 404)
    fresh.approval_request_id = str(approval.id)
    if fresh.status == "pending" and approval.status != "pending":
        fresh.status = approval.status
    fresh.updated_at = utcnow()
    fresh.updated_by = actor.user_id
    await fresh.save(session=session)
    return fresh


async def _open_request(
    actor: Actor,
    doc: Any,
    module: str,
    subject_type: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    async with transaction() as session:
        await doc.insert(session=session)
        saved = await _attach_approval(actor, doc, module, subject_type, context, session)
        await write_audit(
            company_id=actor.company_id,
            actor_id=actor.user_id,
            action="create",
            entity_type=saved.get_collection_name(),
            entity_id=str(saved.id),
            after=api(saved),
            session=session,
        )
        return api(saved)


async def _sync_context(doc: Any) -> None:
    if not getattr(doc, "approval_request_id", None):
        return
    approval = await ApprovalRequest.get(doc.approval_request_id)
    if approval is None or approval.company_id != doc.company_id or approval.status != "pending":
        return
    approval.context = _context_for(doc)
    approval.updated_at = utcnow()
    await approval.save()


async def _sync_request_status(
    model: type,
    approval: ApprovalRequest,
    session: AsyncClientSession | None,
) -> None:
    if approval.status not in {"approved", "rejected", "returned"}:
        return
    doc = await model.get(approval.subject_id, session=session)  # type: ignore[attr-defined]
    if doc is None or doc.company_id != approval.company_id:
        return
    doc.status = approval.status
    doc.updated_at = utcnow()
    await doc.save(session=session)


def _bind_status(subject_type: str, model: type) -> None:
    async def handler(approval: ApprovalRequest, session: AsyncClientSession | None) -> None:
        await _sync_request_status(model, approval, session)

    handler.__name__ = f"on_{subject_type}"
    handles(subject_type)(handler)


_bind_status("overtime_requests", OvertimeRequest)
_bind_status("attendance_corrections", AttendanceCorrection)
_bind_status("official_business", OfficialBusiness)
_bind_status("wfh_requests", WfhRequest)
_bind_status("shift_swap_requests", ShiftSwapRequest)


def _owner(doc: Any) -> str:
    return subject_employee_id(
        getattr(doc, "employee_id", None), getattr(doc, "requester_id", None)
    )


def _editable(actor: Actor, employee_id: str) -> None:
    if actor.has("attendance.manage"):
        return
    if actor.has("self.service") and actor.employee_id == employee_id:
        return
    raise AppError("forbidden", "You do not have access to this action", 403)


async def _readable(actor: Actor, model: type, doc_id: str) -> Any:
    doc = await TenantRepo(model, actor).get(doc_id)
    await assert_can_touch(actor, _owner(doc))
    return doc


async def _request_extra(actor: Actor, employee_id: str | None, field: str) -> dict[str, Any]:
    extra = await employee_scope(actor, employee_id)
    if field != "employee_id" and "employee_id" in extra:
        extra[field] = extra.pop("employee_id")
    return extra


def _check_range(start: date, end: date) -> int:
    if end < start:
        raise AppError("bad_dates", "End date is before the start", 400)
    return (end - start).days + 1


async def list_overtime(
    actor: Actor, employee_id: str | None, page: int, page_size: int
) -> dict[str, Any]:
    require_reader(actor)
    extra = await _request_extra(actor, employee_id, "employee_id")
    return await _list(actor, OvertimeRequest, (), page, page_size, None, "-created_at", extra)


async def get_overtime(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await _readable(actor, OvertimeRequest, doc_id))


async def create_overtime(actor: Actor, body: OvertimeWrite) -> dict[str, Any]:
    company_id = require_company(actor)
    employee_id = resolve_filer(actor, body.employee_id)
    await _employee(company_id, employee_id)
    doc = OvertimeRequest(
        company_id=company_id,
        employee_id=employee_id,
        date=body.date,
        minutes=body.minutes,
        reason=body.reason,
        status="pending",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    context = {"employee_id": employee_id, "minutes": body.minutes}
    return await _open_request(actor, doc, "overtime", "overtime_requests", context)


async def update_overtime(actor: Actor, doc_id: str, body: OvertimeWrite) -> dict[str, Any]:
    doc = await _readable(actor, OvertimeRequest, doc_id)
    _editable(actor, doc.employee_id)
    if doc.status != "pending":
        raise AppError("conflict", "Only a pending request can be edited", 409)
    employee_id = resolve_filer(actor, body.employee_id or doc.employee_id)
    await _employee(require_company(actor), employee_id)
    body = body.model_copy(update={"employee_id": employee_id})
    updated = await TenantRepo(OvertimeRequest, actor).update(doc_id, body)
    await _sync_context(updated)
    return api(updated)


async def delete_overtime(actor: Actor, doc_id: str) -> None:
    await _delete_pending(actor, OvertimeRequest, doc_id)


async def list_corrections(
    actor: Actor, employee_id: str | None, page: int, page_size: int
) -> dict[str, Any]:
    require_reader(actor)
    extra = await _request_extra(actor, employee_id, "employee_id")
    return await _list(actor, AttendanceCorrection, (), page, page_size, None, "-created_at", extra)


async def get_correction(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await _readable(actor, AttendanceCorrection, doc_id))


async def create_correction(actor: Actor, body: CorrectionWrite) -> dict[str, Any]:
    company_id = require_company(actor)
    employee_id = resolve_filer(actor, body.employee_id)
    await _employee(company_id, employee_id)
    if body.proposed_in is None and body.proposed_out is None:
        raise AppError("bad_request", "A correction needs a proposed in or out", 400)
    doc = AttendanceCorrection(
        company_id=company_id,
        employee_id=employee_id,
        date=body.date,
        proposed_in=body.proposed_in,
        proposed_out=body.proposed_out,
        reason=body.reason,
        status="pending",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    return await _open_request(
        actor,
        doc,
        "attendance_correction",
        "attendance_corrections",
        {"employee_id": employee_id, "days": 1},
    )


async def update_correction(actor: Actor, doc_id: str, body: CorrectionWrite) -> dict[str, Any]:
    doc = await _readable(actor, AttendanceCorrection, doc_id)
    _editable(actor, doc.employee_id)
    if doc.status != "pending":
        raise AppError("conflict", "Only a pending request can be edited", 409)
    proposed_in = body.proposed_in if "proposed_in" in body.model_fields_set else doc.proposed_in
    proposed_out = (
        body.proposed_out if "proposed_out" in body.model_fields_set else doc.proposed_out
    )
    if proposed_in is None and proposed_out is None:
        raise AppError("bad_request", "A correction needs a proposed in or out", 400)
    employee_id = resolve_filer(actor, body.employee_id or doc.employee_id)
    await _employee(require_company(actor), employee_id)
    body = body.model_copy(update={"employee_id": employee_id})
    updated = await TenantRepo(AttendanceCorrection, actor).update(doc_id, body)
    await _sync_context(updated)
    return api(updated)


async def delete_correction(actor: Actor, doc_id: str) -> None:
    await _delete_pending(actor, AttendanceCorrection, doc_id)


async def list_official_business(
    actor: Actor, employee_id: str | None, page: int, page_size: int
) -> dict[str, Any]:
    require_reader(actor)
    extra = await _request_extra(actor, employee_id, "employee_id")
    return await _list(actor, OfficialBusiness, (), page, page_size, None, "-created_at", extra)


async def get_official_business(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await _readable(actor, OfficialBusiness, doc_id))


async def create_official_business(actor: Actor, body: OfficialBusinessWrite) -> dict[str, Any]:
    company_id = require_company(actor)
    employee_id = resolve_filer(actor, body.employee_id)
    await _employee(company_id, employee_id)
    days = _check_range(body.start_date, body.end_date)
    doc = OfficialBusiness(
        company_id=company_id,
        employee_id=employee_id,
        start_date=body.start_date,
        end_date=body.end_date,
        location=body.location,
        reason=body.reason,
        status="pending",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    return await _open_request(
        actor,
        doc,
        "official_business",
        "official_business",
        {"employee_id": employee_id, "days": days},
    )


async def update_official_business(
    actor: Actor, doc_id: str, body: OfficialBusinessWrite
) -> dict[str, Any]:
    doc = await _readable(actor, OfficialBusiness, doc_id)
    _editable(actor, doc.employee_id)
    if doc.status != "pending":
        raise AppError("conflict", "Only a pending request can be edited", 409)
    _check_range(body.start_date, body.end_date)
    employee_id = resolve_filer(actor, body.employee_id or doc.employee_id)
    await _employee(require_company(actor), employee_id)
    body = body.model_copy(update={"employee_id": employee_id})
    updated = await TenantRepo(OfficialBusiness, actor).update(doc_id, body)
    await _sync_context(updated)
    return api(updated)


async def delete_official_business(actor: Actor, doc_id: str) -> None:
    await _delete_pending(actor, OfficialBusiness, doc_id)


async def list_wfh(
    actor: Actor, employee_id: str | None, page: int, page_size: int
) -> dict[str, Any]:
    require_reader(actor)
    extra = await _request_extra(actor, employee_id, "employee_id")
    return await _list(actor, WfhRequest, (), page, page_size, None, "-created_at", extra)


async def get_wfh(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await _readable(actor, WfhRequest, doc_id))


async def create_wfh(actor: Actor, body: WfhWrite) -> dict[str, Any]:
    company_id = require_company(actor)
    employee_id = resolve_filer(actor, body.employee_id)
    await _employee(company_id, employee_id)
    days = _check_range(body.start_date, body.end_date)
    doc = WfhRequest(
        company_id=company_id,
        employee_id=employee_id,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
        status="pending",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    return await _open_request(
        actor, doc, "wfh", "wfh_requests", {"employee_id": employee_id, "days": days}
    )


async def update_wfh(actor: Actor, doc_id: str, body: WfhWrite) -> dict[str, Any]:
    doc = await _readable(actor, WfhRequest, doc_id)
    _editable(actor, doc.employee_id)
    if doc.status != "pending":
        raise AppError("conflict", "Only a pending request can be edited", 409)
    _check_range(body.start_date, body.end_date)
    employee_id = resolve_filer(actor, body.employee_id or doc.employee_id)
    await _employee(require_company(actor), employee_id)
    body = body.model_copy(update={"employee_id": employee_id})
    updated = await TenantRepo(WfhRequest, actor).update(doc_id, body)
    await _sync_context(updated)
    return api(updated)


async def delete_wfh(actor: Actor, doc_id: str) -> None:
    await _delete_pending(actor, WfhRequest, doc_id)


async def list_swaps(
    actor: Actor, employee_id: str | None, page: int, page_size: int
) -> dict[str, Any]:
    require_reader(actor)
    extra = await _request_extra(actor, employee_id, "requester_id")
    return await _list(actor, ShiftSwapRequest, (), page, page_size, None, "-created_at", extra)


async def get_swap(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await _readable(actor, ShiftSwapRequest, doc_id))


async def create_swap(actor: Actor, body: ShiftSwapWrite) -> dict[str, Any]:
    company_id = require_company(actor)
    requester_id = resolve_filer(actor, body.requester_id)
    await _employee(company_id, requester_id)
    if body.counterpart_id == requester_id:
        raise AppError("bad_request", "Choose a different coworker for the swap", 400)
    await _employee(company_id, body.counterpart_id)
    dates = sorted(set(body.dates))
    doc = ShiftSwapRequest(
        company_id=company_id,
        requester_id=requester_id,
        counterpart_id=body.counterpart_id,
        dates=dates,
        status="pending",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    return await _open_request(
        actor,
        doc,
        "shift_swap",
        "shift_swap_requests",
        {"employee_id": requester_id, "days": len(dates)},
    )


async def update_swap(actor: Actor, doc_id: str, body: ShiftSwapWrite) -> dict[str, Any]:
    doc = await _readable(actor, ShiftSwapRequest, doc_id)
    _editable(actor, doc.requester_id)
    if doc.status != "pending":
        raise AppError("conflict", "Only a pending request can be edited", 409)
    company_id = require_company(actor)
    requester_id = resolve_filer(actor, body.requester_id or doc.requester_id)
    await _employee(company_id, requester_id)
    if body.counterpart_id == requester_id:
        raise AppError("bad_request", "Choose a different coworker for the swap", 400)
    await _employee(company_id, body.counterpart_id)
    body = body.model_copy(update={"requester_id": requester_id, "dates": sorted(set(body.dates))})
    updated = await TenantRepo(ShiftSwapRequest, actor).update(doc_id, body)
    await _sync_context(updated)
    return api(updated)


async def delete_swap(actor: Actor, doc_id: str) -> None:
    await _delete_pending(actor, ShiftSwapRequest, doc_id)


async def _delete_pending(actor: Actor, model: type, doc_id: str) -> None:
    doc = await _readable(actor, model, doc_id)
    _editable(actor, _owner(doc))
    if doc.status != "pending":
        raise AppError("conflict", "Only a pending request can be deleted", 409)
    before = api(doc)
    await doc.delete()
    await write_audit(
        company_id=actor.company_id,
        actor_id=actor.user_id,
        action="delete",
        entity_type=model.get_collection_name(),  # type: ignore[attr-defined]
        entity_id=doc_id,
        before=before,
        after=None,
    )


def _apply_day(doc: AttendanceDay, result: Any, snapshot: dict[str, Any]) -> None:
    doc.schedule_snapshot = snapshot
    doc.first_in = result.first_in
    doc.last_out = result.last_out
    doc.hours_worked = money_str(result.hours_worked)
    doc.late_minutes = result.late_minutes
    doc.undertime_minutes = result.undertime_minutes
    doc.overtime_minutes = result.overtime_minutes
    doc.night_diff_minutes = result.night_diff_minutes
    doc.is_rest_day = result.is_rest_day
    doc.holiday_type = result.holiday_type
    doc.status = result.status
    doc.portions = [
        {
            "day": portion.day.isoformat(),
            "minutes": portion.minutes,
            "holiday_type": portion.holiday_type,
        }
        for portion in result.portions
    ]


async def _branch_place(company_id: str, employee: Employee) -> tuple[str | None, str | None]:
    if not employee.branch_id:
        return None, None
    branch = await Branch.get(employee.branch_id)
    if branch is None or branch.company_id != company_id or branch.deleted_at is not None:
        return None, None
    city = branch.city.strip() if branch.city else ""
    return str(branch.id), city or None


async def _punches_for(
    company_id: str,
    employee_id: str,
    day: date,
    tz: ZoneInfo,
    spans: list[_Span],
) -> tuple[Punch, ...]:
    window_start = datetime.combine(day - timedelta(days=2), time.min, tzinfo=tz)
    window_end = datetime.combine(day + timedelta(days=3), time.min, tzinfo=tz)
    logs = await AttendanceLog.find(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "logged_at": {"$gte": window_start, "$lt": window_end},
        }
    ).to_list()
    punches: list[Punch] = []
    for log in logs:
        if log.type not in {"in", "out"}:
            continue
        moment = _aware(log.logged_at, tz)
        if owning_day(moment, spans) != day:
            continue
        kind: Literal["in", "out"] = "in" if log.type == "in" else "out"
        punches.append(Punch(at=moment, kind=kind))
    return tuple(sorted(punches, key=lambda punch: punch.at))


async def _compute_employee_day(
    company_id: str,
    employee_id: str,
    day: date,
    tz: ZoneInfo,
    *,
    require_logs: bool,
) -> AttendanceDay | None:
    employee = await Employee.get(employee_id)
    if employee is None or employee.company_id != company_id or employee.deleted_at is not None:
        if require_logs:
            return None
        raise AppError("not_found", "Employee not found", 404)
    existing = await AttendanceDay.find_one(
        {"company_id": company_id, "employee_id": employee_id, "date": day}
    )
    if existing is not None and existing.is_locked:
        return existing
    settings = await _settings(company_id)
    snaps: dict[date, ScheduleSnap | None] = {}
    snapshots: dict[date, dict[str, Any]] = {}
    spans: list[_Span] = []
    for offset in (-1, 0, 1):
        current = day + timedelta(days=offset)
        snap, snapshot = await _resolved(company_id, employee_id, current, settings.grace_minutes)
        snaps[current] = snap
        snapshots[current] = snapshot
        spans.append(
            _shift_span(current, snap, tz) if snap is not None else _calendar_span(current, tz)
        )
    punches = await _punches_for(company_id, employee_id, day, tz, spans)
    if require_logs and not punches:
        return None
    holidays = await Holiday.find(
        {
            "company_id": company_id,
            "deleted_at": None,
            "date": {"$gte": day - timedelta(days=1), "$lte": day + timedelta(days=1)},
        }
    ).to_list()
    branch_id, city = await _branch_place(company_id, employee)
    approved_rows = await OvertimeRequest.find(
        {"company_id": company_id, "employee_id": employee_id, "date": day, "status": "approved"}
    ).to_list()
    approved = sum(row.minutes for row in approved_rows)
    leave_rows = await LeaveRequest.find(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "status": "approved",
            "start_date": {"$lte": day},
            "end_date": {"$gte": day},
        }
    ).to_list()
    on_leave = any(
        ranges_overlap(day, day, _as_date(row.start_date), _as_date(row.end_date))
        for row in leave_rows
    )
    result = compute_day(
        day=day,
        punches=punches,
        schedule=snaps[day],
        holiday_type=_holiday_type(holidays, day, branch_id, city),
        next_holiday_type=_holiday_type(holidays, day + timedelta(days=1), branch_id, city),
        approved_ot_minutes=approved,
        is_on_leave=on_leave,
        rules=_rules(settings),
    )
    snapshot = snapshots[day]
    if existing is None:
        created = AttendanceDay(
            company_id=company_id,
            employee_id=employee_id,
            date=day,
            is_locked=False,
        )
        _apply_day(created, result, snapshot)
        try:
            await created.insert()
        except DuplicateKeyError:
            again = await AttendanceDay.find_one({"employee_id": employee_id, "date": day})
            if again is None:
                return None
            if again.company_id != company_id:
                raise AppError("conflict", "That attendance day already exists", 409) from None
            if again.is_locked:
                return again
            _apply_day(again, result, snapshot)
            await again.save()
            return again
        return created
    _apply_day(existing, result, snapshot)
    await existing.save()
    return existing


async def compute_day_for(actor: Actor, employee_id: str, day: date) -> dict[str, Any]:
    actor.require("attendance.manage")
    company_id = require_company(actor)
    company = await Company.get(company_id)
    tz = _zone(company.timezone if company is not None else None)
    result = await _compute_employee_day(company_id, employee_id, day, tz, require_logs=False)
    if result is None:
        raise AppError("not_found", "Attendance day was not computed", 404)
    return api(result)


async def _compute_company_yesterday(company: Company) -> None:
    tz = _zone(company.timezone)
    day = datetime.now(tz).date() - timedelta(days=1)
    company_id = str(company.id)
    window_start = datetime.combine(day - timedelta(days=2), time.min, tzinfo=tz)
    window_end = datetime.combine(day + timedelta(days=3), time.min, tzinfo=tz)
    logs = await AttendanceLog.find(
        {"company_id": company_id, "logged_at": {"$gte": window_start, "$lt": window_end}}
    ).to_list()
    for employee_id in {log.employee_id for log in logs}:
        try:
            await _compute_employee_day(company_id, employee_id, day, tz, require_logs=True)
        except Exception:
            logger.exception("attendance recompute failed for %s on %s", employee_id, day)


async def compute_open_days() -> None:
    companies = await Company.find({"deleted_at": None, "is_active": True}).to_list()
    for company in companies:
        try:
            await _compute_company_yesterday(company)
        except Exception:
            logger.exception("attendance recompute failed for %s", company.id)
