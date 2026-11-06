"""Statutory contribution lookup. Tables are data; these helpers apply them.

SSS brackets follow the 2025/2026 RA 11199 shape (15% of MSC, MSC 5,000–35,000).
PhilHealth is 5% split equally, floor 10,000, ceiling 100,000.
Pag-IBIG is 1%/2% employee and 2% employer, fund salary capped at 10,000.
The payroll officer must confirm the seeded rows against the current circulars.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.money import D, money


@dataclass(frozen=True)
class StatutoryAmount:
    ee: Decimal
    er: Decimal
    ec: Decimal = Decimal("0.00")
    mpf: Decimal = Decimal("0.00")
    mpf_er: Decimal = Decimal("0.00")
    basis: Decimal = Decimal("0.00")


def portion(full: Decimal, timing: str, period_index: int, periods_in_month: int) -> Decimal:
    """Slice a monthly statutory amount across the cutoffs in that month.

    split — even share each cutoff.
    first_cutoff — full amount on period 1, zero after.
    second_cutoff — full amount on the last cutoff of the month.
    A monthly pay group has one period, so every timing returns the full amount.
    """
    if periods_in_month <= 1:
        return money(full)
    if timing == "first_cutoff":
        return money(full) if period_index == 1 else Decimal("0.00")
    if timing == "second_cutoff":
        return money(full) if period_index == periods_in_month else Decimal("0.00")
    share = D(full) / Decimal(periods_in_month)
    return money(share)


def sss_msc(monthly_salary: Decimal) -> Decimal:
    """Monthly salary credit. Below 5,250 → 5,000. 34,750 and above → 35,000.

    The steps in between round the salary to the nearest 500, half up,
    which matches the published 500-peso brackets (5,250–5,749.99 → 5,500).
    """
    salary = D(monthly_salary)
    if salary < Decimal("5250"):
        return Decimal("5000")
    if salary >= Decimal("34750"):
        return Decimal("35000")
    steps = (salary / Decimal("500")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return steps * Decimal("500")


def sss_amount(monthly_salary: Decimal) -> StatutoryAmount:
    msc = sss_msc(monthly_salary)
    regular = min(msc, Decimal("20000"))
    mpf_base = msc - regular
    ee = money(msc * Decimal("0.05"))
    er = money(msc * Decimal("0.10"))
    ec = Decimal("10.00") if msc < Decimal("15000") else Decimal("30.00")
    return StatutoryAmount(
        ee=ee,
        er=er,
        ec=ec,
        mpf=money(mpf_base * Decimal("0.05")),
        mpf_er=money(mpf_base * Decimal("0.10")),
        basis=msc,
    )


def philhealth_amount(monthly_salary: Decimal) -> StatutoryAmount:
    salary = D(monthly_salary)
    if salary < Decimal("10000"):
        base = Decimal("10000")
    elif salary > Decimal("100000"):
        base = Decimal("100000")
    else:
        base = salary
    share = money(base * Decimal("0.025"))
    return StatutoryAmount(ee=share, er=share, basis=base)


def pagibig_amount(monthly_salary: Decimal) -> StatutoryAmount:
    salary = D(monthly_salary)
    if salary <= Decimal("1500"):
        return StatutoryAmount(
            ee=money(salary * Decimal("0.01")),
            er=money(salary * Decimal("0.02")),
            basis=salary,
        )
    base = min(salary, Decimal("10000"))
    return StatutoryAmount(
        ee=money(base * Decimal("0.02")),
        er=money(base * Decimal("0.02")),
        basis=base,
    )
