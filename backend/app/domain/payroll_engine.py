"""Payroll computation. Inputs in, payslip out. No database access.

The step order matches docs/PAYROLL_RULES.md. De minimis excess is moved into
the taxable base before withholding tax so the excess is actually taxed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.core.money import D, money
from app.domain.annualization import TaxBracket, tax_from_brackets
from app.domain.contributions import StatutoryAmount, portion


@dataclass(frozen=True)
class SalarySlice:
    """Working days inside the period paid at one daily rate."""

    daily_rate: Decimal
    days: Decimal


@dataclass(frozen=True)
class PremiumInput:
    code: str
    label: str
    minutes: int
    multiplier: Decimal
    taxable: bool = True


@dataclass(frozen=True)
class AllowanceInput:
    code: str
    label: str
    amount: Decimal
    taxable: bool
    de_minimis_category: str | None = None
    annual_ceiling: Decimal | None = None
    ytd_in_category: Decimal = Decimal("0")


@dataclass(frozen=True)
class AdjustmentInput:
    code: str
    label: str
    amount: Decimal
    taxable: bool


@dataclass(frozen=True)
class ClaimInput:
    code: str
    label: str
    amount: Decimal
    taxable: bool


@dataclass(frozen=True)
class OtherDeduction:
    code: str
    label: str
    amount: Decimal
    kind: str
    ref_id: str | None = None


@dataclass(frozen=True)
class Ytd:
    gross: Decimal = Decimal("0")
    taxable: Decimal = Decimal("0")
    non_taxable: Decimal = Decimal("0")
    contributions: Decimal = Decimal("0")
    tax_withheld: Decimal = Decimal("0")
    thirteenth_and_other_benefits: Decimal = Decimal("0")
    basic: Decimal = Decimal("0")


@dataclass(frozen=True)
class PayLine:
    type: str
    code: str
    label: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    is_taxable: bool
    deferred: bool = False
    ref_id: str | None = None


@dataclass(frozen=True)
class PayslipResult:
    lines: tuple[PayLine, ...]
    basic_pay: Decimal
    gross: Decimal
    taxable_income: Decimal
    non_taxable_income: Decimal
    withholding_tax: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    deferred_amount: Decimal
    ytd: Ytd
    has_deferrals: bool


@dataclass(frozen=True)
class PayrollInput:
    employee_id: str
    pay_basis: str
    basic_salary: Decimal
    daily_rate: Decimal
    hourly_rate: Decimal
    periods_per_year: int
    period_start: date
    period_end: date
    working_days_in_period: Decimal
    days_employed_in_period: Decimal
    days_worked: Decimal
    hours_worked: Decimal
    absence_days: Decimal = Decimal("0")
    lwop_days: Decimal = Decimal("0")
    suspension_days: Decimal = Decimal("0")
    late_minutes: int = 0
    undertime_minutes: int = 0
    is_minimum_wage_earner: bool = False
    salary_slices: tuple[SalarySlice, ...] = ()
    premiums: tuple[PremiumInput, ...] = ()
    allowances: tuple[AllowanceInput, ...] = ()
    adjustments: tuple[AdjustmentInput, ...] = ()
    claims: tuple[ClaimInput, ...] = ()
    retro_pay: Decimal = Decimal("0")
    sss: StatutoryAmount = field(
        default_factory=lambda: StatutoryAmount(Decimal("0"), Decimal("0"))
    )
    philhealth: StatutoryAmount = field(
        default_factory=lambda: StatutoryAmount(Decimal("0"), Decimal("0"))
    )
    pagibig: StatutoryAmount = field(
        default_factory=lambda: StatutoryAmount(Decimal("0"), Decimal("0"))
    )
    contribution_timing: str = "split"
    period_index: int = 1
    periods_in_month: int = 1
    tax_brackets: tuple[TaxBracket, ...] = ()
    other_deductions: tuple[OtherDeduction, ...] = ()
    ytd: Ytd = field(default_factory=Ytd)
    # Lower index is taken first. Anything that does not fit is deferred.
    deduction_order: tuple[str, ...] = (
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


def _hours(minutes: int) -> Decimal:
    return Decimal(minutes) / Decimal(60)


def period_basic(data: PayrollInput) -> Decimal:
    if data.salary_slices:
        total = Decimal("0")
        for sliver in data.salary_slices:
            total += D(sliver.daily_rate) * D(sliver.days)
        return money(total)
    if data.pay_basis == "monthly":
        full = D(data.basic_salary) * Decimal(12) / Decimal(data.periods_per_year)
        employed = D(data.days_employed_in_period)
        working = D(data.working_days_in_period)
        if working > 0 and employed != working:
            return money(full * employed / working)
        return money(full)
    if data.pay_basis == "daily":
        return money(D(data.daily_rate) * D(data.days_worked))
    if data.pay_basis == "hourly":
        return money(D(data.hourly_rate) * D(data.hours_worked))
    raise ValueError(f"unknown pay basis {data.pay_basis}")


def compute_payroll(data: PayrollInput) -> PayslipResult:
    lines: list[PayLine] = []
    basic = period_basic(data)
    lines.append(
        PayLine(
            "earning",
            "basic",
            "Basic pay",
            Decimal(data.periods_per_year),
            data.basic_salary,
            basic,
            True,
        )
    )

    taxable_extra = Decimal("0")
    nontaxable_extra = Decimal("0")

    if data.pay_basis == "monthly":
        for code, label, days in (
            ("absence", "Absences", data.absence_days),
            ("lwop", "Leave without pay", data.lwop_days),
            ("suspension", "Suspension", data.suspension_days),
        ):
            if D(days) > 0:
                amount = money(D(data.daily_rate) * D(days))
                lines.append(
                    PayLine("earning", code, label, D(days), data.daily_rate, -amount, True)
                )
        for code, label, minutes in (
            ("late", "Late", data.late_minutes),
            ("undertime", "Undertime", data.undertime_minutes),
        ):
            if minutes > 0:
                amount = money(D(data.hourly_rate) * _hours(minutes))
                lines.append(
                    PayLine(
                        "earning",
                        code,
                        label,
                        _hours(minutes),
                        data.hourly_rate,
                        -amount,
                        True,
                    )
                )
    else:
        for code, label, minutes in (
            ("late", "Late", data.late_minutes),
            ("undertime", "Undertime", data.undertime_minutes),
        ):
            if minutes > 0:
                amount = money(D(data.hourly_rate) * _hours(minutes))
                lines.append(
                    PayLine(
                        "earning",
                        code,
                        label,
                        _hours(minutes),
                        data.hourly_rate,
                        -amount,
                        True,
                    )
                )

    mwe_statutory = Decimal("0")
    for premium in data.premiums:
        amount = money(D(data.hourly_rate) * _hours(premium.minutes) * D(premium.multiplier))
        if amount == 0:
            continue
        lines.append(
            PayLine(
                "earning",
                premium.code,
                premium.label,
                _hours(premium.minutes),
                money(D(data.hourly_rate) * D(premium.multiplier)),
                amount,
                premium.taxable and not data.is_minimum_wage_earner,
            )
        )
        if data.is_minimum_wage_earner and premium.taxable:
            mwe_statutory += amount
        elif premium.taxable:
            taxable_extra += amount
        else:
            nontaxable_extra += amount

    for allowance in data.allowances:
        amount = money(allowance.amount)
        taxable_part = amount if allowance.taxable else Decimal("0")
        nontax_part = Decimal("0") if allowance.taxable else amount
        if allowance.de_minimis_category and allowance.annual_ceiling is not None:
            room = D(allowance.annual_ceiling) - D(allowance.ytd_in_category)
            if room < 0:
                room = Decimal("0")
            nontax_part = money(min(amount, room))
            taxable_part = money(amount - nontax_part)
        if taxable_part:
            lines.append(
                PayLine(
                    "earning",
                    allowance.code,
                    allowance.label,
                    Decimal(1),
                    taxable_part,
                    taxable_part,
                    True,
                )
            )
            taxable_extra += taxable_part
        if nontax_part:
            lines.append(
                PayLine(
                    "earning",
                    f"{allowance.code}_nontax",
                    f"{allowance.label} (non-taxable)",
                    Decimal(1),
                    nontax_part,
                    nontax_part,
                    False,
                )
            )
            nontaxable_extra += nontax_part

    for adj in data.adjustments:
        amount = money(adj.amount)
        lines.append(
            PayLine("earning", adj.code, adj.label, Decimal(1), amount, amount, adj.taxable)
        )
        if adj.taxable:
            taxable_extra += amount
        else:
            nontaxable_extra += amount

    if D(data.retro_pay) != 0:
        retro = money(data.retro_pay)
        lines.append(PayLine("earning", "retro", "Retroactive pay", Decimal(1), retro, retro, True))
        taxable_extra += retro

    for claim in data.claims:
        amount = money(claim.amount)
        lines.append(
            PayLine("earning", claim.code, claim.label, Decimal(1), amount, amount, claim.taxable)
        )
        if claim.taxable:
            taxable_extra += amount
        else:
            nontaxable_extra += amount

    earning_sum = money(sum((line.amount for line in lines), Decimal("0")))
    if data.is_minimum_wage_earner:
        # Statutory basic, OT, holiday, night diff and hazard pay are exempt.
        statutory_basic = money(
            sum(
                (
                    line.amount
                    for line in lines
                    if line.code
                    in {"basic", "absence", "lwop", "suspension", "late", "undertime"}
                ),
                Decimal("0"),
            )
        )
        mwe_statutory += statutory_basic
        taxable_income_before_contrib = money(taxable_extra)
    else:
        taxable_income_before_contrib = money(
            sum((line.amount for line in lines if line.is_taxable), Decimal("0"))
        )

    def timed(amount: Decimal) -> Decimal:
        return portion(amount, data.contribution_timing, data.period_index, data.periods_in_month)

    statutory = [
        ("sss", "SSS", timed(data.sss.ee)),
        ("philhealth", "PhilHealth", timed(data.philhealth.ee)),
        ("pagibig", "Pag-IBIG", timed(data.pagibig.ee)),
    ]
    contributions = Decimal("0")
    for code, label, amount in statutory:
        if amount > 0:
            contributions += amount
            lines.append(PayLine("deduction", code, label, Decimal(1), amount, amount, False))
    contributions = money(contributions)

    taxable_income = money(max(Decimal("0"), taxable_income_before_contrib - contributions))
    tax = (
        tax_from_brackets(taxable_income, data.tax_brackets)
        if data.tax_brackets
        else Decimal("0.00")
    )
    if tax > 0:
        lines.append(PayLine("deduction", "tax", "Withholding tax", Decimal(1), tax, tax, False))

    for item in data.other_deductions:
        amount = money(item.amount)
        if amount <= 0:
            continue
        lines.append(
            PayLine(
                "deduction",
                item.code,
                item.label,
                Decimal(1),
                amount,
                amount,
                False,
                False,
                item.ref_id,
            )
        )

    gross = earning_sum
    # Take deductions in priority order. Net cannot go below zero.
    taken: dict[int, Decimal] = {}
    remaining = gross
    order = {kind: index for index, kind in enumerate(data.deduction_order)}

    def kind_of(line: PayLine) -> str:
        if line.code in {"sss", "philhealth", "pagibig", "tax"}:
            return line.code
        for item in data.other_deductions:
            if item.code == line.code:
                return item.kind
        return "other"

    deduction_lines = [line for line in lines if line.type == "deduction"]
    ranked = sorted(enumerate(deduction_lines), key=lambda pair: order.get(kind_of(pair[1]), 99))
    deferred_total = Decimal("0")
    final_lines: list[PayLine] = [line for line in lines if line.type != "deduction"]
    deferred_flags: dict[int, tuple[Decimal, Decimal]] = {}
    for index, line in ranked:
        if remaining <= 0:
            deferred_flags[index] = (Decimal("0.00"), line.amount)
            deferred_total += line.amount
            continue
        if line.amount <= remaining:
            taken[index] = line.amount
            remaining -= line.amount
        else:
            take = money(remaining)
            deferred_flags[index] = (take, money(line.amount - take))
            deferred_total += line.amount - take
            remaining = Decimal("0")
            taken[index] = take

    total_deductions = Decimal("0")
    for index, line in enumerate(deduction_lines):
        if index in deferred_flags:
            take, deferred_amt = deferred_flags[index]
            if take > 0:
                final_lines.append(
                    PayLine(
                        "deduction",
                        line.code,
                        line.label,
                        line.quantity,
                        line.rate,
                        take,
                        False,
                        False,
                        line.ref_id,
                    )
                )
                total_deductions += take
            if deferred_amt > 0:
                final_lines.append(
                    PayLine(
                        "deferred",
                        line.code,
                        f"{line.label} deferred",
                        line.quantity,
                        line.rate,
                        deferred_amt,
                        False,
                        True,
                        line.ref_id,
                    )
                )
        else:
            final_lines.append(line)
            total_deductions += line.amount

    total_deductions = money(total_deductions)
    net = money(gross - total_deductions)
    if net < 0:
        raise RuntimeError("payroll engine produced a negative net")

    nontaxable_income = money(
        nontaxable_extra + (mwe_statutory if data.is_minimum_wage_earner else Decimal("0"))
    )
    ytd = Ytd(
        gross=money(D(data.ytd.gross) + gross),
        taxable=money(D(data.ytd.taxable) + taxable_income),
        non_taxable=money(D(data.ytd.non_taxable) + nontaxable_income),
        contributions=money(D(data.ytd.contributions) + contributions),
        tax_withheld=money(
            D(data.ytd.tax_withheld)
            + (
                tax
                if any(
                    line.code == "tax"
                    and line.type == "deduction"
                    and not line.deferred
                    for line in final_lines
                )
                else Decimal("0")
            )
        ),
        thirteenth_and_other_benefits=data.ytd.thirteenth_and_other_benefits,
        basic=money(D(data.ytd.basic) + basic),
    )
    # Withheld tax is the amount actually taken, which may be deferred in part.
    tax_taken = money(
        sum(
            (
                line.amount
                for line in final_lines
                if line.code == "tax" and line.type == "deduction"
            ),
            Decimal("0"),
        )
    )
    ytd = Ytd(
        gross=ytd.gross,
        taxable=ytd.taxable,
        non_taxable=ytd.non_taxable,
        contributions=ytd.contributions,
        tax_withheld=money(D(data.ytd.tax_withheld) + tax_taken),
        thirteenth_and_other_benefits=ytd.thirteenth_and_other_benefits,
        basic=ytd.basic,
    )
    return PayslipResult(
        lines=tuple(final_lines),
        basic_pay=basic,
        gross=gross,
        taxable_income=taxable_income,
        non_taxable_income=nontaxable_income,
        withholding_tax=tax_taken,
        total_deductions=total_deductions,
        net_pay=net,
        deferred_amount=money(deferred_total),
        ytd=ytd,
        has_deferrals=deferred_total > 0,
    )
