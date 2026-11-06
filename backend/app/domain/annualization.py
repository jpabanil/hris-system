"""Year-end tax annualization and 13th-month pay. Brackets are data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.money import D, money


@dataclass(frozen=True)
class TaxBracket:
    start: Decimal
    base_tax: Decimal
    rate: Decimal


@dataclass(frozen=True)
class AnnualizationResult:
    annual_taxable: Decimal
    annual_tax_due: Decimal
    total_withheld: Decimal
    refund_or_payable: Decimal


def tax_from_brackets(taxable: Decimal, brackets: tuple[TaxBracket, ...]) -> Decimal:
    if not brackets:
        raise ValueError("tax brackets are empty")
    income = D(taxable)
    if income < 0:
        income = Decimal("0")
    chosen = brackets[0]
    for bracket in brackets:
        if income >= D(bracket.start):
            chosen = bracket
    excess = income - D(chosen.start)
    return money(D(chosen.base_tax) + excess * D(chosen.rate))


def annualize(
    *,
    ytd_taxable: Decimal,
    previous_employer_taxable: Decimal,
    ytd_withheld: Decimal,
    previous_employer_withheld: Decimal,
    brackets: tuple[TaxBracket, ...],
) -> AnnualizationResult:
    """Positive refund_or_payable means the employee still owes tax."""
    annual_taxable = money(D(ytd_taxable) + D(previous_employer_taxable))
    due = tax_from_brackets(annual_taxable, brackets)
    withheld = money(D(ytd_withheld) + D(previous_employer_withheld))
    return AnnualizationResult(
        annual_taxable=annual_taxable,
        annual_tax_due=due,
        total_withheld=withheld,
        refund_or_payable=money(due - withheld),
    )


def thirteenth_month(basic_earned_in_year: Decimal) -> Decimal:
    """Prorated 13th month is total basic salary actually earned, divided by 12."""
    return money(D(basic_earned_in_year) / Decimal(12))


def thirteenth_month_taxable_excess(
    thirteenth_and_other_benefits: Decimal, ceiling: Decimal
) -> Decimal:
    excess = D(thirteenth_and_other_benefits) - D(ceiling)
    if excess <= 0:
        return Decimal("0.00")
    return money(excess)
