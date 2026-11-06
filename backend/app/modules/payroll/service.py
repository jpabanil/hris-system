"""Payroll use cases. No FastAPI imports. The engine stays pure."""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from html import escape

from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.errors import AppError
from app.core.money import D, money, money_str
from app.core.repository import TenantRepo, api
from app.domain.annualization import TaxBracket
from app.domain.contributions import (
    StatutoryAmount,
    pagibig_amount,
    philhealth_amount,
    portion,
    sss_amount,
)
from app.domain.payroll_engine import (
    AdjustmentInput,
    AllowanceInput,
    ClaimInput,
    OtherDeduction,
    PayLine,
    PayrollInput,
    PremiumInput,
    SalarySlice,
    compute_payroll,
)
from app.domain.payroll_engine import (
    Ytd as EngineYtd,
)
from app.modules.attendance.models import AttendanceDay
from app.modules.claims.models import CashAdvance, Claim, ClaimType
from app.modules.employees.models import (
    AllowanceType,
    CompensationHistory,
    Employee,
    EmployeeAllowance,
    EmployeeSensitive,
)
from app.modules.leave.models import LeaveRequest, LeaveType
from app.modules.payroll import policies
from app.modules.payroll.models import (
    Adjustment,
    ContributionTable,
    Loan,
    LoanPayment,
    PayGroup,
    PayrollPeriod,
    PayrollRun,
    Payslip,
    PayslipLine,
    RecurringDeduction,
    RetroAdjustment,
    TaxTable,
    YtdOpening,
)
from app.modules.payroll.schemas import (
    AdjustmentWrite,
    ContributionTableWrite,
    LoanWrite,
    PayGroupWrite,
    PayrollPeriodWrite,
    RecurringDeductionWrite,
    TaxTableWrite,
)
from app.shared.approvals import start_request
from app.shared.audit import write_audit
from app.shared.settings_store import PayrollSettings, get_settings_model

logger = logging.getLogger(__name__)

_PERIODS = {"monthly": 12, "semi_monthly": 24, "weekly": 52}
_CLOSED = {"approved", "released", "locked"}
_PERIOD_TYPES = {"regular", "special", "13th_month", "final_pay", "bonus"}
_LOAN_KINDS = {
    "sss_salary": "sss_loan",
    "sss_calamity": "sss_loan",
    "pagibig_mpl": "pagibig_loan",
    "pagibig_calamity": "pagibig_loan",
    "company": "company_loan",
    "cash_advance": "cash_advance",
}
_DEDUCTION_ORDER = (
    "sss",
    "philhealth",
    "pagibig",
    "tax",
    "sss_loan",
    "pagibig_loan",
    "company_loan",
    "cash_advance",
    "recurring",
    "other",
)
_HOLIDAY_DAY = {
    "regular": ("regular_holiday", "Regular holiday premium", "2.00", True),
    "local_regular": ("regular_holiday", "Regular holiday premium", "2.00", True),
    "double_regular": ("double_regular", "Double holiday premium", "3.00", True),
    "special_non_working": ("special_non_working", "Special non-working premium", "1.30", False),
    "local_special": ("special_non_working", "Special non-working premium", "1.30", False),
}


def _frequency(value: str) -> str:
    if value not in _PERIODS:
        raise AppError("bad_frequency", "Frequency must be weekly, semi_monthly, or monthly", 400)
    return value


def _period_type(value: str) -> str:
    if value not in _PERIOD_TYPES:
        raise AppError("bad_type", "Unsupported payroll period type", 400)
    return value


async def _settings(company_id: str) -> PayrollSettings:
    loaded = await get_settings_model(company_id, "payroll")
    if isinstance(loaded, PayrollSettings):
        return loaded
    return PayrollSettings.model_validate(loaded.model_dump())


async def _employee(actor: Actor, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if (
        employee is None
        or employee.company_id != actor.company_id
        or employee.deleted_at is not None
    ):
        raise AppError("not_found", "Employee not found", 404)
    return employee


async def _period(actor: Actor, period_id: str) -> PayrollPeriod:
    period = await TenantRepo(PayrollPeriod, actor).get(period_id)
    if not isinstance(period, PayrollPeriod):
        raise AppError("not_found", "Payroll period not found", 404)
    return period


def _reject_closed(period: PayrollPeriod) -> None:
    if period.status in _CLOSED:
        raise AppError(
            "conflict",
            "Approved, released, and locked periods cannot be recomputed",
            409,
        )
    if period.type == "final_pay":
        raise AppError("bad_request", "Final pay is not computed here", 400)


def _workflow(period: PayrollPeriod, run: PayrollRun | None = None) -> dict:
    body = api(period)
    if run is not None:
        body["run_id"] = str(run.id)
        body["computed_by"] = run.computed_by
        body["approved_by"] = run.approved_by
        body["run_status"] = run.status
    return body


async def _audit(actor: Actor, action: str, entity_type: str, entity_id: str, after: dict) -> None:
    await write_audit(
        company_id=actor.company_id,
        actor_id=actor.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        after=after,
    )


# --- reference data ---------------------------------------------------------


async def list_pay_groups(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_view(actor)
    return await TenantRepo(PayGroup, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("name",),
        sort_fields={"created_at", "name"},
        q=q,
        sort="name",
    )


async def create_pay_group(actor: Actor, body: PayGroupWrite) -> dict:
    policies.require_compute(actor)
    _frequency(body.frequency)
    doc = await TenantRepo(PayGroup, actor).create(body)
    return api(doc)


async def get_pay_group(actor: Actor, group_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(PayGroup, actor).get(group_id))


async def update_pay_group(actor: Actor, group_id: str, body: PayGroupWrite) -> dict:
    policies.require_compute(actor)
    _frequency(body.frequency)
    doc = await TenantRepo(PayGroup, actor).update(group_id, body)
    return api(doc)


async def delete_pay_group(actor: Actor, group_id: str) -> None:
    policies.require_compute(actor)
    await TenantRepo(PayGroup, actor).soft_delete(group_id)


async def list_periods(
    actor: Actor,
    page: int,
    page_size: int,
    q: str | None,
    pay_group_id: str | None,
) -> dict:
    policies.require_view(actor)
    extra = {"pay_group_id": pay_group_id} if pay_group_id else None
    return await TenantRepo(PayrollPeriod, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("status", "type"),
        sort_fields={"created_at", "start", "pay_date", "status"},
        q=q,
        sort="-start",
        extra=extra,
    )


async def create_period(actor: Actor, body: PayrollPeriodWrite) -> dict:
    policies.require_compute(actor)
    _period_type(body.type)
    if body.end < body.start or body.period_index < 1 or body.periods_in_month < 1:
        raise AppError("bad_period", "Period dates or index are not valid", 400)
    await TenantRepo(PayGroup, actor).get(body.pay_group_id)
    doc = await TenantRepo(PayrollPeriod, actor).create(body)
    return api(doc)


async def get_period(actor: Actor, period_id: str) -> dict:
    policies.require_view(actor)
    return api(await _period(actor, period_id))


async def update_period(actor: Actor, period_id: str, body: PayrollPeriodWrite) -> dict:
    policies.require_compute(actor)
    period = await _period(actor, period_id)
    if period.status in _CLOSED:
        raise AppError("conflict", "This period can no longer be edited", 409)
    _period_type(body.type)
    if body.end < body.start or body.period_index < 1 or body.periods_in_month < 1:
        raise AppError("bad_period", "Period dates or index are not valid", 400)
    await TenantRepo(PayGroup, actor).get(body.pay_group_id)
    doc = await TenantRepo(PayrollPeriod, actor).update(period_id, body)
    return api(doc)


async def delete_period(actor: Actor, period_id: str) -> None:
    policies.require_compute(actor)
    period = await _period(actor, period_id)
    if period.status != "draft":
        raise AppError("conflict", "Only a draft period can be deleted", 409)
    await period.delete()


async def list_loans(
    actor: Actor,
    page: int,
    page_size: int,
    q: str | None,
    employee_id: str | None,
    status: str | None,
) -> dict:
    policies.require_view(actor)
    extra: dict[str, str] = {}
    if employee_id:
        extra["employee_id"] = employee_id
    if status:
        extra["status"] = status
    return await TenantRepo(Loan, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("reference_no", "type"),
        sort_fields={"created_at", "type", "status"},
        q=q,
        sort="-created_at",
        extra=extra or None,
    )


async def create_loan(actor: Actor, body: LoanWrite) -> dict:
    policies.require_compute(actor)
    await _employee(actor, body.employee_id)
    balance = body.principal if body.balance is None else body.balance
    loan = Loan(
        company_id=policies.company_id(actor),
        employee_id=body.employee_id,
        type=body.type,
        reference_no=body.reference_no,
        principal=money(body.principal),
        amortization=money(body.amortization),
        balance=money(balance),
        start_period_id=body.start_period_id,
        end_period_id=body.end_period_id,
        status=body.status or "active",
        can_pause=body.can_pause,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await loan.insert()
    await _audit(actor, "create", "loans", str(loan.id), api(loan))
    return api(loan)


async def get_loan(actor: Actor, loan_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(Loan, actor).get(loan_id))


async def update_loan(actor: Actor, loan_id: str, body: LoanWrite) -> dict:
    policies.require_compute(actor)
    loan = await TenantRepo(Loan, actor).get(loan_id)
    if not isinstance(loan, Loan):
        raise AppError("not_found", "Loan not found", 404)
    data = body.model_dump(exclude_unset=True)
    if data.get("employee_id"):
        await _employee(actor, data["employee_id"])
    for key in ("principal", "amortization", "balance"):
        if data.get(key) is not None:
            data[key] = money(data[key])
    for key, value in data.items():
        if value is None and key == "balance":
            continue
        setattr(loan, key, value)
    loan.updated_at = utcnow()
    loan.updated_by = actor.user_id
    await loan.save()
    await _audit(actor, "update", "loans", str(loan.id), api(loan))
    return api(loan)


async def delete_loan(actor: Actor, loan_id: str) -> None:
    policies.require_compute(actor)
    loan = await TenantRepo(Loan, actor).get(loan_id)
    paid = await LoanPayment.find(
        {"company_id": policies.company_id(actor), "loan_id": loan_id}
    ).to_list()
    if paid:
        raise AppError("conflict", "This loan already has payments", 409)
    await loan.delete()


async def list_recurring(
    actor: Actor, page: int, page_size: int, q: str | None, employee_id: str | None
) -> dict:
    policies.require_view(actor)
    extra = {"employee_id": employee_id} if employee_id else None
    return await TenantRepo(RecurringDeduction, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("type", "label"),
        sort_fields={"created_at", "type"},
        q=q,
        sort="-created_at",
        extra=extra,
    )


async def create_recurring(actor: Actor, body: RecurringDeductionWrite) -> dict:
    policies.require_compute(actor)
    await _employee(actor, body.employee_id)
    doc = await TenantRepo(RecurringDeduction, actor).create(body)
    return api(doc)


async def update_recurring(actor: Actor, deduction_id: str, body: RecurringDeductionWrite) -> dict:
    policies.require_compute(actor)
    await _employee(actor, body.employee_id)
    doc = await TenantRepo(RecurringDeduction, actor).update(deduction_id, body)
    return api(doc)


async def delete_recurring(actor: Actor, deduction_id: str) -> None:
    policies.require_compute(actor)
    doc = await TenantRepo(RecurringDeduction, actor).get(deduction_id)
    await doc.delete()


async def list_adjustments(
    actor: Actor, page: int, page_size: int, q: str | None, period_id: str | None
) -> dict:
    policies.require_view(actor)
    extra = {"period_id": period_id} if period_id else None
    return await TenantRepo(Adjustment, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("label", "type"),
        sort_fields={"created_at", "type"},
        q=q,
        sort="-created_at",
        extra=extra,
    )


async def create_adjustment(actor: Actor, body: AdjustmentWrite) -> dict:
    policies.require_compute(actor)
    await _employee(actor, body.employee_id)
    await _period(actor, body.period_id)
    doc = await TenantRepo(Adjustment, actor).create(body)
    return api(doc)


async def update_adjustment(actor: Actor, adjustment_id: str, body: AdjustmentWrite) -> dict:
    policies.require_compute(actor)
    await _employee(actor, body.employee_id)
    await _period(actor, body.period_id)
    doc = await TenantRepo(Adjustment, actor).update(adjustment_id, body)
    return api(doc)


async def delete_adjustment(actor: Actor, adjustment_id: str) -> None:
    policies.require_compute(actor)
    doc = await TenantRepo(Adjustment, actor).get(adjustment_id)
    await doc.delete()


async def list_contribution_tables(actor: Actor, page: int, page_size: int) -> dict:
    policies.require_view(actor)
    return await TenantRepo(ContributionTable, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("agency",),
        sort_fields={"created_at", "effective_from", "agency"},
        q=None,
        sort="-effective_from",
    )


async def create_contribution_table(actor: Actor, body: ContributionTableWrite) -> dict:
    policies.require_tables(actor)
    if body.agency not in {"sss", "philhealth", "pagibig"}:
        raise AppError("bad_agency", "Agency must be sss, philhealth, or pagibig", 400)
    doc = await TenantRepo(ContributionTable, actor).create(body)
    return api(doc)


async def update_contribution_table(
    actor: Actor, table_id: str, body: ContributionTableWrite
) -> dict:
    policies.require_tables(actor)
    doc = await TenantRepo(ContributionTable, actor).update(table_id, body)
    return api(doc)


async def list_tax_tables(actor: Actor, page: int, page_size: int) -> dict:
    policies.require_view(actor)
    return await TenantRepo(TaxTable, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("frequency",),
        sort_fields={"created_at", "effective_from", "frequency"},
        q=None,
        sort="-effective_from",
    )


async def create_tax_table(actor: Actor, body: TaxTableWrite) -> dict:
    policies.require_tables(actor)
    doc = await TenantRepo(TaxTable, actor).create(body)
    return api(doc)


async def update_tax_table(actor: Actor, table_id: str, body: TaxTableWrite) -> dict:
    policies.require_tables(actor)
    doc = await TenantRepo(TaxTable, actor).update(table_id, body)
    return api(doc)


# --- compute ----------------------------------------------------------------


async def latest_runs(company_id: str, period_ids: list[str]) -> dict[str, PayrollRun]:
    if not period_ids:
        return {}
    runs = await PayrollRun.find(
        {"company_id": company_id, "period_id": {"$in": period_ids}}
    ).to_list()
    chosen: dict[str, PayrollRun] = {}
    for run in runs:
        current = chosen.get(run.period_id)
        if current is None or run.version > current.version:
            chosen[run.period_id] = run
    return chosen


async def latest_run(company_id: str, period_id: str) -> PayrollRun | None:
    found = await latest_runs(company_id, [period_id])
    return found.get(period_id)


async def _tax_table(company_id: str, frequency: str, as_of: date) -> TaxTable:
    rows = await TaxTable.find({"company_id": company_id, "frequency": frequency}).to_list()
    chosen = [row for row in rows if row.effective_from <= as_of]
    if not chosen:
        raise AppError("tax_table_missing", "Tax table is missing for this pay frequency", 400)
    chosen.sort(key=lambda row: row.effective_from, reverse=True)
    table = chosen[0]
    if not table.brackets:
        raise AppError("tax_table_missing", "Tax table has no brackets", 400)
    return table


def _brackets(table: TaxTable) -> tuple[TaxBracket, ...]:
    return tuple(
        TaxBracket(start=D(row.start), base_tax=D(row.base_tax), rate=D(row.rate))
        for row in table.brackets
    )


def _multiplier(table: dict[str, str], key: str, default: str) -> Decimal:
    raw = table.get(key) if table else None
    if raw is None or str(raw).strip() == "":
        raw = default
    return D(str(raw))


def _paid_day_extra(full: Decimal) -> Decimal:
    """Full statutory factor includes the paid day. The engine wants only the extra."""
    if full > Decimal("1"):
        return full - Decimal("1")
    return full


def _minutes(hours: object) -> int:
    counted = D(hours or 0) * Decimal(60)
    return int(counted.to_integral_value(rounding=ROUND_HALF_UP))


def _portion_minutes(value: object) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        raise AppError("bad_attendance", "Attendance minutes must not be float", 400)
    if isinstance(value, int):
        return value
    if value is None or value == "":
        return 0
    return int(D(value))


def _holiday_minutes(day: AttendanceDay) -> tuple[str, int]:
    total = 0
    chosen = "none"
    for part in day.portions or []:
        if not isinstance(part, dict):
            continue
        kind = str(part.get("holiday_type") or "none")
        if kind in {"none", "special_working", ""}:
            continue
        total += _portion_minutes(part.get("minutes"))
        chosen = kind
    if total > 0:
        return chosen, total
    kind = day.holiday_type or "none"
    if kind in {"none", "special_working", ""}:
        return "none", 0
    return kind, _minutes(day.hours_worked)


def _ot_choice(holiday: str, rest: bool) -> tuple[str, str, str]:
    if holiday in {"regular", "local_regular", "double_regular"}:
        return ("regular_holiday_ot", "Holiday OT", "2.60")
    if holiday in {"special_non_working", "local_special"}:
        return ("special_non_working_ot", "Special non-working OT", "1.69")
    if rest:
        return ("rest_day_ot", "Rest day OT", "1.69")
    return ("regular_ot", "Regular OT", "1.25")


def _premiums(days: list[AttendanceDay], multipliers: dict[str, str]) -> tuple[PremiumInput, ...]:
    buckets: dict[tuple[str, str, Decimal], int] = {}

    def add(code: str, label: str, minutes: int, factor: Decimal) -> None:
        if minutes <= 0 or factor == 0:
            return
        key = (code, label, factor)
        buckets[key] = buckets.get(key, 0) + minutes

    for day in days:
        night = _multiplier(multipliers, "night_diff", "0.10")
        add("night_diff", "Night differential", day.night_diff_minutes or 0, night)
        holiday, holiday_mins = _holiday_minutes(day)
        ot_holiday = holiday if holiday != "none" else (day.holiday_type or "none")
        ot_minutes = day.overtime_minutes or 0
        if ot_minutes > 0:
            code, label, default = _ot_choice(ot_holiday, day.is_rest_day)
            add(code, label, ot_minutes, _multiplier(multipliers, code, default))
        rest_key = "regular_holiday_rest" if day.is_rest_day and holiday in {
            "regular",
            "local_regular",
        } else None
        if holiday not in {"none", "special_working"}:
            if rest_key:
                full = _multiplier(multipliers, rest_key, "2.60")
                factor = _paid_day_extra(full)
                code, label = rest_key, "Regular holiday on rest day"
            else:
                spec = _HOLIDAY_DAY.get(holiday)
                if spec is None:
                    continue
                code, label, default, as_extra = spec
                full = _multiplier(multipliers, code, default)
                factor = _paid_day_extra(full) if as_extra else full
            add(code, label, max(0, holiday_mins - ot_minutes), factor)
        elif day.is_rest_day:
            full = _multiplier(multipliers, "rest_day", "1.30")
            worked = max(0, _minutes(day.hours_worked) - ot_minutes)
            add("rest_day", "Rest day premium", worked, full)
    return tuple(
        PremiumInput(code=code, label=label, minutes=minutes, multiplier=factor)
        for (code, label, factor), minutes in buckets.items()
    )


def _employment_window(employee: Employee, period: PayrollPeriod) -> tuple[date, date]:
    start = period.start
    end = period.end
    if employee.date_hired and employee.date_hired > start:
        start = employee.date_hired
    if employee.separation_date and employee.separation_date < end:
        end = employee.separation_date
    return start, end


def _prorate_days(employee: Employee, period: PayrollPeriod, working: Decimal) -> Decimal:
    span = (period.end - period.start).days + 1
    if span <= 0:
        return working
    start, end = _employment_window(employee, period)
    if start > end:
        return Decimal("0")
    if start == period.start and end == period.end:
        return working
    covered = (end - start).days + 1
    return D(working) * Decimal(covered) / Decimal(span)


def _salary_slices(
    history: list[CompensationHistory],
    employee: Employee,
    period: PayrollPeriod,
    working: Decimal,
) -> tuple[SalarySlice, ...]:
    rows = sorted(history, key=lambda item: item.effective_date)
    window_start, window_end = _employment_window(employee, period)
    if window_start > window_end:
        return ()
    applicable = [row for row in rows if row.effective_date <= window_end]
    inside = [row for row in applicable if row.effective_date > window_start]
    if not inside:
        return ()
    boundaries = [window_start]
    for row in inside:
        if row.effective_date not in boundaries:
            boundaries.append(row.effective_date)
    boundaries.append(window_end + timedelta(days=1))
    full_span = Decimal((period.end - period.start).days + 1)
    window_span = Decimal((window_end - window_start).days + 1)
    if full_span <= 0 or window_span <= 0:
        return ()
    employed_days = working * window_span / full_span
    built: list[SalarySlice] = []
    for index in range(len(boundaries) - 1):
        seg_start = boundaries[index]
        seg_days = Decimal((boundaries[index + 1] - seg_start).days)
        if seg_days <= 0:
            continue
        rate_row = None
        for row in applicable:
            if row.effective_date <= seg_start:
                rate_row = row
        if rate_row is None:
            return ()
        built.append(
            SalarySlice(
                daily_rate=D(rate_row.daily_rate),
                days=employed_days * seg_days / window_span,
            )
        )
    return tuple(built)


def _ytd_from_dict(data: dict | None) -> EngineYtd:
    source = data or {}

    def pick(key: str) -> Decimal:
        value = source.get(key)
        if value is None or value == "":
            return Decimal("0")
        return D(value)

    return EngineYtd(
        gross=pick("gross"),
        taxable=pick("taxable"),
        non_taxable=pick("non_taxable"),
        contributions=pick("contributions"),
        tax_withheld=pick("tax_withheld"),
        thirteenth_and_other_benefits=pick("thirteenth_and_other_benefits"),
        basic=pick("basic"),
    )


def _ytd_from_opening(opening: YtdOpening | None) -> EngineYtd:
    if opening is None:
        return EngineYtd()
    return EngineYtd(
        gross=D(opening.gross),
        taxable=D(opening.taxable),
        non_taxable=D(opening.non_taxable),
        contributions=D(opening.contributions),
        tax_withheld=D(opening.tax_withheld),
        thirteenth_and_other_benefits=D(opening.thirteenth_and_other_benefits),
        basic=D(opening.basic),
    )


def _dump_ytd(ytd: EngineYtd) -> dict[str, str]:
    return {
        "gross": money_str(ytd.gross),
        "taxable": money_str(ytd.taxable),
        "non_taxable": money_str(ytd.non_taxable),
        "contributions": money_str(ytd.contributions),
        "tax_withheld": money_str(ytd.tax_withheld),
        "thirteenth_and_other_benefits": money_str(ytd.thirteenth_and_other_benefits),
        "basic": money_str(ytd.basic),
    }


def _stat_dict(
    amount: StatutoryAmount, timing: str, index: int, count: int
) -> dict[str, str]:
    return {
        "ee": money_str(amount.ee),
        "er": money_str(amount.er),
        "ec": money_str(amount.ec),
        "mpf": money_str(amount.mpf),
        "mpf_er": money_str(amount.mpf_er),
        "basis": money_str(amount.basis),
        "ee_period": money_str(portion(amount.ee, timing, index, count)),
        "er_period": money_str(portion(amount.er, timing, index, count)),
        "ec_period": money_str(portion(amount.ec, timing, index, count)),
        "mpf_period": money_str(portion(amount.mpf, timing, index, count)),
        "mpf_er_period": money_str(portion(amount.mpf_er, timing, index, count)),
    }


def _monthly_compensation(
    basis: str, basic: Decimal, daily: Decimal, hourly: Decimal, factor_days: int
) -> Decimal:
    if basis == "monthly":
        return money(basic)
    if basis == "daily":
        return money(D(daily) * Decimal(factor_days) / Decimal(12))
    if basis == "hourly":
        return money(D(hourly) * Decimal(8) * Decimal(factor_days) / Decimal(12))
    raise AppError("bad_basis", f"Unknown pay basis {basis}", 400)


def _to_line(line: PayLine, cost_center_id: str | None) -> PayslipLine:
    return PayslipLine(
        type=line.type,
        code=line.code,
        label=line.label,
        quantity=line.quantity,
        rate=line.rate,
        amount=line.amount,
        is_taxable=line.is_taxable,
        deferred=line.deferred,
        cost_center_id=cost_center_id,
        ref_id=line.ref_id,
    )


def _loan_applies(
    loan: Loan, period: PayrollPeriod, periods: dict[str, PayrollPeriod]
) -> bool:
    if loan.status != "active" or D(loan.balance) <= 0 or D(loan.amortization) <= 0:
        return False
    if loan.start_period_id:
        start = periods.get(loan.start_period_id)
        if start is not None and period.start < start.start:
            return False
    if loan.end_period_id:
        end = periods.get(loan.end_period_id)
        if end is not None and period.start > end.end:
            return False
    return True


def _in_job(employee: Employee, day: date) -> bool:
    if employee.date_hired and day < employee.date_hired:
        return False
    if employee.separation_date and day > employee.separation_date:
        return False
    return True


def _lwop_days(
    employee_id: str,
    period: PayrollPeriod,
    requests: list[LeaveRequest],
    types: dict[str, LeaveType],
) -> tuple[Decimal, set[date]]:
    total = Decimal("0")
    covered: set[date] = set()
    for request in requests:
        if request.employee_id != employee_id or request.status != "approved":
            continue
        leave_type = types.get(request.leave_type_id)
        if leave_type is None or leave_type.is_paid:
            continue
        if request.end_date < period.start or request.start_date > period.end:
            continue
        span = Decimal((request.end_date - request.start_date).days + 1)
        if span <= 0:
            continue
        overlap_dates = []
        cursor = max(request.start_date, period.start)
        stop = min(request.end_date, period.end)
        while cursor <= stop:
            overlap_dates.append(cursor)
            cursor += timedelta(days=1)
        if not overlap_dates:
            continue
        total += D(request.days or 0) * Decimal(len(overlap_dates)) / span
        covered.update(overlap_dates)
    return total, covered


def _allowance_inputs(
    employee_id: str,
    period: PayrollPeriod,
    period_index: int,
    periods_in_month: int,
    allowances: list[EmployeeAllowance],
    types: dict[str, AllowanceType],
    prior_slips: list[Payslip],
) -> tuple[AllowanceInput, ...]:
    codes_by_category: dict[str, set[str]] = defaultdict(set)
    for item in types.values():
        if item.de_minimis_category:
            codes_by_category[item.de_minimis_category].add(item.code)
    built: list[AllowanceInput] = []
    for allowance in allowances:
        if allowance.employee_id != employee_id:
            continue
        if allowance.effective_from > period.end:
            continue
        if allowance.effective_to and allowance.effective_to < period.start:
            continue
        if allowance.frequency in {"monthly", "once_a_month"} and periods_in_month > 1:
            if period_index != 1:
                continue
        atype = types.get(allowance.allowance_type_id)
        code = atype.code if atype else f"allowance_{allowance.id}"
        label = atype.name if atype else "Allowance"
        ceiling = D(atype.annual_ceiling) if atype and atype.annual_ceiling is not None else None
        category = atype.de_minimis_category if atype else None
        used = Decimal("0")
        if category:
            nontax_codes = {f"{item}_nontax" for item in codes_by_category.get(category, set())}
            for slip in prior_slips:
                for line in slip.lines:
                    if line.code in nontax_codes:
                        used += D(line.amount)
        built.append(
            AllowanceInput(
                code=code,
                label=label,
                amount=D(allowance.amount),
                taxable=(allowance.taxability or "taxable") == "taxable",
                de_minimis_category=category,
                annual_ceiling=ceiling,
                ytd_in_category=used,
            )
        )
    return tuple(built)


async def compute_period(actor: Actor, period_id: str) -> dict:
    from app.modules.identity.service import block_payroll_if_impersonating

    block_payroll_if_impersonating(actor)
    policies.require_compute(actor)
    period = await _period(actor, period_id)
    _reject_closed(period)
    company = policies.company_id(actor)
    group = await PayGroup.get(period.pay_group_id)
    if group is None or group.company_id != company or group.deleted_at is not None:
        raise AppError("not_found", "Pay group not found", 404)
    frequency = _frequency(group.frequency)
    await _tax_table(company, frequency, period.end)
    roster = await Employee.find(
        {
            "company_id": company,
            "pay_group_id": str(group.id),
            "employment_status": "active",
            "deleted_at": None,
        }
    ).to_list()
    missing_pay = [item.employee_no for item in roster if item.current_compensation is None]
    if missing_pay:
        raise AppError(
            "compensation_missing",
            "Active employees are missing compensation",
            400,
            {"employee_nos": missing_pay},
        )
    existing = await PayrollRun.find({"company_id": company, "period_id": str(period.id)}).to_list()
    version = max((run.version for run in existing), default=0) + 1
    run = PayrollRun(
        company_id=company,
        period_id=str(period.id),
        version=version,
        computed_by=actor.user_id,
        computed_at=utcnow(),
        status="processing",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await run.insert()
    await _audit(actor, "compute", "payroll_runs", str(run.id), api(run))
    from app.modules.payroll.tasks import compute_run

    await compute_run(str(run.id))
    fresh = await PayrollRun.get(str(run.id))
    period_fresh = await PayrollPeriod.get(str(period.id))
    if fresh is None or period_fresh is None:
        raise AppError("not_found", "Payroll run not found", 404)
    body = api(fresh)
    body["period_status"] = period_fresh.status
    return body


async def execute_compute(run_id: str) -> None:
    run = await PayrollRun.get(run_id)
    if run is None:
        raise AppError("not_found", "Payroll run not found", 404)
    company = run.company_id
    period = await PayrollPeriod.get(run.period_id)
    if period is None or period.company_id != company:
        raise AppError("not_found", "Payroll period not found", 404)
    _reject_closed(period)
    group = await PayGroup.get(period.pay_group_id)
    if group is None or group.company_id != company or group.deleted_at is not None:
        raise AppError("not_found", "Pay group not found", 404)
    frequency = _frequency(group.frequency)
    settings = await _settings(company)
    table = await _tax_table(company, frequency, period.end)
    brackets = _brackets(table)
    employees = await Employee.find(
        {
            "company_id": company,
            "pay_group_id": str(group.id),
            "employment_status": "active",
            "deleted_at": None,
        }
    ).to_list()
    employees.sort(key=lambda item: item.employee_no)
    missing = [item.employee_no for item in employees if item.current_compensation is None]
    if missing:
        raise AppError(
            "compensation_missing",
            "Active employees are missing compensation",
            400,
            {"employee_nos": missing},
        )
    linked = await Claim.find({"company_id": company, "period_id": str(period.id)}).to_list()
    for claim in linked:
        if claim.paid_via != "payroll":
            continue
        claim.period_id = None
        claim.updated_at = utcnow()
        await claim.save()
    emp_ids = [str(item.id) for item in employees]
    window_start = min(period.start, period.attendance_cutoff)
    window_end = max(period.end, period.attendance_cutoff)
    days = []
    if emp_ids:
        fetched = await AttendanceDay.find(
            {"company_id": company, "employee_id": {"$in": emp_ids}}
        ).to_list()
        days = [day for day in fetched if window_start <= day.date <= window_end]
    days_by_emp: dict[str, list[AttendanceDay]] = defaultdict(list)
    for day in days:
        days_by_emp[day.employee_id].append(day)
    claim_rows = []
    if emp_ids:
        claim_rows = await Claim.find(
            {
                "company_id": company,
                "status": "approved",
                "paid_via": "payroll",
                "period_id": None,
                "employee_id": {"$in": emp_ids},
            }
        ).to_list()
    claim_types = {
        str(item.id): item
        for item in await ClaimType.find({"company_id": company, "deleted_at": None}).to_list()
    }
    adjustments = await Adjustment.find(
        {"company_id": company, "period_id": str(period.id)}
    ).to_list()
    retros = await RetroAdjustment.find(
        {"company_id": company, "period_id": str(period.id)}
    ).to_list()
    loans = await Loan.find({"company_id": company, "status": "active"}).to_list()
    recurring = []
    advances = []
    allowances = []
    histories = []
    leave_requests = []
    if emp_ids:
        recurring = await RecurringDeduction.find(
            {"company_id": company, "employee_id": {"$in": emp_ids}}
        ).to_list()
        advances = await CashAdvance.find(
            {"company_id": company, "employee_id": {"$in": emp_ids}}
        ).to_list()
        allowances = await EmployeeAllowance.find(
            {"company_id": company, "employee_id": {"$in": emp_ids}}
        ).to_list()
        histories = await CompensationHistory.find(
            {"company_id": company, "employee_id": {"$in": emp_ids}}
        ).to_list()
        leave_requests = await LeaveRequest.find(
            {"company_id": company, "employee_id": {"$in": emp_ids}, "status": "approved"}
        ).to_list()
    allowance_types = {
        str(item.id): item
        for item in await AllowanceType.find({"company_id": company}).to_list()
    }
    leave_types = {
        str(item.id): item for item in await LeaveType.find({"company_id": company}).to_list()
    }
    periods = {
        str(item.id): item
        for item in await PayrollPeriod.find({"company_id": company}).to_list()
    }
    openings = {
        item.employee_id: item
        for item in await YtdOpening.find(
            {"company_id": company, "year": period.end.year}
        ).to_list()
    }
    group_periods = [
        item
        for item in periods.values()
        if (
            item.pay_group_id == str(group.id)
            and item.end < period.start
            and item.end.year == period.end.year
        )
    ]
    group_periods.sort(key=lambda item: item.end)
    run_map = await latest_runs(company, [str(item.id) for item in group_periods])
    prior_slips = []
    if run_map:
        prior_slips = await Payslip.find(
            {"company_id": company, "run_id": {"$in": [str(item.id) for item in run_map.values()]}}
        ).to_list()
    slips_by_run = {(slip.run_id, slip.employee_id): slip for slip in prior_slips}
    per_year = _PERIODS[frequency]
    period_index = period.period_index if period.period_index > 0 else 1
    periods_in_month = period.periods_in_month if period.periods_in_month > 0 else 1
    order = tuple(settings.deduction_order) or _DEDUCTION_ORDER
    timing = settings.contribution_timing or "split"
    working = D(settings.factor_days_per_year) / Decimal(per_year)
    run.progress_total = len(employees)
    run.progress_done = 0
    run.status = "processing"
    run.updated_at = utcnow()
    await run.save()
    deferred_notes: list[str] = []
    for employee in employees:
        emp_id = str(employee.id)
        comp = employee.current_compensation
        assert comp is not None
        emp_days = [day for day in days_by_emp.get(emp_id, []) if _in_job(employee, day.date)]
        prior_for_emp: list[Payslip] = []
        for item in group_periods:
            found = run_map.get(str(item.id))
            if found is None:
                continue
            slip = slips_by_run.get((str(found.id), emp_id))
            if slip is not None:
                prior_for_emp.append(slip)
        opening = openings.get(emp_id)
        if prior_for_emp:
            source = prior_for_emp[-1]
            input_ytd = _ytd_from_dict(source.ytd)
            includes_opening = bool((source.snapshot or {}).get("includes_opening"))
        else:
            input_ytd = _ytd_from_opening(opening)
            includes_opening = opening is not None
        monthly_pay = _monthly_compensation(
            comp.pay_basis,
            D(comp.basic_salary),
            D(comp.daily_rate),
            D(comp.hourly_rate),
            settings.factor_days_per_year,
        )
        sss = sss_amount(monthly_pay)
        philhealth = philhealth_amount(monthly_pay)
        pagibig = pagibig_amount(monthly_pay)
        lwop, lwop_dates = _lwop_days(emp_id, period, leave_requests, leave_types)
        absence = Decimal(
            sum(
                1
                for day in emp_days
                if day.status == "absent" and not day.is_rest_day and day.date not in lwop_dates
            )
        )
        suspension = Decimal(sum(1 for day in emp_days if day.status == "suspension"))
        if emp_days:
            days_worked = Decimal(
                sum(
                    1
                    for day in emp_days
                    if day.status in {"present", "incomplete", "leave"}
                    or D(day.hours_worked or 0) > 0
                )
            )
            hours_worked = sum((D(day.hours_worked or 0) for day in emp_days), Decimal("0"))
        else:
            days_worked = _prorate_days(employee, period, working)
            hours_worked = days_worked * Decimal(8)
        deductions: list[OtherDeduction] = []
        for loan in loans:
            if loan.employee_id != emp_id or not _loan_applies(loan, period, periods):
                continue
            deductions.append(
                OtherDeduction(
                    code=f"loan:{loan.id}",
                    label=loan.type.replace("_", " "),
                    amount=money(min(D(loan.amortization), D(loan.balance))),
                    kind=_LOAN_KINDS.get(loan.type, "company_loan"),
                    ref_id=str(loan.id),
                )
            )
        for advance in advances:
            if advance.employee_id != emp_id or D(advance.balance) <= 0:
                continue
            if advance.status in {"liquidated", "closed", "cancelled"}:
                continue
            deductions.append(
                OtherDeduction(
                    code=f"cash_advance:{advance.id}",
                    label="Cash advance recovery",
                    amount=D(advance.balance),
                    kind="cash_advance",
                )
            )
        for item in recurring:
            if item.employee_id != emp_id or D(item.amount) <= 0:
                continue
            if item.until is not None and item.until < period.start:
                continue
            if item.frequency in {"monthly", "once_a_month"} and periods_in_month > 1:
                if period_index != 1:
                    continue
            deductions.append(
                OtherDeduction(
                    code=f"recurring:{item.id}",
                    label=item.label or item.type,
                    amount=D(item.amount),
                    kind="recurring",
                )
            )
        rank = {kind: index for index, kind in enumerate(order)}
        deductions.sort(key=lambda item: rank.get(item.kind, 99))
        emp_claims = [row for row in claim_rows if row.employee_id == emp_id]
        claim_inputs = []
        for claim in emp_claims:
            claim_type = claim_types.get(claim.claim_type_id)
            label = claim_type.name if claim_type else claim.description or "Claim"
            taxable = bool(claim_type and claim_type.taxability == "taxable")
            claim_inputs.append(
                ClaimInput(
                    code=f"claim:{claim.id}",
                    label=label,
                    amount=D(claim.amount),
                    taxable=taxable,
                )
            )
        emp_adjustments = [
            AdjustmentInput(
                code=f"adj:{item.id}",
                label=item.label,
                amount=D(item.amount),
                taxable=item.is_taxable,
            )
            for item in adjustments
            if item.employee_id == emp_id
        ]
        retro_pay = money(
            sum((D(item.amount) for item in retros if item.employee_id == emp_id), Decimal("0"))
        )
        payload = PayrollInput(
            employee_id=emp_id,
            pay_basis=comp.pay_basis,
            basic_salary=D(comp.basic_salary),
            daily_rate=D(comp.daily_rate),
            hourly_rate=D(comp.hourly_rate),
            periods_per_year=per_year,
            period_start=period.start,
            period_end=period.end,
            working_days_in_period=working,
            days_employed_in_period=_prorate_days(employee, period, working),
            days_worked=days_worked,
            hours_worked=hours_worked,
            absence_days=absence,
            lwop_days=lwop,
            suspension_days=suspension,
            late_minutes=sum(day.late_minutes or 0 for day in emp_days),
            undertime_minutes=sum(day.undertime_minutes or 0 for day in emp_days),
            is_minimum_wage_earner=employee.is_minimum_wage_earner,
            salary_slices=_salary_slices(
                [row for row in histories if row.employee_id == emp_id],
                employee,
                period,
                working,
            ),
            premiums=_premiums(emp_days, settings.ot_multipliers),
            allowances=_allowance_inputs(
                emp_id,
                period,
                period_index,
                periods_in_month,
                allowances,
                allowance_types,
                prior_for_emp,
            ),
            adjustments=tuple(emp_adjustments),
            claims=tuple(claim_inputs),
            retro_pay=retro_pay,
            sss=sss,
            philhealth=philhealth,
            pagibig=pagibig,
            contribution_timing=timing,
            period_index=period_index,
            periods_in_month=periods_in_month,
            tax_brackets=brackets,
            other_deductions=tuple(deductions),
            ytd=input_ytd,
            deduction_order=order,
        )
        result = compute_payroll(payload)
        lines = [_to_line(line, employee.cost_center_id) for line in result.lines]
        snapshot = {
            "pay_basis": comp.pay_basis,
            "basic_salary": money_str(comp.basic_salary),
            "daily_rate": money_str(comp.daily_rate),
            "hourly_rate": money_str(comp.hourly_rate),
            "periods_per_year": per_year,
            "period_index": period_index,
            "periods_in_month": periods_in_month,
            "factor_days_per_year": settings.factor_days_per_year,
            "contribution_timing": timing,
            "tax_table_id": str(table.id),
            "pay_group_id": str(group.id),
            "frequency": frequency,
            "includes_opening": includes_opening,
            "is_minimum_wage_earner": employee.is_minimum_wage_earner,
            "sss": _stat_dict(sss, timing, period_index, periods_in_month),
            "philhealth": _stat_dict(philhealth, timing, period_index, periods_in_month),
            "pagibig": _stat_dict(pagibig, timing, period_index, periods_in_month),
        }
        existing_slip = await Payslip.find_one(
            {"company_id": company, "run_id": str(run.id), "employee_id": emp_id}
        )
        if existing_slip is None:
            existing_slip = Payslip(
                company_id=company,
                run_id=str(run.id),
                period_id=str(period.id),
                employee_id=emp_id,
                basic_pay=result.basic_pay,
                gross=result.gross,
                taxable_income=result.taxable_income,
                non_taxable_income=result.non_taxable_income,
                withholding_tax=result.withholding_tax,
                total_deductions=result.total_deductions,
                net_pay=result.net_pay,
                lines=lines,
                ytd=_dump_ytd(result.ytd),
                snapshot=snapshot,
                is_published=False,
                has_deferrals=result.has_deferrals,
                created_by=run.computed_by,
                updated_by=run.computed_by,
            )
            await existing_slip.insert()
        else:
            existing_slip.basic_pay = result.basic_pay
            existing_slip.gross = result.gross
            existing_slip.taxable_income = result.taxable_income
            existing_slip.non_taxable_income = result.non_taxable_income
            existing_slip.withholding_tax = result.withholding_tax
            existing_slip.total_deductions = result.total_deductions
            existing_slip.net_pay = result.net_pay
            existing_slip.lines = lines
            existing_slip.ytd = _dump_ytd(result.ytd)
            existing_slip.snapshot = snapshot
            existing_slip.has_deferrals = result.has_deferrals
            existing_slip.updated_at = utcnow()
            existing_slip.updated_by = run.computed_by
            await existing_slip.save()
        for claim in emp_claims:
            claim.period_id = str(period.id)
            claim.updated_at = utcnow()
            await claim.save()
        if result.has_deferrals:
            deferred_notes.append(employee.employee_no)
        run.progress_done += 1
        run.updated_at = utcnow()
        await run.save()
    covered = set(emp_ids)
    for day in days:
        if day.employee_id not in covered:
            continue
        day.is_locked = True
        await day.save()
    run.progress_done = run.progress_total
    run.status = "computed"
    if deferred_notes:
        run.notes = "Deferred deductions: " + ", ".join(deferred_notes)
    run.updated_at = utcnow()
    await run.save()
    period.status = "computed"
    period.updated_at = utcnow()
    period.updated_by = run.computed_by
    await period.save()


async def submit_period(actor: Actor, period_id: str) -> dict:
    from app.modules.identity.service import block_payroll_if_impersonating

    block_payroll_if_impersonating(actor)
    policies.require_compute(actor)
    period = await _period(actor, period_id)
    if period.status != "computed":
        raise AppError("conflict", "Compute the period before submitting", 409)
    run = await latest_run(policies.company_id(actor), str(period.id))
    if run is None:
        raise AppError("not_found", "Payroll run not found", 404)
    if not run.computed_by:
        raise AppError("conflict", "This run has no computer recorded", 409)
    period.status = "for_approval"
    period.updated_at = utcnow()
    period.updated_by = actor.user_id
    run.status = "for_approval"
    run.updated_at = utcnow()
    run.updated_by = actor.user_id
    await period.save()
    await run.save()
    request = await start_request(
        actor=actor,
        module="payroll",
        subject_type="payroll_run",
        subject_id=str(run.id),
        context={"period_id": str(period.id), "computed_by": run.computed_by},
    )
    body = _workflow(period, run)
    body["approval_request_id"] = str(request.id)
    return body


async def approve_period(actor: Actor, period_id: str) -> dict:
    from app.modules.identity.service import block_payroll_if_impersonating

    block_payroll_if_impersonating(actor)
    policies.require_approve(actor)
    period = await _period(actor, period_id)
    if period.status != "for_approval":
        raise AppError("conflict", "This period is not waiting for approval", 409)
    run = await latest_run(policies.company_id(actor), str(period.id))
    if run is None:
        raise AppError("not_found", "Payroll run not found", 404)
    policies.require_separation(actor, run.computed_by)
    period.status = "approved"
    period.updated_at = utcnow()
    period.updated_by = actor.user_id
    run.status = "approved"
    run.approved_by = actor.user_id
    run.approved_at = utcnow()
    run.updated_at = utcnow()
    run.updated_by = actor.user_id
    await period.save()
    await run.save()
    return _workflow(period, run)


async def _apply_loan_lines(
    company_id: str,
    slip: Payslip,
    session: AsyncClientSession,
    balances: dict[str, Decimal],
) -> None:
    for line in slip.lines:
        if line.type != "deduction" or line.deferred or not line.ref_id:
            continue
        loan = await Loan.get(line.ref_id, session=session)
        if loan is None or loan.company_id != company_id:
            raise AppError("not_found", "Loan not found for a payslip deduction", 404)
        if str(loan.id) not in balances:
            balances[str(loan.id)] = D(loan.balance)
        updated = money(balances[str(loan.id)] - D(line.amount))
        if updated < 0:
            raise AppError("conflict", "Loan balance would become negative", 409)
        payment = LoanPayment(
            company_id=company_id,
            loan_id=str(loan.id),
            payslip_id=str(slip.id),
            amount=money(line.amount),
            at=utcnow(),
        )
        await payment.insert(session=session)
        loan.balance = updated
        balances[str(loan.id)] = updated
        if loan.balance == 0:
            loan.status = "paid"
        loan.updated_at = utcnow()
        await loan.save(session=session)


async def _apply_cash_advances(
    company_id: str,
    slip: Payslip,
    session: AsyncClientSession,
    balances: dict[str, Decimal],
) -> None:
    prefix = "cash_advance:"
    for line in slip.lines:
        if line.type != "deduction" or line.deferred or not line.code.startswith(prefix):
            continue
        advance_id = line.code[len(prefix) :]
        advance = await CashAdvance.get(advance_id, session=session)
        if advance is None or advance.company_id != company_id:
            raise AppError("not_found", "Cash advance not found for a payslip deduction", 404)
        if advance_id not in balances:
            balances[advance_id] = D(advance.balance)
        updated = money(balances[advance_id] - D(line.amount))
        if updated < 0:
            raise AppError("conflict", "Cash advance balance would become negative", 409)
        advance.balance = updated
        balances[advance_id] = updated
        if advance.balance == 0:
            advance.status = "liquidated"
        advance.updated_at = utcnow()
        await advance.save(session=session)


async def release_period(actor: Actor, period_id: str) -> dict:
    from app.modules.identity.service import block_payroll_if_impersonating

    block_payroll_if_impersonating(actor)
    policies.require_approve(actor)
    company = policies.company_id(actor)
    period = await _period(actor, period_id)
    if period.status != "approved":
        raise AppError("conflict", "Approve the period before release", 409)
    run = await latest_run(company, str(period.id))
    if run is None:
        raise AppError("not_found", "Payroll run not found", 404)
    slips = await Payslip.find({"company_id": company, "run_id": str(run.id)}).to_list()
    loan_balances: dict[str, Decimal] = {}
    advance_balances: dict[str, Decimal] = {}
    async with transaction() as session:
        for slip in slips:
            fresh = await Payslip.get(slip.id, session=session)
            if fresh is None or fresh.company_id != company:
                raise AppError("not_found", "Payslip not found", 404)
            fresh.is_published = True
            fresh.updated_at = utcnow()
            fresh.updated_by = actor.user_id
            await fresh.save(session=session)
            await _apply_loan_lines(company, fresh, session, loan_balances)
            await _apply_cash_advances(company, fresh, session, advance_balances)
        period.status = "released"
        period.updated_at = utcnow()
        period.updated_by = actor.user_id
        await period.save(session=session)
        run.status = "released"
        run.updated_at = utcnow()
        run.updated_by = actor.user_id
        await run.save(session=session)
    await _email_released_payslips(company, str(run.id))
    fresh_period = await PayrollPeriod.get(str(period.id))
    return _workflow(fresh_period or period, run)


async def lock_period(actor: Actor, period_id: str) -> dict:
    from app.modules.identity.service import block_payroll_if_impersonating

    block_payroll_if_impersonating(actor)
    policies.require_approve(actor)
    period = await _period(actor, period_id)
    if period.status == "locked":
        raise AppError("conflict", "This period is already locked", 409)
    period.status = "locked"
    period.updated_at = utcnow()
    period.updated_by = actor.user_id
    await period.save()
    run = await latest_run(policies.company_id(actor), str(period.id))
    if run is not None:
        run.status = "locked"
        run.updated_at = utcnow()
        run.updated_by = actor.user_id
        await run.save()
    return _workflow(period, run)


async def _people(company_id: str) -> dict[str, Employee]:
    rows = await Employee.find({"company_id": company_id}).to_list()
    return {str(item.id): item for item in rows}


async def _current_slips(
    actor: Actor, period_id: str
) -> tuple[PayrollPeriod, PayrollRun, list[Payslip]]:
    policies.require_view(actor)
    period = await _period(actor, period_id)
    run = await latest_run(policies.company_id(actor), str(period.id))
    if run is None:
        raise AppError("not_found", "Payroll run not found", 404)
    slips = await Payslip.find(
        {"company_id": policies.company_id(actor), "run_id": str(run.id)}
    ).to_list()
    slips.sort(key=lambda item: item.employee_id)
    return period, run, slips


async def list_payslips(actor: Actor, period_id: str) -> dict:
    _period_doc, run, slips = await _current_slips(actor, period_id)
    return {"run_id": str(run.id), "items": [api(item) for item in slips], "total": len(slips)}


async def progress_report(actor: Actor, period_id: str) -> dict:
    policies.require_view(actor)
    period = await _period(actor, period_id)
    run = await latest_run(policies.company_id(actor), str(period.id))
    if run is None:
        return {
            "done": 0,
            "total": 0,
            "status": period.status,
            "run_id": None,
            "period_status": period.status,
        }
    return {
        "done": run.progress_done,
        "total": run.progress_total,
        "status": run.status,
        "run_id": str(run.id),
        "period_status": period.status,
    }


async def variance_report(actor: Actor, period_id: str) -> dict:
    period, _run, slips = await _current_slips(actor, period_id)
    company = policies.company_id(actor)
    settings = await _settings(company)
    threshold = D(settings.variance_threshold)
    people = await _people(company)
    previous_rows = await PayrollPeriod.find(
        {"company_id": company, "pay_group_id": period.pay_group_id}
    ).to_list()
    previous = [
        item
        for item in previous_rows
        if item.end < period.start and str(item.id) != str(period.id)
    ]
    previous.sort(key=lambda item: (item.end, item.start))
    prior_nets: dict[str, Decimal] = {}
    if previous:
        prior_run = await latest_run(company, str(previous[-1].id))
        if prior_run is not None:
            prior_slips = await Payslip.find(
                {"company_id": company, "run_id": str(prior_run.id)}
            ).to_list()
            prior_nets = {item.employee_id: D(item.net_pay) for item in prior_slips}
    current = {item.employee_id: D(item.net_pay) for item in slips}
    rows = []
    for emp_id in sorted(set(current) | set(prior_nets)):
        now = current.get(emp_id, Decimal("0"))
        before = prior_nets.get(emp_id, Decimal("0"))
        if before == 0:
            ratio = None
            flagged = now != before
        else:
            ratio = abs(now - before) / abs(before)
            flagged = ratio > threshold
        person = people.get(emp_id)
        rows.append(
            {
                "employee_id": emp_id,
                "employee_no": person.employee_no if person else "",
                "name": person.name.full_name if person else "",
                "previous_net": money_str(before),
                "current_net": money_str(now),
                "change_ratio": None if ratio is None else format(ratio, "f"),
                "flagged": flagged,
            }
        )
    return {"threshold": money_str(threshold), "items": rows}


async def register_report(actor: Actor, period_id: str) -> dict:
    period, run, slips = await _current_slips(actor, period_id)
    people = await _people(policies.company_id(actor))
    rows = []
    totals = {
        "basic_pay": Decimal("0"),
        "gross": Decimal("0"),
        "withholding_tax": Decimal("0"),
        "total_deductions": Decimal("0"),
        "net_pay": Decimal("0"),
    }
    for slip in slips:
        person = people.get(slip.employee_id)
        row = {
            "employee_id": slip.employee_id,
            "employee_no": person.employee_no if person else "",
            "name": person.name.full_name if person else "",
            "basic_pay": money_str(slip.basic_pay),
            "gross": money_str(slip.gross),
            "taxable_income": money_str(slip.taxable_income),
            "withholding_tax": money_str(slip.withholding_tax),
            "total_deductions": money_str(slip.total_deductions),
            "net_pay": money_str(slip.net_pay),
            "has_deferrals": slip.has_deferrals,
        }
        rows.append(row)
        totals["basic_pay"] += D(slip.basic_pay)
        totals["gross"] += D(slip.gross)
        totals["withholding_tax"] += D(slip.withholding_tax)
        totals["total_deductions"] += D(slip.total_deductions)
        totals["net_pay"] += D(slip.net_pay)
    return {
        "period_id": str(period.id),
        "run_id": str(run.id),
        "rows": rows,
        "totals": {key: money_str(value) for key, value in totals.items()},
    }


def _reveal(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if not value.startswith("v1:"):
        return value
    from app.core.encryption import decrypt

    try:
        return decrypt(value)
    except Exception:
        return ""


def _bank_label(accounts: list[dict] | None) -> str:
    if not accounts:
        return ""
    first = accounts[0]
    if not isinstance(first, dict):
        return ""
    name = _reveal(first.get("bank") or first.get("bank_name") or first.get("name") or "")
    number = _reveal(
        first.get("account_no") or first.get("account_number") or first.get("number") or ""
    )
    return f"{name} {number}".strip()


async def bank_file_csv(actor: Actor, period_id: str) -> str:
    _period_doc, _run, slips = await _current_slips(actor, period_id)
    company = policies.company_id(actor)
    people = await _people(company)
    sensitive = await EmployeeSensitive.find({"company_id": company}).to_list()
    banks = {item.employee_id: item.bank_accounts for item in sensitive}
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["employee_no", "name", "bank", "net"])
    ordered = sorted(
        slips,
        key=lambda item: people[item.employee_id].employee_no if item.employee_id in people else "",
    )
    for slip in ordered:
        person = people.get(slip.employee_id)
        writer.writerow(
            [
                person.employee_no if person else "",
                person.name.full_name if person else "",
                _bank_label(banks.get(slip.employee_id)),
                money_str(slip.net_pay),
            ]
        )
    return buffer.getvalue()


async def journal_report(actor: Actor, period_id: str) -> dict:
    period, run, slips = await _current_slips(actor, period_id)
    totals: dict[tuple[str, str, str | None], Decimal] = {}
    for slip in slips:
        for line in slip.lines:
            key = (line.type, line.code, line.cost_center_id)
            totals[key] = totals.get(key, Decimal("0")) + D(line.amount)
    rows = [
        {
            "type": kind,
            "code": code,
            "cost_center_id": cost_center_id,
            "amount": money_str(amount),
        }
        for (kind, code, cost_center_id), amount in sorted(
            totals.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2] or ""),
        )
    ]
    return {"period_id": str(period.id), "run_id": str(run.id), "rows": rows}


def _payslip_html(employee: Employee, period: PayrollPeriod, slip: Payslip) -> str:
    rows = []
    for line in slip.lines:
        label = escape(line.label)
        code = escape(line.code)
        amount = escape(money_str(line.amount))
        rows.append(f"<tr><td>{label}</td><td>{code}</td><td>{amount}</td></tr>")
    return (
        "<html><body><h1>Payslip</h1>"
        f"<p>{escape(employee.name.full_name)} ({escape(employee.employee_no)})</p>"
        f"<p>Period {escape(period.start.isoformat())} to {escape(period.end.isoformat())}</p>"
        "<table><tr><th>Item</th><th>Code</th><th>Amount</th></tr>"
        + "".join(rows)
        + "</table>"
        f"<p>Gross {escape(money_str(slip.gross))}</p>"
        f"<p>Deductions {escape(money_str(slip.total_deductions))}</p>"
        f"<p>Net pay {escape(money_str(slip.net_pay))}</p>"
        "</body></html>"
    )


async def payslip_pdf_bytes(actor: Actor, payslip_id: str) -> bytes:
    slip = await TenantRepo(Payslip, actor).get(payslip_id)
    if not isinstance(slip, Payslip):
        raise AppError("not_found", "Payslip not found", 404)
    policies.require_payslip_access(actor, slip.employee_id, slip.is_published)
    employee = await Employee.get(slip.employee_id)
    period = await PayrollPeriod.get(slip.period_id)
    if (
        employee is None
        or period is None
        or employee.company_id != slip.company_id
        or period.company_id != slip.company_id
    ):
        raise AppError("not_found", "Payslip not found", 404)
    from app.shared import documents

    return documents.html_to_pdf(_payslip_html(employee, period, slip))


def _password(pattern: str, employee_no: str, birth: date | None) -> str:
    mmdd = birth.strftime("%m%d") if birth else ""
    if "{employee_no}" in pattern or "{birth_mmdd}" in pattern:
        return pattern.format(employee_no=employee_no, birth_mmdd=mmdd)
    return f"{employee_no}{mmdd}"


async def _email_released_payslips(company_id: str, run_id: str) -> None:
    try:
        settings = await _settings(company_id)
        slips = await Payslip.find({"company_id": company_id, "run_id": run_id}).to_list()
        for slip in slips:
            try:
                await _email_one(company_id, slip, settings.payslip_password_pattern)
            except Exception:
                logger.exception("payslip email failed for %s", slip.employee_id)
    except Exception:
        logger.exception("payslip publishing email failed")


async def _email_one(company_id: str, slip: Payslip, pattern: str) -> None:
    employee = await Employee.get(slip.employee_id)
    period = await PayrollPeriod.get(slip.period_id)
    if employee is None or period is None or employee.company_id != company_id:
        return
    from app.modules.identity.models import User
    from app.shared import documents
    from app.shared.notify import notify

    email = None
    user = await User.get(employee.user_id) if employee.user_id else None
    if user and user.email:
        email = user.email
    if email is None:
        contact = employee.contact.get("email") if isinstance(employee.contact, dict) else None
        email = contact if isinstance(contact, str) else None
    pdf = documents.html_to_pdf(_payslip_html(employee, period, slip))
    password = _password(pattern, employee.employee_no, employee.birth_date)
    protected = documents.protect_pdf(pdf, password)
    if user is not None:
        await notify(
            company_id=company_id,
            user_id=str(user.id),
            event_key="payroll.payslip",
            title="Your payslip is ready",
            body="A password-protected payslip was sent to you.",
            email=None,
        )
    if not email:
        return
    await _send_pdf(email, "Your payslip", "<p>Your payslip is attached.</p>", protected)
    slip.emailed_at = utcnow()
    await slip.save()


async def _send_pdf(to: str, subject: str, html: str, pdf: bytes) -> None:
    from email.message import EmailMessage

    import aiosmtplib

    from app.core.config import get_settings

    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(html, subtype="html")
    message.add_attachment(pdf, maintype="application", subtype="pdf", filename="payslip.pdf")
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=False,
    )
