"""Attendance day calculator. The caller groups punches onto the shift start date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

HolidayType = Literal[
    "none",
    "regular",
    "special_non_working",
    "special_working",
    "double_regular",
    "local_regular",
    "local_special",
]


@dataclass(frozen=True)
class ScheduleSnap:
    start_minute: int
    end_minute: int
    break_minutes: int
    grace_minutes: int
    rest_days: tuple[int, ...]
    crosses_midnight: bool
    required_minutes: int


@dataclass(frozen=True)
class Punch:
    at: datetime
    kind: Literal["in", "out"]


@dataclass(frozen=True)
class AttendanceRules:
    late_counts_from_schedule_if_beyond_grace: bool = False
    night_start_minute: int = 22 * 60
    night_end_minute: int = 6 * 60
    ot_rounding_minutes: int = 0
    ot_requires_approval: bool = True
    daily_ot_cap_minutes: int | None = None


@dataclass(frozen=True)
class DayPortion:
    day: date
    minutes: int
    holiday_type: str


@dataclass(frozen=True)
class DayResult:
    first_in: datetime | None
    last_out: datetime | None
    hours_worked: Decimal
    late_minutes: int
    undertime_minutes: int
    overtime_minutes: int
    night_diff_minutes: int
    is_rest_day: bool
    holiday_type: str
    status: str
    portions: tuple[DayPortion, ...]


def holiday_applies(
    scope: str,
    *,
    branch_id: str | None,
    branch_city: str | None,
    branch_ids: tuple[str, ...] = (),
    cities: tuple[str, ...] = (),
) -> bool:
    if scope == "nationwide":
        return True
    if scope == "branch":
        return branch_id is not None and branch_id in branch_ids
    if scope == "city":
        return branch_city is not None and branch_city in cities
    return False


def _minutes(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def _clock_on(day: date, minute: int) -> datetime:
    # A naive clock used only for differences. Callers pass aware punches;
    # we compare them on their own timeline.
    return datetime(day.year, day.month, day.day) + timedelta(minutes=minute)


def _overlap_minutes(start: datetime, end: datetime, night_start: int, night_end: int) -> int:
    """Minutes of [start, end) inside the night window, which may cross midnight."""
    if end <= start:
        return 0
    total = 0
    cursor = start
    while cursor < end:
        day_start = datetime(cursor.year, cursor.month, cursor.day, tzinfo=cursor.tzinfo)
        day_end = day_start + timedelta(days=1)
        slice_end = min(end, day_end)
        begin_m = _minutes(cursor)
        finish_m = _minutes(slice_end) if slice_end.date() == cursor.date() else 24 * 60
        total += _night_on_day(begin_m, finish_m, night_start, night_end)
        cursor = slice_end
    return total


def _night_on_day(begin: int, finish: int, night_start: int, night_end: int) -> int:
    # Night is [night_start, 24:00) U [0, night_end).
    windows = [(night_start, 24 * 60), (0, night_end)]
    counted = 0
    for w0, w1 in windows:
        left = max(begin, w0)
        right = min(finish, w1)
        if right > left:
            counted += right - left
    return counted


def compute_day(
    *,
    day: date,
    punches: tuple[Punch, ...],
    schedule: ScheduleSnap | None,
    holiday_type: str,
    next_holiday_type: str,
    approved_ot_minutes: int,
    is_on_leave: bool,
    rules: AttendanceRules,
) -> DayResult:
    ordered = tuple(sorted(punches, key=lambda p: p.at))
    ins = [p.at for p in ordered if p.kind == "in"]
    outs = [p.at for p in ordered if p.kind == "out"]
    first_in = ins[0] if ins else None
    last_out = outs[-1] if outs else None
    is_rest = schedule is not None and day.weekday() in schedule.rest_days

    if first_in is None or last_out is None or last_out <= first_in:
        status = (
            "leave"
            if is_on_leave
            else "holiday"
            if holiday_type != "none"
            else "rest"
            if is_rest
            else "absent"
            if schedule and not is_rest
            else "rest"
            if is_rest
            else "absent"
        )
        if first_in is not None and last_out is None:
            status = "incomplete"
        return DayResult(
            first_in=first_in,
            last_out=last_out,
            hours_worked=Decimal("0.00"),
            late_minutes=0,
            undertime_minutes=0,
            overtime_minutes=0,
            night_diff_minutes=0,
            is_rest_day=is_rest,
            holiday_type=holiday_type,
            status=status,
            portions=(),
        )

    presence = int((last_out - first_in).total_seconds() // 60)
    break_minutes = schedule.break_minutes if schedule else 0
    worked = max(0, presence - break_minutes)
    hours = (Decimal(worked) / Decimal(60)).quantize(Decimal("0.01"))

    late = 0
    undertime = 0
    required = schedule.required_minutes if schedule else worked
    if schedule is not None:
        start_at = _aware_like(first_in, day, schedule.start_minute)
        end_day = day + timedelta(days=1) if schedule.crosses_midnight else day
        end_at = _aware_like(first_in, end_day, schedule.end_minute)
        grace_end = start_at + timedelta(minutes=schedule.grace_minutes)
        if first_in > grace_end:
            if rules.late_counts_from_schedule_if_beyond_grace:
                late = int((first_in - start_at).total_seconds() // 60)
            else:
                late = int((first_in - grace_end).total_seconds() // 60)
        if last_out < end_at:
            undertime = int((end_at - last_out).total_seconds() // 60)
        raw_ot = max(0, worked - required)
    else:
        raw_ot = 0

    if rules.ot_requires_approval:
        ot = min(raw_ot, max(0, approved_ot_minutes))
    else:
        ot = raw_ot
    block = rules.ot_rounding_minutes
    if block and block > 1:
        ot = (ot // block) * block
    if rules.daily_ot_cap_minutes is not None:
        ot = min(ot, rules.daily_ot_cap_minutes)

    night_presence = _overlap_minutes(
        first_in, last_out, rules.night_start_minute, rules.night_end_minute
    )
    if presence > 0:
        night = int(night_presence * worked / presence)
    else:
        night = 0

    portions = _split_by_calendar_day(
        first_in, last_out, worked, presence, holiday_type, next_holiday_type
    )
    return DayResult(
        first_in=first_in,
        last_out=last_out,
        hours_worked=hours,
        late_minutes=late,
        undertime_minutes=undertime,
        overtime_minutes=ot,
        night_diff_minutes=night,
        is_rest_day=is_rest,
        holiday_type=holiday_type,
        status="present",
        portions=portions,
    )


def _aware_like(sample: datetime, day: date, minute: int) -> datetime:
    clock = datetime(day.year, day.month, day.day, minute // 60, minute % 60)
    if sample.tzinfo is not None:
        return clock.replace(tzinfo=sample.tzinfo)
    return clock


def _split_by_calendar_day(
    start: datetime,
    end: datetime,
    worked: int,
    presence: int,
    holiday_type: str,
    next_holiday_type: str,
) -> tuple[DayPortion, ...]:
    if presence <= 0:
        return ()
    if start.date() == end.date():
        return (DayPortion(start.date(), worked, holiday_type),)
    midnight = datetime(end.year, end.month, end.day)
    if start.tzinfo is not None:
        midnight = midnight.replace(tzinfo=start.tzinfo)
    first_presence = max(0, int((midnight - start).total_seconds() // 60))
    first_worked = int(worked * first_presence / presence)
    second_worked = worked - first_worked
    return (
        DayPortion(start.date(), first_worked, holiday_type),
        DayPortion(end.date(), second_worked, next_holiday_type),
    )
