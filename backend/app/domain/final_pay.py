"""Final pay. A negative net means the employee still owes the company."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.money import D, money


@dataclass(frozen=True)
class FinalPayInput:
    unpaid_salary: Decimal
    prorated_thirteenth: Decimal
    leave_conversion: Decimal
    annualization_refund_or_payable: Decimal
    accountabilities: Decimal


@dataclass(frozen=True)
class FinalPayLine:
    code: str
    label: str
    amount: Decimal


@dataclass(frozen=True)
class FinalPayResult:
    lines: tuple[FinalPayLine, ...]
    gross: Decimal
    deductions: Decimal
    net: Decimal
    employee_owes: bool


def compute_final_pay(data: FinalPayInput) -> FinalPayResult:
    lines: list[FinalPayLine] = []

    def add(code: str, label: str, amount: Decimal) -> None:
        rounded = money(amount)
        if rounded == 0:
            return
        lines.append(FinalPayLine(code, label, rounded))

    add("unpaid_salary", "Unpaid salary", data.unpaid_salary)
    add("thirteenth", "Prorated 13th month", data.prorated_thirteenth)
    add("leave_conversion", "Convertible leave", data.leave_conversion)
    tax = D(data.annualization_refund_or_payable)
    if tax < 0:
        add("tax_refund", "Annualization refund", -tax)
    elif tax > 0:
        add("tax_payable", "Annualization tax due", -tax)
    add("accountabilities", "Accountabilities", -D(data.accountabilities))

    gross = Decimal("0.00")
    deductions = Decimal("0.00")
    for line in lines:
        if line.amount >= 0:
            gross += line.amount
        else:
            deductions += -line.amount
    net = money(gross - deductions)
    return FinalPayResult(
        lines=tuple(lines),
        gross=money(gross),
        deductions=money(deductions),
        net=net,
        employee_owes=net < 0,
    )
