"""Payroll separation of duties, locked recompute, and release rollback."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest
from app.core.actor import Actor
from app.core.errors import AppError
from app.modules.employees.models import CompensationSnapshot, Employee, PersonName
from app.modules.payroll.models import (
    Loan,
    LoanPayment,
    PayGroup,
    PayrollPeriod,
    PayrollRun,
    Payslip,
    PayslipLine,
    TaxBracketRow,
    TaxTable,
)
from app.modules.payroll.service import approve_period, compute_period, release_period
from bson import ObjectId
from tests.api.factories import make_company, make_user

ZERO = Decimal("0")
START = date(2026, 11, 1)
END = date(2026, 11, 30)


def _actor(
    user_id: str, company_id: str, permissions: set[str], *, impersonating: bool = False
) -> Actor:
    return Actor(
        user_id=user_id,
        email="payroll@example.com",
        company_id=company_id,
        permissions=permissions,
        is_impersonating=impersonating,
    )


async def _period(company_id: str, status: str) -> tuple[PayGroup, PayrollPeriod]:
    group = PayGroup(company_id=company_id, name="Monthly", frequency="monthly")
    await group.insert()
    period = PayrollPeriod(
        company_id=company_id,
        pay_group_id=str(group.id),
        start=START,
        end=END,
        attendance_cutoff=END,
        pay_date=END,
        status=status,
    )
    await period.insert()
    return group, period


def _slip(company_id: str, run_id: str, period_id: str, lines: list[PayslipLine]) -> Payslip:
    return Payslip(
        company_id=company_id,
        run_id=run_id,
        period_id=period_id,
        employee_id=str(ObjectId()),
        basic_pay=Decimal("30000"),
        gross=Decimal("30000"),
        taxable_income=Decimal("30000"),
        non_taxable_income=ZERO,
        withholding_tax=Decimal("2500"),
        total_deductions=Decimal("2500"),
        net_pay=Decimal("27500"),
        lines=lines,
    )


async def test_computer_cannot_approve_and_impersonation_is_blocked(
    client: httpx.AsyncClient,
) -> None:
    company = await make_company("Pay Co", "pay-co")
    computer = await make_user(
        email="computer@pay.example.com",
        company=company,
        role_name="Payroll Officer",
    )
    approver = await make_user(
        email="approver@pay.example.com",
        company=company,
        role_name="Payroll Approver",
    )
    company_id = str(company.id)
    _group, period = await _period(company_id, "for_approval")
    run = PayrollRun(
        company_id=company_id,
        period_id=str(period.id),
        computed_by=str(computer.id),
        status="for_approval",
    )
    await run.insert()

    both = _actor(
        str(computer.id),
        company_id,
        {"payroll.compute", "payroll.approve", "payroll.view"},
    )
    with pytest.raises(AppError) as same_person:
        await approve_period(both, str(period.id))
    assert same_person.value.status_code == 403
    assert same_person.value.code == "forbidden"

    posing = _actor(
        str(approver.id),
        company_id,
        {"payroll.approve", "payroll.view"},
        impersonating=True,
    )
    with pytest.raises(AppError) as impersonated:
        await approve_period(posing, str(period.id))
    assert impersonated.value.status_code == 403

    approved = await approve_period(
        _actor(str(approver.id), company_id, {"payroll.approve", "payroll.view"}),
        str(period.id),
    )
    assert approved["status"] == "approved"
    fresh = await PayrollRun.get(run.id)
    assert fresh is not None
    assert fresh.approved_by == str(approver.id)


async def test_locked_period_rejects_recompute(client: httpx.AsyncClient) -> None:
    company = await make_company("Lock Co", "lock-co")
    officer = await make_user(
        email="officer@lock.example.com",
        company=company,
        role_name="Payroll Officer",
    )
    _group, period = await _period(str(company.id), "locked")
    actor = _actor(str(officer.id), str(company.id), {"payroll.compute", "payroll.view"})
    with pytest.raises(AppError) as exc:
        await compute_period(actor, str(period.id))
    assert exc.value.status_code == 409
    assert exc.value.code == "conflict"
    runs = await PayrollRun.find({"period_id": str(period.id)}).to_list()
    assert runs == []


async def test_release_failure_rolls_back_payslips_and_loans(
    client: httpx.AsyncClient,
) -> None:
    company = await make_company("Release Co", "release-co")
    approver = await make_user(
        email="approver@release.example.com",
        company=company,
        role_name="Payroll Approver",
    )
    company_id = str(company.id)
    _group, period = await _period(company_id, "approved")
    run = PayrollRun(
        company_id=company_id,
        period_id=str(period.id),
        computed_by=str(ObjectId()),
        status="approved",
    )
    await run.insert()
    loan = Loan(
        company_id=company_id,
        employee_id=str(ObjectId()),
        type="company",
        principal=Decimal("1000"),
        amortization=Decimal("200"),
        balance=Decimal("1000"),
    )
    await loan.insert()
    first = _slip(company_id, str(run.id), str(period.id), [])
    second = _slip(
        company_id,
        str(run.id),
        str(period.id),
        [
            PayslipLine(
                type="deduction",
                code="company_loan",
                label="Company loan",
                amount=Decimal("200"),
                ref_id=str(ObjectId()),
            )
        ],
    )
    await first.insert()
    await second.insert()

    actor = _actor(str(approver.id), company_id, {"payroll.approve", "payroll.view"})
    with pytest.raises(AppError) as exc:
        await release_period(actor, str(period.id))
    assert exc.value.code == "not_found"

    period_after = await PayrollPeriod.get(period.id)
    first_after = await Payslip.get(first.id)
    loan_after = await Loan.get(loan.id)
    payments = await LoanPayment.find({"company_id": company_id}).to_list()
    assert period_after is not None and period_after.status == "approved"
    assert first_after is not None and first_after.is_published is False
    assert loan_after is not None and loan_after.balance == Decimal("1000")
    assert payments == []
    run_after = await PayrollRun.get(run.id)
    assert run_after is not None and run_after.status == "approved"


_MONTHLY_TAX = (
    ("0", "0", "0"),
    ("20833.33", "0", "0.15"),
    ("33333.33", "1875.00", "0.20"),
    ("66666.67", "8541.67", "0.25"),
    ("166666.67", "33541.67", "0.30"),
    ("666666.67", "183541.67", "0.35"),
)


async def _monthly_employee(company_id: str, group_id: str) -> Employee:
    employee = Employee(
        company_id=company_id,
        employee_no="EMP-00001",
        name=PersonName(first="Liza", last="Reyes"),
        employment_status="active",
        date_hired=date(2024, 1, 8),
        pay_group_id=group_id,
        current_compensation=CompensationSnapshot(
            basic_salary=Decimal("30000"),
            pay_basis="monthly",
            daily_rate=Decimal("1379.31"),
            hourly_rate=Decimal("172.41"),
        ),
    )
    await employee.insert()
    return employee


async def test_missing_tax_table_does_not_open_a_run(client: httpx.AsyncClient) -> None:
    company = await make_company("Tax Co", "tax-co")
    officer = await make_user(
        email="officer@tax.example.com",
        company=company,
        role_name="Payroll Officer",
    )
    _group, period = await _period(str(company.id), "draft")
    actor = _actor(str(officer.id), str(company.id), {"payroll.compute", "payroll.view"})
    with pytest.raises(AppError) as exc:
        await compute_period(actor, str(period.id))
    assert exc.value.code == "tax_table_missing"
    assert await PayrollRun.find({"period_id": str(period.id)}).to_list() == []


async def test_compute_monthly_regular_matches_golden_net(client: httpx.AsyncClient) -> None:
    company = await make_company("Golden Co", "golden-co")
    officer = await make_user(
        email="officer@golden.example.com",
        company=company,
        role_name="Payroll Officer",
    )
    company_id = str(company.id)
    group, period = await _period(company_id, "draft")
    await _monthly_employee(company_id, str(group.id))
    await TaxTable(
        company_id=company_id,
        effective_from=date(2026, 1, 1),
        frequency="monthly",
        brackets=[TaxBracketRow(start=a, base_tax=b, rate=c) for a, b, c in _MONTHLY_TAX],
    ).insert()
    actor = _actor(str(officer.id), company_id, {"payroll.compute", "payroll.view"})
    body = await compute_period(actor, str(period.id))
    assert body["status"] == "computed"
    assert body["period_status"] == "computed"
    slips = await Payslip.find({"company_id": company_id}).to_list()
    assert len(slips) == 1
    assert slips[0].net_pay == Decimal("26542.50")
    assert slips[0].withholding_tax == Decimal("1007.50")
    assert slips[0].basic_pay == Decimal("30000.00")
