"""Table-driven checks for the pure HR engines."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.core.money import money
from app.domain.annualization import TaxBracket, annualize, thirteenth_month
from app.domain.attendance import (
    AttendanceRules,
    Punch,
    ScheduleSnap,
    compute_day,
    holiday_applies,
)
from app.domain.contributions import (
    StatutoryAmount,
    pagibig_amount,
    philhealth_amount,
    portion,
    sss_amount,
    sss_msc,
)
from app.domain.final_pay import FinalPayInput, compute_final_pay
from app.domain.leave import (
    LedgerEntry,
    can_debit,
    count_leave_days,
    project_balance,
    ranges_overlap,
    split_year_end,
)
from app.domain.payroll_engine import (
    OtherDeduction,
    PayrollInput,
    PremiumInput,
    SalarySlice,
    compute_payroll,
)

TZ = ZoneInfo("Asia/Manila")
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "payroll"

MONTHLY_TAX = (
    TaxBracket(Decimal("0"), Decimal("0"), Decimal("0")),
    TaxBracket(Decimal("20833.33"), Decimal("0"), Decimal("0.15")),
    TaxBracket(Decimal("33333.33"), Decimal("1875.00"), Decimal("0.20")),
    TaxBracket(Decimal("66666.67"), Decimal("8541.67"), Decimal("0.25")),
    TaxBracket(Decimal("166666.67"), Decimal("33541.67"), Decimal("0.30")),
    TaxBracket(Decimal("666666.67"), Decimal("183541.67"), Decimal("0.35")),
)

ANNUAL_TAX = (
    TaxBracket(Decimal("0"), Decimal("0"), Decimal("0")),
    TaxBracket(Decimal("250000"), Decimal("0"), Decimal("0.15")),
    TaxBracket(Decimal("400000"), Decimal("22500"), Decimal("0.20")),
    TaxBracket(Decimal("800000"), Decimal("102500"), Decimal("0.25")),
    TaxBracket(Decimal("2000000"), Decimal("402500"), Decimal("0.30")),
    TaxBracket(Decimal("8000000"), Decimal("2202500"), Decimal("0.35")),
)


def _monthly(**overrides: object) -> PayrollInput:
    base = dict(
        employee_id="e1",
        pay_basis="monthly",
        basic_salary=Decimal("30000"),
        daily_rate=Decimal("1379.31"),
        hourly_rate=Decimal("172.41"),
        periods_per_year=12,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 30),
        working_days_in_period=Decimal("22"),
        days_employed_in_period=Decimal("22"),
        days_worked=Decimal("22"),
        hours_worked=Decimal("176"),
        sss=sss_amount(Decimal("30000")),
        philhealth=philhealth_amount(Decimal("30000")),
        pagibig=pagibig_amount(Decimal("30000")),
        tax_brackets=MONTHLY_TAX,
        contribution_timing="split",
        period_index=1,
        periods_in_month=1,
    )
    base.update(overrides)
    return PayrollInput(**base)  # type: ignore[arg-type]


def test_money_rejects_float() -> None:
    with pytest.raises(TypeError):
        money(1.25)


def test_sss_philhealth_pagibig_anchors() -> None:
    assert sss_msc(Decimal("4000")) == Decimal("5000")
    assert sss_msc(Decimal("5250")) == Decimal("5500")
    assert sss_msc(Decimal("30000")) == Decimal("30000")
    assert sss_msc(Decimal("50000")) == Decimal("35000")
    sss = sss_amount(Decimal("30000"))
    assert sss.ee == Decimal("1500.00")
    assert sss.er == Decimal("3000.00")
    assert sss.ec == Decimal("30.00")
    assert sss.mpf == Decimal("500.00")
    assert philhealth_amount(Decimal("30000")).ee == Decimal("750.00")
    assert philhealth_amount(Decimal("5000")).ee == Decimal("250.00")
    assert philhealth_amount(Decimal("250000")).ee == Decimal("2500.00")
    assert pagibig_amount(Decimal("30000")).ee == Decimal("200.00")
    assert pagibig_amount(Decimal("1000")).ee == Decimal("10.00")
    assert portion(Decimal("200"), "split", 1, 2) == Decimal("100.00")
    assert portion(Decimal("200"), "first_cutoff", 2, 2) == Decimal("0.00")
    assert portion(Decimal("200"), "second_cutoff", 2, 2) == Decimal("200.00")


def test_monthly_regular_matches_fixture() -> None:
    raw = json.loads((FIXTURES / "monthly_regular.json").read_text())
    result = compute_payroll(_monthly())
    expect = raw["expect"]
    assert result.basic_pay == Decimal(expect["basic_pay"])
    assert result.gross == Decimal(expect["gross"])
    assert result.taxable_income == Decimal(expect["taxable_income"])
    assert result.withholding_tax == Decimal(expect["withholding_tax"])
    assert result.total_deductions == Decimal(expect["total_deductions"])
    assert result.net_pay == Decimal(expect["net_pay"])
    assert result.has_deferrals is False
    assert result.net_pay == money(result.gross - result.total_deductions)


def test_daily_paid_uses_days_worked() -> None:
    result = compute_payroll(
        _monthly(
            pay_basis="daily",
            basic_salary=Decimal("0"),
            daily_rate=Decimal("800"),
            hourly_rate=Decimal("100"),
            days_worked=Decimal("10"),
            periods_per_year=24,
            sss=StatutoryAmount(Decimal("500"), Decimal("1000"), Decimal("10")),
            philhealth=StatutoryAmount(Decimal("250"), Decimal("250")),
            pagibig=StatutoryAmount(Decimal("200"), Decimal("200")),
            contribution_timing="split",
            periods_in_month=2,
            period_index=1,
        )
    )
    assert result.basic_pay == Decimal("8000.00")
    # Split monthly contributions in half.
    assert _line(result, "sss") == Decimal("250.00")
    assert result.net_pay > 0


def test_minimum_wage_earner_exempts_statutory_pay() -> None:
    result = compute_payroll(
        _monthly(
            basic_salary=Decimal("15000"),
            daily_rate=Decimal("625"),
            hourly_rate=Decimal("78.125"),
            is_minimum_wage_earner=True,
            premiums=(PremiumInput("ot_regular", "Regular OT", 120, Decimal("1.25")),),
            sss=StatutoryAmount(Decimal("0"), Decimal("0")),
            philhealth=StatutoryAmount(Decimal("0"), Decimal("0")),
            pagibig=StatutoryAmount(Decimal("0"), Decimal("0")),
            tax_brackets=(TaxBracket(Decimal("0"), Decimal("0"), Decimal("0.10")),),
        )
    )
    assert result.taxable_income == Decimal("0.00")
    assert result.withholding_tax == Decimal("0.00")
    assert result.basic_pay == Decimal("15000.00")


def test_mid_period_hire_prorates_monthly_basic() -> None:
    result = compute_payroll(
        _monthly(
            periods_per_year=24,
            working_days_in_period=Decimal("10"),
            days_employed_in_period=Decimal("6"),
            days_worked=Decimal("6"),
            sss=StatutoryAmount(Decimal("0"), Decimal("0")),
            philhealth=StatutoryAmount(Decimal("0"), Decimal("0")),
            pagibig=StatutoryAmount(Decimal("0"), Decimal("0")),
            tax_brackets=(),
        )
    )
    # Semi-monthly basic 15,000 × 6/10.
    assert result.basic_pay == Decimal("9000.00")


def test_backdated_salary_slices() -> None:
    result = compute_payroll(
        _monthly(
            salary_slices=(
                SalarySlice(Decimal("1500"), Decimal("7")),
                SalarySlice(Decimal("1800"), Decimal("3")),
            ),
            sss=StatutoryAmount(Decimal("0"), Decimal("0")),
            philhealth=StatutoryAmount(Decimal("0"), Decimal("0")),
            pagibig=StatutoryAmount(Decimal("0"), Decimal("0")),
            tax_brackets=(),
        )
    )
    assert result.basic_pay == Decimal("15900.00")


def test_holiday_rest_ot_night_premiums() -> None:
    result = compute_payroll(
        _monthly(
            pay_basis="daily",
            daily_rate=Decimal("800"),
            hourly_rate=Decimal("100"),
            days_worked=Decimal("1"),
            premiums=(
                PremiumInput("regular_holiday_ot", "Regular holiday OT", 120, Decimal("2.60")),
                PremiumInput("night_diff", "Night differential", 60, Decimal("0.10")),
            ),
            sss=StatutoryAmount(Decimal("0"), Decimal("0")),
            philhealth=StatutoryAmount(Decimal("0"), Decimal("0")),
            pagibig=StatutoryAmount(Decimal("0"), Decimal("0")),
            tax_brackets=(),
        )
    )
    assert result.basic_pay == Decimal("800.00")
    assert _line(result, "regular_holiday_ot") == Decimal("520.00")
    assert _line(result, "night_diff") == Decimal("10.00")
    assert result.gross == Decimal("1330.00")


def test_loan_beyond_pay_is_deferred_and_net_is_not_negative() -> None:
    result = compute_payroll(
        _monthly(
            basic_salary=Decimal("5000"),
            sss=StatutoryAmount(Decimal("800"), Decimal("1600"), Decimal("10")),
            philhealth=StatutoryAmount(Decimal("200"), Decimal("200")),
            pagibig=StatutoryAmount(Decimal("100"), Decimal("100")),
            other_deductions=(
                OtherDeduction(
                    "company_loan",
                    "Company loan",
                    Decimal("10000"),
                    "company_loan",
                    "loan-1",
                ),
            ),
        )
    )
    assert result.net_pay == Decimal("0.00")
    assert result.has_deferrals is True
    assert result.deferred_amount == Decimal("6100.00")
    taken = _line(result, "company_loan")
    assert taken == Decimal("3900.00")


def test_separation_proration_and_annualization_and_thirteenth() -> None:
    separated = compute_payroll(
        _monthly(
            periods_per_year=24,
            working_days_in_period=Decimal("10"),
            days_employed_in_period=Decimal("4"),
            sss=StatutoryAmount(Decimal("0"), Decimal("0")),
            philhealth=StatutoryAmount(Decimal("0"), Decimal("0")),
            pagibig=StatutoryAmount(Decimal("0"), Decimal("0")),
            tax_brackets=(),
        )
    )
    assert separated.basic_pay == Decimal("6000.00")
    assert thirteenth_month(Decimal("120000")) == Decimal("10000.00")
    refund = annualize(
        ytd_taxable=Decimal("200000"),
        previous_employer_taxable=Decimal("80000"),
        ytd_withheld=Decimal("5000"),
        previous_employer_withheld=Decimal("2000"),
        brackets=ANNUAL_TAX,
    )
    # 280,000 taxable. Tax = 15% of 30,000 = 4,500. Withheld 7,000. Refund 2,500.
    assert refund.annual_tax_due == Decimal("4500.00")
    assert refund.refund_or_payable == Decimal("-2500.00")
    payable = annualize(
        ytd_taxable=Decimal("500000"),
        previous_employer_taxable=Decimal("0"),
        ytd_withheld=Decimal("10000"),
        previous_employer_withheld=Decimal("0"),
        brackets=ANNUAL_TAX,
    )
    # 500,000 → 22,500 + 20% of 100,000 = 42,500. Payable 32,500.
    assert payable.annual_tax_due == Decimal("42500.00")
    assert payable.refund_or_payable == Decimal("32500.00")


def test_final_pay_components() -> None:
    result = compute_final_pay(
        FinalPayInput(
            unpaid_salary=Decimal("6000"),
            prorated_thirteenth=Decimal("10000"),
            leave_conversion=Decimal("1500"),
            annualization_refund_or_payable=Decimal("-2500"),
            accountabilities=Decimal("800"),
        )
    )
    assert result.net == Decimal("19200.00")
    owes = compute_final_pay(
        FinalPayInput(
            unpaid_salary=Decimal("1000"),
            prorated_thirteenth=Decimal("0"),
            leave_conversion=Decimal("0"),
            annualization_refund_or_payable=Decimal("500"),
            accountabilities=Decimal("4000"),
        )
    )
    assert owes.employee_owes is True
    assert owes.net == Decimal("-3500.00")


def _line(result: object, code: str) -> Decimal:
    from app.domain.payroll_engine import PayslipResult

    assert isinstance(result, PayslipResult)
    amounts = [
        line.amount for line in result.lines if line.code == code and line.type != "deferred"
    ]
    return money(sum(amounts, Decimal("0")))


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=TZ)


def _schedule(**overrides: object) -> ScheduleSnap:
    base = dict(
        start_minute=8 * 60,
        end_minute=17 * 60,
        break_minutes=60,
        grace_minutes=5,
        rest_days=(5, 6),
        crosses_midnight=False,
        required_minutes=8 * 60,
    )
    base.update(overrides)
    return ScheduleSnap(**base)  # type: ignore[arg-type]


def test_attendance_late_undertime_ot_night_and_holiday_split() -> None:
    rules = AttendanceRules(ot_rounding_minutes=30)
    on_time = compute_day(
        day=date(2026, 11, 3),
        punches=(Punch(_at(3, 8), "in"), Punch(_at(3, 17), "out")),
        schedule=_schedule(),
        holiday_type="none",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=rules,
    )
    assert on_time.late_minutes == 0
    assert on_time.hours_worked == Decimal("8.00")
    assert on_time.status == "present"

    late = compute_day(
        day=date(2026, 11, 3),
        punches=(Punch(_at(3, 8, 20), "in"), Punch(_at(3, 17), "out")),
        schedule=_schedule(),
        holiday_type="none",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=AttendanceRules(late_counts_from_schedule_if_beyond_grace=False),
    )
    assert late.late_minutes == 15
    from_start = compute_day(
        day=date(2026, 11, 3),
        punches=(Punch(_at(3, 8, 20), "in"), Punch(_at(3, 17), "out")),
        schedule=_schedule(),
        holiday_type="none",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=AttendanceRules(late_counts_from_schedule_if_beyond_grace=True),
    )
    assert from_start.late_minutes == 20

    early = compute_day(
        day=date(2026, 11, 3),
        punches=(Punch(_at(3, 8), "in"), Punch(_at(3, 16), "out")),
        schedule=_schedule(),
        holiday_type="none",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=rules,
    )
    assert early.undertime_minutes == 60

    ot = compute_day(
        day=date(2026, 11, 3),
        punches=(Punch(_at(3, 8), "in"), Punch(_at(3, 18, 30), "out")),
        schedule=_schedule(),
        holiday_type="none",
        next_holiday_type="none",
        approved_ot_minutes=60,
        is_on_leave=False,
        rules=rules,
    )
    assert ot.overtime_minutes == 60
    unapproved = compute_day(
        day=date(2026, 11, 3),
        punches=(Punch(_at(3, 8), "in"), Punch(_at(3, 18, 30), "out")),
        schedule=_schedule(),
        holiday_type="none",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=rules,
    )
    assert unapproved.overtime_minutes == 0

    night = compute_day(
        day=date(2026, 11, 3),
        punches=(Punch(_at(3, 22), "in"), Punch(_at(4, 6), "out")),
        schedule=_schedule(
            start_minute=22 * 60,
            end_minute=6 * 60,
            crosses_midnight=True,
            required_minutes=7 * 60,
        ),
        holiday_type="regular",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=rules,
    )
    assert night.night_diff_minutes == 420
    assert night.hours_worked == Decimal("7.00")
    assert night.portions[0].holiday_type == "regular"
    assert night.portions[1].holiday_type == "none"
    assert night.portions[0].day == date(2026, 11, 3)
    assert sum(part.minutes for part in night.portions) == 420

    rest = compute_day(
        day=date(2026, 11, 7),
        punches=(Punch(_at(7, 8), "in"), Punch(_at(7, 17), "out")),
        schedule=_schedule(),
        holiday_type="none",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=rules,
    )
    assert rest.is_rest_day is True
    assert rest.status == "present"

    holiday = compute_day(
        day=date(2026, 11, 30),
        punches=(),
        schedule=_schedule(),
        holiday_type="double_regular",
        next_holiday_type="none",
        approved_ot_minutes=0,
        is_on_leave=False,
        rules=rules,
    )
    assert holiday.status == "holiday"
    assert holiday.holiday_type == "double_regular"
    assert holiday_applies("nationwide", branch_id="b", branch_city="Cebu")
    assert holiday_applies("city", branch_id="b", branch_city="Cebu", cities=("Cebu",))
    assert not holiday_applies("city", branch_id="b", branch_city="Manila", cities=("Cebu",))
    assert holiday_applies("branch", branch_id="b1", branch_city="Manila", branch_ids=("b1",))


def test_leave_day_count_and_ledger_fold() -> None:
    holidays = frozenset({date(2026, 11, 2)})
    # Mon Nov 2 is a holiday, request Mon-Sun. Charge Tue-Fri only (4) when weekends excluded.
    assert count_leave_days(
        date(2026, 11, 2),
        date(2026, 11, 8),
        rest_days=(5, 6),
        holidays=holidays,
        counts_weekends=False,
        half_day=False,
    ) == Decimal("4")
    assert count_leave_days(
        date(2026, 11, 2),
        date(2026, 11, 8),
        rest_days=(5, 6),
        holidays=holidays,
        counts_weekends=True,
        half_day=False,
    ) == Decimal("6")
    assert count_leave_days(
        date(2026, 11, 3),
        date(2026, 11, 3),
        rest_days=(5, 6),
        holidays=holidays,
        counts_weekends=False,
        half_day=True,
    ) == Decimal("0.5")
    assert ranges_overlap(
        date(2026, 11, 1), date(2026, 11, 3), date(2026, 11, 3), date(2026, 11, 4)
    )
    entries = (
        LedgerEntry("entitlement", Decimal("5")),
        LedgerEntry("usage", Decimal("-2")),
        LedgerEntry("reversal", Decimal("2")),
        LedgerEntry("usage", Decimal("-1")),
        LedgerEntry("accrual", Decimal("1")),
    )
    projected = project_balance(entries)
    assert projected.available == Decimal("5")
    assert projected.used == Decimal("1")
    assert can_debit(projected.available, Decimal("5"), False)
    assert not can_debit(projected.available, Decimal("6"), False)
    assert can_debit(projected.available, Decimal("6"), True)
    assert split_year_end(
        Decimal("5"),
        carry_over_max=Decimal("2"),
        convertible=True,
        max_conversion_days=Decimal("1"),
    ) == (Decimal("2"), Decimal("2"), Decimal("1"))
    assert split_year_end(
        Decimal("0"),
        carry_over_max=Decimal("5"),
        convertible=False,
        max_conversion_days=Decimal("0"),
    ) == (Decimal("0"), Decimal("0"), Decimal("0"))


def test_hypothesis_ledger_matches_signed_sum() -> None:
    from hypothesis import given
    from hypothesis import strategies as st

    kinds = st.sampled_from(
        [
            "entitlement",
            "accrual",
            "usage",
            "reversal",
            "carry_over",
            "adjustment",
            "expiry",
            "conversion",
        ]
    )
    signed = st.decimals(min_value="-2", max_value="2", places=2).filter(lambda d: d != 0)

    @given(st.lists(st.tuples(kinds, signed), max_size=30))
    def _check(rows: list[tuple[str, Decimal]]) -> None:
        fixed: list[LedgerEntry] = []
        for kind, days in rows:
            amount = days if kind not in {"usage", "expiry", "conversion"} else -abs(days)
            if kind == "reversal":
                amount = abs(days)
            fixed.append(LedgerEntry(kind, amount))
        projected = project_balance(tuple(fixed))
        assert projected.available == sum((entry.days for entry in fixed), Decimal("0"))

    _check()
