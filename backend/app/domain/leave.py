"""Leave day counting and ledger projection. Balances are a cache of the ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class LedgerEntry:
    entry_type: str
    days: Decimal


@dataclass(frozen=True)
class BalanceProjection:
    entitled: Decimal
    accrued: Decimal
    used: Decimal
    carried_over: Decimal
    adjusted: Decimal
    available: Decimal


def count_leave_days(
    start: date,
    end: date,
    *,
    rest_days: tuple[int, ...],
    holidays: frozenset[date],
    counts_weekends: bool,
    half_day: bool,
) -> Decimal:
    """Count chargeable days. Rest days and holidays are skipped unless counts_weekends.

    counts_weekends includes rest days. Holidays stay excluded: a holiday is not a
    weekend, and Philippine service-incentive practice does not charge it.
    A half-day request charges 0.5 only when that single day is chargeable.
    """
    if end < start:
        raise ValueError("leave end is before start")
    if half_day:
        if start != end:
            raise ValueError("half day covers one date")
        charged = _charges(start, rest_days, holidays, counts_weekends)
        return Decimal("0.5") if charged else Decimal("0")
    total = Decimal("0")
    cursor = start
    while cursor <= end:
        if _charges(cursor, rest_days, holidays, counts_weekends):
            total += Decimal("1")
        cursor += timedelta(days=1)
    return total


def _charges(
    day: date,
    rest_days: tuple[int, ...],
    holidays: frozenset[date],
    counts_weekends: bool,
) -> bool:
    if day in holidays:
        return False
    if day.weekday() in rest_days and not counts_weekends:
        return False
    return True


def ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def project_balance(entries: tuple[LedgerEntry, ...]) -> BalanceProjection:
    """Fold an append-only ledger. Usage and expiry and conversion reduce availability.

    entry days are signed: accruals positive, usage negative. The cached columns
    store the absolute movement in each bucket so a payslip can show them.
    """
    entitled = Decimal("0")
    accrued = Decimal("0")
    used = Decimal("0")
    carried = Decimal("0")
    adjusted = Decimal("0")
    signed = Decimal("0")
    for entry in entries:
        days = entry.days
        signed += days
        kind = entry.entry_type
        if kind == "entitlement":
            entitled += days
        elif kind == "accrual":
            accrued += days
        elif kind == "carry_over":
            carried += days
        elif kind == "adjustment":
            adjusted += days
        elif kind in {"usage", "reversal"}:
            used -= days
        elif kind in {"expiry", "conversion"}:
            adjusted += days
        else:
            raise ValueError(f"unknown ledger entry {kind}")
    available = entitled + accrued + carried + adjusted - used
    return BalanceProjection(
        entitled=entitled,
        accrued=accrued,
        used=used,
        carried_over=carried,
        adjusted=adjusted,
        available=available,
    )


def split_year_end(
    available: Decimal,
    *,
    carry_over_max: Decimal,
    convertible: bool,
    max_conversion_days: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Split unused days into carry, expiry, and cash conversion.

    The three amounts are never negative and they sum to the unused balance.
    A zero carry cap keeps nothing. Conversion is taken before carry.
    """
    if available <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0")
    convert = min(available, max_conversion_days) if convertible else Decimal("0")
    if convert < 0:
        convert = Decimal("0")
    rest = available - convert
    cap = carry_over_max if carry_over_max > 0 else Decimal("0")
    carry = min(rest, cap)
    return carry, rest - carry, convert


def can_debit(available: Decimal, days: Decimal, allow_negative: bool) -> bool:
    if days < 0:
        raise ValueError("debit days must be positive")
    if allow_negative:
        return True
    return available >= days
