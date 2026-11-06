"""Leave requests, ledger, and balances. No FastAPI imports."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import DuplicateKeyError

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.errors import AppError
from app.core.money import D, money, money_str
from app.core.repository import TenantRepo, api
from app.domain.attendance import holiday_applies
from app.domain.leave import (
    BalanceProjection,
    LedgerEntry,
    can_debit,
    count_leave_days,
    project_balance,
    ranges_overlap,
    split_year_end,
)
from app.modules.attendance.models import (
    EmployeeSchedule,
    Holiday,
    OfficialBusiness,
    WfhRequest,
    WorkSchedule,
)
from app.modules.employees.models import Employee
from app.modules.leave.models import (
    LeaveBalance,
    LeaveBlackout,
    LeaveLedger,
    LeaveRequest,
    LeaveType,
)
from app.modules.leave.policies import (
    assert_can_cancel,
    assert_can_see,
    request_filter,
    require_company,
    require_reader,
    resolve_filer,
)
from app.modules.leave.schemas import (
    BalanceAdjust,
    LeaveBlackoutWrite,
    LeaveRequestCreate,
    LeaveTypeWrite,
)
from app.modules.organization.models import Branch, Company
from app.shared.approvals import handles, start_request
from app.shared.audit import write_audit
from app.shared.models import ApprovalRequest

logger = logging.getLogger("hris.leave")

_ACCRUAL = {"upfront", "monthly", "per_service_year"}
_NON_WORKING = {
    "regular",
    "special_non_working",
    "local",
    "local_regular",
    "local_special",
    "double_regular",
}
_SORTS = {"name", "code", "created_at", "start_date"}


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "Asia/Manila")
    except Exception:
        return ZoneInfo("Asia/Manila")


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _months_between(start: date, end: date) -> int:
    if end < start:
        return -1
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def _eligible(employee: Employee, months_needed: int, on: date) -> bool:
    if months_needed <= 0:
        return True
    if employee.date_hired is None:
        return False
    return _months_between(_as_date(employee.date_hired), on) >= months_needed


def _matches(actual: str, restriction: str) -> bool:
    if not restriction.strip():
        return True
    return actual.strip().casefold() == restriction.strip().casefold()


def _money_field(value: str, label: str) -> str:
    try:
        parsed = D(value)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise AppError("bad_days", f"{label} must be a decimal", 400) from exc
    if parsed < 0:
        raise AppError("bad_days", f"{label} cannot be negative", 400)
    return money_str(parsed)


def _normalize_type(body: LeaveTypeWrite) -> LeaveTypeWrite:
    if not body.code.strip() or not body.name.strip():
        raise AppError("bad_request", "Code and name are required", 400)
    if body.accrual_method not in _ACCRUAL:
        raise AppError("bad_accrual", "Accrual method is not recognized", 400)
    if body.eligibility_after_months < 0 or body.min_notice_days < 0:
        raise AppError("bad_request", "Months and notice days cannot be negative", 400)
    if body.carry_over_expiry_months < 0:
        raise AppError("bad_request", "Carry-over expiry cannot be negative", 400)
    tiers = []
    for tier in body.tenure_tiers:
        tiers.append(tier.model_copy(update={"days": _money_field(tier.days, "Tier days")}))
    return body.model_copy(
        update={
            "code": body.code.strip(),
            "name": body.name.strip(),
            "annual_entitlement": _money_field(body.annual_entitlement, "Entitlement"),
            "carry_over_max": _money_field(body.carry_over_max, "Carry over"),
            "max_conversion_days": _money_field(body.max_conversion_days, "Conversion"),
            "attachment_required_after_days": _money_field(
                body.attachment_required_after_days, "Attachment threshold"
            ),
            "tenure_tiers": tiers,
        }
    )


def _public_balance(balance: LeaveBalance) -> dict[str, Any]:
    data = api(balance)
    available = (
        D(balance.entitled)
        + D(balance.accrued)
        + D(balance.carried_over)
        + D(balance.adjusted)
        - D(balance.used)
    )
    data["available"] = money_str(available)
    return data


async def _conflict(awaitable: Any) -> Any:
    try:
        return await awaitable
    except DuplicateKeyError as exc:
        raise AppError("conflict", "That record already exists", 409) from exc


async def _employee(company_id: str, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if employee is None or employee.company_id != company_id or employee.deleted_at is not None:
        raise AppError("not_found", "Employee not found", 404)
    return employee


async def _zone_for(company_id: str) -> ZoneInfo:
    company = await Company.get(company_id)
    return _zone(company.timezone if company is not None else None)


async def list_leave_types(
    actor: Actor, page: int, page_size: int, q: str | None, sort: str | None
) -> dict[str, Any]:
    require_reader(actor)
    require_company(actor)
    return await TenantRepo(LeaveType, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("name", "code"),
        sort_fields=_SORTS,
        q=q,
        sort=sort or "name",
    )


async def get_leave_type(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await TenantRepo(LeaveType, actor).get(doc_id))


async def create_leave_type(actor: Actor, body: LeaveTypeWrite) -> dict[str, Any]:
    actor.require("leave.manage")
    require_company(actor)
    saved = await _conflict(TenantRepo(LeaveType, actor).create(_normalize_type(body)))
    return api(saved)


async def update_leave_type(actor: Actor, doc_id: str, body: LeaveTypeWrite) -> dict[str, Any]:
    actor.require("leave.manage")
    require_company(actor)
    saved = await _conflict(TenantRepo(LeaveType, actor).update(doc_id, _normalize_type(body)))
    return api(saved)


async def delete_leave_type(actor: Actor, doc_id: str) -> None:
    actor.require("leave.manage")
    require_company(actor)
    await TenantRepo(LeaveType, actor).soft_delete(doc_id)


def _check_blackout(body: LeaveBlackoutWrite) -> None:
    if body.end_date < body.start_date:
        raise AppError("bad_dates", "End date is before the start", 400)


async def list_blackouts(actor: Actor, page: int, page_size: int) -> dict[str, Any]:
    require_reader(actor)
    require_company(actor)
    return await TenantRepo(LeaveBlackout, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("reason",),
        sort_fields=_SORTS,
        q=None,
        sort="start_date",
    )


async def get_blackout(actor: Actor, doc_id: str) -> dict[str, Any]:
    require_reader(actor)
    return api(await TenantRepo(LeaveBlackout, actor).get(doc_id))


async def create_blackout(actor: Actor, body: LeaveBlackoutWrite) -> dict[str, Any]:
    actor.require("leave.manage")
    require_company(actor)
    _check_blackout(body)
    return api(await TenantRepo(LeaveBlackout, actor).create(body))


async def update_blackout(actor: Actor, doc_id: str, body: LeaveBlackoutWrite) -> dict[str, Any]:
    actor.require("leave.manage")
    require_company(actor)
    _check_blackout(body)
    return api(await TenantRepo(LeaveBlackout, actor).update(doc_id, body))


async def delete_blackout(actor: Actor, doc_id: str) -> None:
    actor.require("leave.manage")
    require_company(actor)
    await TenantRepo(LeaveBlackout, actor).soft_delete(doc_id)


async def _rest_days(company_id: str, employee_id: str, day: date) -> tuple[int, ...]:
    rows = await EmployeeSchedule.find(
        {"company_id": company_id, "employee_id": employee_id, "effective_from": {"$lte": day}}
    ).to_list()
    chosen: EmployeeSchedule | None = None
    for row in rows:
        if row.effective_to is not None and _as_date(row.effective_to) < day:
            continue
        if chosen is None or _as_date(row.effective_from) > _as_date(chosen.effective_from):
            chosen = row
    if chosen is None:
        return (5, 6)
    work = await WorkSchedule.get(chosen.work_schedule_id)
    if work is None or work.company_id != company_id or work.deleted_at is not None:
        return (5, 6)
    return tuple(int(item) for item in work.rest_days)


async def _holiday_dates(
    company_id: str, employee: Employee, start: date, end: date
) -> frozenset[date]:
    rows = await Holiday.find(
        {
            "company_id": company_id,
            "deleted_at": None,
            "date": {"$gte": start, "$lte": end},
        }
    ).to_list()
    branch_id = employee.branch_id
    city: str | None = None
    if branch_id:
        branch = await Branch.get(branch_id)
        if branch is None or branch.company_id != company_id or branch.deleted_at is not None:
            branch_id = None
        else:
            city = branch.city.strip() or None
    # Special working days are work days, so leave is still charged.
    found: set[date] = set()
    for holiday in rows:
        if holiday.type not in _NON_WORKING:
            continue
        applies = holiday_applies(
            holiday.scope,
            branch_id=branch_id,
            branch_city=city,
            branch_ids=tuple(holiday.branch_ids),
            cities=tuple(holiday.cities),
        )
        if applies:
            found.add(_as_date(holiday.date))
    return frozenset(found)


async def _assert_no_overlap(
    company_id: str, employee_id: str, start: date, end: date
) -> list[LeaveRequest]:
    pending = await LeaveRequest.find(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "status": {"$in": ["pending", "approved"]},
        }
    ).to_list()
    for other in pending:
        if ranges_overlap(start, end, _as_date(other.start_date), _as_date(other.end_date)):
            raise AppError("overlap", "Those dates overlap another leave request", 409)
    business = await OfficialBusiness.find(
        {"company_id": company_id, "employee_id": employee_id, "status": "approved"}
    ).to_list()
    for item in business:
        if ranges_overlap(start, end, _as_date(item.start_date), _as_date(item.end_date)):
            raise AppError("overlap", "Those dates overlap approved official business", 409)
    remote = await WfhRequest.find(
        {"company_id": company_id, "employee_id": employee_id, "status": "approved"}
    ).to_list()
    for item in remote:
        if ranges_overlap(start, end, _as_date(item.start_date), _as_date(item.end_date)):
            raise AppError("overlap", "Those dates overlap approved work from home", 409)
    return pending


def _available(balance: LeaveBalance | None) -> Decimal:
    if balance is None:
        return Decimal(0)
    return (
        D(balance.entitled)
        + D(balance.accrued)
        + D(balance.carried_over)
        + D(balance.adjusted)
        - D(balance.used)
    )


async def list_requests(
    actor: Actor,
    *,
    scope: str | None,
    employee_id: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    require_reader(actor)
    extra = await request_filter(actor, scope=scope, employee_id=employee_id)
    return await TenantRepo(LeaveRequest, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields=_SORTS,
        q=None,
        sort="-created_at",
        extra=extra,
    )


async def get_request(actor: Actor, request_id: str) -> dict[str, Any]:
    require_reader(actor)
    leave = await TenantRepo(LeaveRequest, actor).get(request_id)
    if not isinstance(leave, LeaveRequest):
        raise AppError("not_found", "Record not found", 404)
    await assert_can_see(actor, leave.employee_id)
    return api(leave)


async def create_request(actor: Actor, body: LeaveRequestCreate) -> dict[str, Any]:
    company_id = require_company(actor)
    employee_id = resolve_filer(actor, body.employee_id)
    employee = await _employee(company_id, employee_id)
    leave_type = await TenantRepo(LeaveType, actor).get(body.leave_type_id)
    if not isinstance(leave_type, LeaveType):
        raise AppError("not_found", "Leave type not found", 404)
    start = body.start_date
    end = body.end_date
    rest = await _rest_days(company_id, employee_id, start)
    holidays = await _holiday_dates(company_id, employee, start, end)
    try:
        counted = count_leave_days(
            start,
            end,
            rest_days=rest,
            holidays=holidays,
            counts_weekends=leave_type.counts_weekends,
            half_day=body.half_day,
        )
    except ValueError as exc:
        raise AppError("bad_dates", str(exc), 400) from exc
    if counted <= 0:
        raise AppError("bad_dates", "Those dates have no chargeable leave days", 400)
    if not _eligible(employee, leave_type.eligibility_after_months, start):
        raise AppError("not_eligible", "You are not eligible for this leave yet", 400)
    if not _matches(employee.gender, leave_type.gender_restriction):
        raise AppError("not_eligible", "This leave type does not apply to you", 400)
    if not _matches(employee.civil_status, leave_type.civil_status_restriction):
        raise AppError("not_eligible", "This leave type does not apply to you", 400)
    today = datetime.now(await _zone_for(company_id)).date()
    notice = leave_type.min_notice_days
    if notice > 0 and start < today + timedelta(days=notice):
        raise AppError("notice", "This leave needs more notice", 400)
    await _reject_blackout(company_id, employee, start, end)
    threshold = D(leave_type.attachment_required_after_days)
    if counted > threshold and not (body.attachment_key and body.attachment_key.strip()):
        raise AppError("attachment_required", "This leave needs an attachment", 400)
    pending = await _assert_no_overlap(company_id, employee_id, start, end)
    year = start.year
    balance = await LeaveBalance.find_one(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "leave_type_id": str(leave_type.id),
            "year": year,
        }
    )
    pending_days = Decimal(0)
    for other in pending:
        # Approved days are already in the cached used column.
        same_type = other.leave_type_id == str(leave_type.id)
        same_year = _as_date(other.start_date).year == year
        if other.status == "pending" and same_type and same_year:
            pending_days += D(other.days)
    if not can_debit(
        _available(balance) - pending_days, counted, leave_type.allow_negative_balance
    ):
        raise AppError("insufficient_balance", "Leave balance is not enough", 400)
    days = money_str(counted)
    doc = LeaveRequest(
        company_id=company_id,
        employee_id=employee_id,
        leave_type_id=str(leave_type.id),
        start_date=start,
        end_date=end,
        half_day=body.half_day,
        days=days,
        reason=body.reason,
        attachment_key=body.attachment_key,
        status="pending",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    async with transaction() as session:
        await doc.insert(session=session)
        approval = await start_request(
            actor=actor,
            module="leave",
            subject_type="leave_request",
            subject_id=str(doc.id),
            context={"employee_id": employee_id, "days": days},
            session=session,
        )
        fresh = await LeaveRequest.get(doc.id, session=session)
        if fresh is None:
            raise AppError("not_found", "Record not found", 404)
        fresh.approval_request_id = str(approval.id)
        if fresh.status == "pending" and approval.status != "pending":
            fresh.status = approval.status
        fresh.updated_at = utcnow()
        fresh.updated_by = actor.user_id
        await fresh.save(session=session)
        await write_audit(
            company_id=company_id,
            actor_id=actor.user_id,
            action="create",
            entity_type="leave_requests",
            entity_id=str(fresh.id),
            after=api(fresh),
            session=session,
        )
        return api(fresh)


async def _reject_blackout(company_id: str, employee: Employee, start: date, end: date) -> None:
    blackouts = await LeaveBlackout.find(
        {
            "company_id": company_id,
            "deleted_at": None,
            "start_date": {"$lte": end},
            "end_date": {"$gte": start},
        }
    ).to_list()
    for blackout in blackouts:
        if blackout.department_id and blackout.department_id != employee.department_id:
            continue
        if blackout.branch_id and blackout.branch_id != employee.branch_id:
            continue
        if ranges_overlap(start, end, _as_date(blackout.start_date), _as_date(blackout.end_date)):
            raise AppError("blackout", "Those dates are blocked for leave", 400)


async def _balance_row(
    company_id: str,
    employee_id: str,
    leave_type_id: str,
    year: int,
    session: AsyncClientSession,
) -> LeaveBalance | None:
    return await LeaveBalance.find_one(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "year": year,
        },
        session=session,
    )


def _set_bucket(balance: LeaveBalance, field: str, value: Decimal) -> None:
    rendered = money_str(value)
    if field == "entitled":
        balance.entitled = rendered
    elif field == "accrued":
        balance.accrued = rendered
    elif field == "used":
        balance.used = rendered
    elif field == "carried_over":
        balance.carried_over = rendered
    elif field == "adjusted":
        balance.adjusted = rendered
    else:
        raise AppError("bad_request", "Unknown balance field", 400)


async def _bump(
    company_id: str,
    employee_id: str,
    leave_type_id: str,
    year: int,
    field: str,
    delta: Decimal,
    session: AsyncClientSession,
) -> LeaveBalance:
    balance = await _balance_row(company_id, employee_id, leave_type_id, year, session)
    if balance is None:
        balance = LeaveBalance(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            year=year,
        )
        _set_bucket(balance, field, delta)
        await balance.insert(session=session)
        return balance
    current = D(getattr(balance, field))
    _set_bucket(balance, field, current + delta)
    await balance.save(session=session)
    return balance


async def _approve_leave(approval: ApprovalRequest, session: AsyncClientSession) -> None:
    leave = await LeaveRequest.get(approval.subject_id, session=session)
    if leave is None or leave.company_id != approval.company_id or leave.status == "cancelled":
        return
    year = _as_date(leave.start_date).year
    prior = await LeaveLedger.find_one(
        {"company_id": leave.company_id, "ref": str(leave.id), "entry_type": "usage"},
        session=session,
    )
    if prior is None:
        # Usage is stored negative so project_balance increases the used column.
        await LeaveLedger(
            company_id=leave.company_id,
            employee_id=leave.employee_id,
            leave_type_id=leave.leave_type_id,
            year=year,
            entry_type="usage",
            days=money_str(-D(leave.days)),
            ref=str(leave.id),
            at=utcnow(),
        ).insert(session=session)
        await _bump(
            leave.company_id,
            leave.employee_id,
            leave.leave_type_id,
            year,
            "used",
            D(leave.days),
            session,
        )
    leave.status = "approved"
    leave.updated_at = utcnow()
    await leave.save(session=session)


async def _set_leave_status(
    approval: ApprovalRequest, status: str, session: AsyncClientSession | None
) -> None:
    leave = await LeaveRequest.get(approval.subject_id, session=session)
    if leave is None or leave.company_id != approval.company_id or leave.status == "cancelled":
        return
    leave.status = status
    leave.updated_at = utcnow()
    await leave.save(session=session)


@handles("leave_request")
async def on_leave_request(approval: ApprovalRequest, session: AsyncClientSession | None) -> None:
    if approval.status == "approved":
        if session is None:
            async with transaction() as owned:
                await _approve_leave(approval, owned)
        else:
            await _approve_leave(approval, session)
        return
    if approval.status in {"rejected", "returned"}:
        await _set_leave_status(approval, approval.status, session)


async def _reverse_usage(leave: LeaveRequest, session: AsyncClientSession) -> None:
    prior = await LeaveLedger.find_one(
        {"company_id": leave.company_id, "ref": str(leave.id), "entry_type": "reversal"},
        session=session,
    )
    if prior is not None:
        return
    year = _as_date(leave.start_date).year
    await LeaveLedger(
        company_id=leave.company_id,
        employee_id=leave.employee_id,
        leave_type_id=leave.leave_type_id,
        year=year,
        entry_type="reversal",
        days=money_str(D(leave.days)),
        ref=str(leave.id),
        at=utcnow(),
    ).insert(session=session)
    balance = await _balance_row(
        leave.company_id, leave.employee_id, leave.leave_type_id, year, session
    )
    if balance is not None:
        balance.used = money_str(D(balance.used) - D(leave.days))
        await balance.save(session=session)


async def cancel_request(actor: Actor, request_id: str) -> dict[str, Any]:
    company_id = require_company(actor)
    async with transaction() as session:
        leave = await LeaveRequest.get(request_id, session=session)
        if leave is None or leave.company_id != company_id:
            raise AppError("not_found", "Record not found", 404)
        assert_can_cancel(actor, leave.employee_id)
        if leave.status in {"cancelled", "rejected"}:
            raise AppError("conflict", "This leave request cannot be cancelled", 409)
        if leave.status == "approved":
            await _reverse_usage(leave, session)
        leave.status = "cancelled"
        leave.updated_at = utcnow()
        leave.updated_by = actor.user_id
        await leave.save(session=session)
        await write_audit(
            company_id=company_id,
            actor_id=actor.user_id,
            action="update",
            entity_type="leave_requests",
            entity_id=str(leave.id),
            after=api(leave),
            session=session,
        )
        return api(leave)


async def list_balances(
    actor: Actor,
    employee_id: str | None,
    year: int | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    require_reader(actor)
    extra = await request_filter(actor, scope=None, employee_id=employee_id)
    if year is not None:
        extra["year"] = year
    result = await TenantRepo(LeaveBalance, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields={"year", "employee_id"},
        q=None,
        sort="year",
        extra=extra,
    )
    for item in result["items"]:
        available = (
            D(item["entitled"])
            + D(item["accrued"])
            + D(item["carried_over"])
            + D(item["adjusted"])
            - D(item["used"])
        )
        item["available"] = money_str(available)
    return result


async def adjust_balance(actor: Actor, body: BalanceAdjust) -> dict[str, Any]:
    actor.require("leave.manage")
    company_id = require_company(actor)
    await _employee(company_id, body.employee_id)
    await TenantRepo(LeaveType, actor).get(body.leave_type_id)
    try:
        delta = D(body.days)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise AppError("bad_days", "Days must be a decimal", 400) from exc
    if delta == 0:
        raise AppError("bad_days", "Adjustment days cannot be zero", 400)
    async with transaction() as session:
        await LeaveLedger(
            company_id=company_id,
            employee_id=body.employee_id,
            leave_type_id=body.leave_type_id,
            year=body.year,
            entry_type="adjustment",
            days=money_str(delta),
            ref=body.reason,
            at=utcnow(),
        ).insert(session=session)
        balance = await _bump(
            company_id,
            body.employee_id,
            body.leave_type_id,
            body.year,
            "adjusted",
            delta,
            session,
        )
        return _public_balance(balance)


async def _write_projection(
    company_id: str, key: tuple[str, str, int], projection: BalanceProjection
) -> None:
    employee_id, leave_type_id, year = key
    balance = await LeaveBalance.find_one(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "year": year,
        }
    )
    inserted = balance is None
    if balance is None:
        balance = LeaveBalance(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            year=year,
        )
    balance.entitled = money_str(projection.entitled)
    balance.accrued = money_str(projection.accrued)
    balance.used = money_str(projection.used)
    balance.carried_over = money_str(projection.carried_over)
    balance.adjusted = money_str(projection.adjusted)
    if inserted:
        await balance.insert()
    else:
        await balance.save()


async def rebuild_balances(company_id: str) -> None:
    rows = await LeaveLedger.find({"company_id": company_id}).to_list()
    grouped: dict[tuple[str, str, int], list[LedgerEntry]] = {}
    for row in rows:
        key = (row.employee_id, row.leave_type_id, row.year)
        grouped.setdefault(key, []).append(LedgerEntry(row.entry_type, D(row.days)))
    seen: set[tuple[str, str, int]] = set()
    for key, entries in grouped.items():
        seen.add(key)
        await _write_projection(company_id, key, project_balance(tuple(entries)))
    zero = money_str(Decimal(0))
    cached = await LeaveBalance.find({"company_id": company_id}).to_list()
    for balance in cached:
        key = (balance.employee_id, balance.leave_type_id, balance.year)
        if key in seen:
            continue
        balance.entitled = zero
        balance.accrued = zero
        balance.used = zero
        balance.carried_over = zero
        balance.adjusted = zero
        await balance.save()


async def _accrue_one(
    company_id: str,
    employee_id: str,
    leave_type: LeaveType,
    year: int,
    month: int,
    amount: Decimal,
) -> None:
    ref = f"accrual-{year:04d}-{month:02d}"
    async with transaction() as session:
        existing = await LeaveLedger.find_one(
            {
                "company_id": company_id,
                "employee_id": employee_id,
                "leave_type_id": str(leave_type.id),
                "entry_type": "accrual",
                "ref": ref,
            },
            session=session,
        )
        if existing is not None:
            return
        await LeaveLedger(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=str(leave_type.id),
            year=year,
            entry_type="accrual",
            days=money_str(amount),
            ref=ref,
            at=utcnow(),
        ).insert(session=session)
        await _bump(
            company_id,
            employee_id,
            str(leave_type.id),
            year,
            "accrued",
            amount,
            session,
        )


async def run_monthly_accrual() -> None:
    companies = await Company.find({"deleted_at": None, "is_active": True}).to_list()
    for company in companies:
        try:
            await _accrue_company(company)
        except Exception:
            logger.exception("leave accrual failed for %s", company.id)


async def _accrue_company(company: Company) -> None:
    today = datetime.now(_zone(company.timezone)).date()
    company_id = str(company.id)
    types = await LeaveType.find(
        {"company_id": company_id, "deleted_at": None, "accrual_method": "monthly"}
    ).to_list()
    if not types:
        return
    employees = await Employee.find(
        {"company_id": company_id, "deleted_at": None, "employment_status": "active"}
    ).to_list()
    for employee in employees:
        separated = (
            employee.separation_date is not None and _as_date(employee.separation_date) <= today
        )
        if separated:
            continue
        for leave_type in types:
            if not _eligible(employee, leave_type.eligibility_after_months, today):
                continue
            amount = money(D(leave_type.annual_entitlement) / Decimal(12))
            if amount <= 0:
                continue
            try:
                await _accrue_one(
                    company_id,
                    str(employee.id),
                    leave_type,
                    today.year,
                    today.month,
                    amount,
                )
            except Exception:
                logger.exception("leave accrual failed for %s type %s", employee.id, leave_type.id)


async def grant_upfront(employee_id: str) -> None:
    """Grant each upfront leave type once. Safe to call again; later calls no-op."""
    employee = await Employee.get(employee_id)
    if employee is None or employee.deleted_at is not None:
        raise AppError("not_found", "Employee not found", 404)
    today = datetime.now(await _zone_for(employee.company_id)).date()
    if employee.separation_date is not None and _as_date(employee.separation_date) <= today:
        return
    types = await LeaveType.find(
        {
            "company_id": employee.company_id,
            "deleted_at": None,
            "accrual_method": "upfront",
        }
    ).to_list()
    for leave_type in types:
        if not _eligible(employee, leave_type.eligibility_after_months, today):
            continue
        amount = money(D(leave_type.annual_entitlement))
        if amount <= 0:
            continue
        await _grant_one(employee, leave_type, today.year, amount)


async def _grant_one(employee: Employee, leave_type: LeaveType, year: int, amount: Decimal) -> None:
    async with transaction() as session:
        existing = await LeaveLedger.find_one(
            {
                "company_id": employee.company_id,
                "employee_id": str(employee.id),
                "leave_type_id": str(leave_type.id),
                "entry_type": "entitlement",
            },
            session=session,
        )
        if existing is not None:
            return
        await LeaveLedger(
            company_id=employee.company_id,
            employee_id=str(employee.id),
            leave_type_id=str(leave_type.id),
            year=year,
            entry_type="entitlement",
            days=money_str(amount),
            ref=f"upfront-{year:04d}",
            at=utcnow(),
        ).insert(session=session)
        await _bump(
            employee.company_id,
            str(employee.id),
            str(leave_type.id),
            year,
            "entitled",
            amount,
            session,
        )


async def calendar(actor: Actor, start: date, end: date) -> dict[str, Any]:
    if end < start:
        raise AppError("bad_dates", "Calendar end is before the start", 400)
    company_id = require_company(actor)
    require_reader(actor)
    extra = await request_filter(actor, scope=None, employee_id=None)
    query: dict[str, Any] = {
        "company_id": company_id,
        "status": {"$in": ["pending", "approved"]},
        "start_date": {"$lte": end},
        "end_date": {"$gte": start},
        **extra,
    }
    rows = await LeaveRequest.find(query).to_list()
    rows.sort(key=lambda row: (_as_date(row.start_date), row.employee_id))
    return {"items": [api(row) for row in rows[:500]]}


async def grant_company(company_id: str) -> int:
    employees = await Employee.find(
        {"company_id": company_id, "deleted_at": None, "employment_status": "active"}
    ).to_list()
    for employee in employees:
        await grant_upfront(str(employee.id))
    return len(employees)


def _year_end_ref(year: int, kind: str) -> str:
    return f"year-end-{year}-{kind}"


async def _ledger_exists(
    company_id: str,
    employee_id: str,
    leave_type_id: str,
    year: int,
    ref: str,
    session: AsyncClientSession,
) -> bool:
    found = await LeaveLedger.find_one(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "year": year,
            "ref": ref,
        },
        session=session,
    )
    return found is not None


async def _post_signed(
    *,
    company_id: str,
    employee_id: str,
    leave_type_id: str,
    year: int,
    entry_type: str,
    days: Decimal,
    ref: str,
    bucket: str,
    session: AsyncClientSession,
) -> None:
    if days == 0 or await _ledger_exists(
        company_id, employee_id, leave_type_id, year, ref, session
    ):
        return
    await LeaveLedger(
        company_id=company_id,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=year,
        entry_type=entry_type,
        days=money_str(days),
        ref=ref,
        at=utcnow(),
    ).insert(session=session)
    await _bump(company_id, employee_id, leave_type_id, year, bucket, days, session)


async def close_leave_year(company_id: str, year: int) -> int:
    """Move unused leave into carry, expiry, and taxable cash conversion.

    Conversion becomes a payroll adjustment only when a draft January period
    of the next year already exists. The ledger entry is written either way.
    """
    from app.modules.payroll.models import Adjustment, PayrollPeriod

    types = await LeaveType.find({"company_id": company_id, "deleted_at": None}).to_list()
    employees = await Employee.find(
        {"company_id": company_id, "deleted_at": None}
    ).to_list()
    periods = await PayrollPeriod.find(
        {"company_id": company_id, "status": "draft"}
    ).to_list()
    january = [row for row in periods if row.start.year == year + 1 and row.start.month == 1]
    january.sort(key=lambda row: row.start)
    period = january[0] if january else None
    closed = 0
    for employee in employees:
        daily = Decimal("0")
        if employee.current_compensation is not None:
            daily = D(employee.current_compensation.daily_rate)
        for leave_type in types:
            type_id = str(leave_type.id)
            rows = await LeaveLedger.find(
                {
                    "company_id": company_id,
                    "employee_id": str(employee.id),
                    "leave_type_id": type_id,
                    "year": year,
                }
            ).to_list()
            if not rows:
                continue
            projection = project_balance(
                tuple(LedgerEntry(row.entry_type, D(row.days)) for row in rows)
            )
            carry, expire, convert = split_year_end(
                projection.available,
                carry_over_max=D(leave_type.carry_over_max),
                convertible=leave_type.convertible_to_cash,
                max_conversion_days=D(leave_type.max_conversion_days),
            )
            if carry == 0 and expire == 0 and convert == 0:
                continue
            async with transaction() as session:
                await _post_signed(
                    company_id=company_id,
                    employee_id=str(employee.id),
                    leave_type_id=type_id,
                    year=year,
                    entry_type="carry_over",
                    days=-carry,
                    ref=_year_end_ref(year, "carry-out"),
                    bucket="carried_over",
                    session=session,
                )
                await _post_signed(
                    company_id=company_id,
                    employee_id=str(employee.id),
                    leave_type_id=type_id,
                    year=year + 1,
                    entry_type="carry_over",
                    days=carry,
                    ref=_year_end_ref(year, "carry-in"),
                    bucket="carried_over",
                    session=session,
                )
                await _post_signed(
                    company_id=company_id,
                    employee_id=str(employee.id),
                    leave_type_id=type_id,
                    year=year,
                    entry_type="expiry",
                    days=-expire,
                    ref=_year_end_ref(year, "expire"),
                    bucket="adjusted",
                    session=session,
                )
                await _post_signed(
                    company_id=company_id,
                    employee_id=str(employee.id),
                    leave_type_id=type_id,
                    year=year,
                    entry_type="conversion",
                    days=-convert,
                    ref=_year_end_ref(year, "convert"),
                    bucket="adjusted",
                    session=session,
                )
                if convert > 0 and period is not None and daily > 0:
                    label = f"Leave conversion {year}"
                    existing = await Adjustment.find_one(
                        {
                            "company_id": company_id,
                            "employee_id": str(employee.id),
                            "period_id": str(period.id),
                            "label": label,
                        },
                        session=session,
                    )
                    if existing is None:
                        await Adjustment(
                            company_id=company_id,
                            employee_id=str(employee.id),
                            period_id=str(period.id),
                            type="leave_conversion",
                            label=label,
                            amount=money(convert * daily),
                            is_taxable=True,
                        ).insert(session=session)
            closed += 1
    return closed


async def expire_carried_leave(today: date | None = None) -> int:
    """Expire leftover carried days once their type's expiry month has passed."""
    companies = await Company.find({"deleted_at": None, "is_active": True}).to_list()
    posted = 0
    for company in companies:
        day = today or datetime.now(_zone(company.timezone)).date()
        company_id = str(company.id)
        types = await LeaveType.find(
            {"company_id": company_id, "deleted_at": None}
        ).to_list()
        for leave_type in types:
            months = leave_type.carry_over_expiry_months
            if months <= 0 or months >= 12 or day.month <= months:
                continue
            balances = await LeaveBalance.find(
                {
                    "company_id": company_id,
                    "leave_type_id": str(leave_type.id),
                    "year": day.year,
                }
            ).to_list()
            for balance in balances:
                rows = await LeaveLedger.find(
                    {
                        "company_id": company_id,
                        "employee_id": balance.employee_id,
                        "leave_type_id": str(leave_type.id),
                        "year": day.year,
                    }
                ).to_list()
                projection = project_balance(
                    tuple(LedgerEntry(row.entry_type, D(row.days)) for row in rows)
                )
                amount = min(projection.carried_over, projection.available)
                if amount <= 0:
                    continue
                async with transaction() as session:
                    before = await _ledger_exists(
                        company_id,
                        balance.employee_id,
                        str(leave_type.id),
                        day.year,
                        f"carry-expiry-{day.year}",
                        session,
                    )
                    if before:
                        continue
                    await _post_signed(
                        company_id=company_id,
                        employee_id=balance.employee_id,
                        leave_type_id=str(leave_type.id),
                        year=day.year,
                        entry_type="expiry",
                        days=-amount,
                        ref=f"carry-expiry-{day.year}",
                        bucket="adjusted",
                        session=session,
                    )
                posted += 1
    return posted
