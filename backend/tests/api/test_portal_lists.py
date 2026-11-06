"""Portal lists stay inside the signed-in employee unless the role can view all."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
from app.modules.attendance.models import AttendanceLog
from app.modules.employees.models import Employee, PersonName
from app.modules.payroll.models import PayGroup, PayrollPeriod, Payslip
from tests.api.factories import DEV_PASSWORD, make_company, make_user

ZERO = Decimal("0")


async def _login(http: httpx.AsyncClient, email: str) -> None:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEV_PASSWORD},
    )
    assert response.status_code == 200, response.text


def _slip(company_id: str, employee_id: str, period_id: str, *, published: bool) -> Payslip:
    return Payslip(
        company_id=company_id,
        run_id="run-portal",
        period_id=period_id,
        employee_id=employee_id,
        basic_pay=Decimal("1000"),
        gross=Decimal("1000"),
        taxable_income=Decimal("1000"),
        non_taxable_income=ZERO,
        withholding_tax=ZERO,
        total_deductions=ZERO,
        net_pay=Decimal("1000"),
        is_published=published,
    )


async def test_portal_lists_and_report_catalog(client: httpx.AsyncClient) -> None:
    company = await make_company("Portal Co", "portal-co")
    employee = Employee(
        company_id=str(company.id),
        employee_no="EMP-1",
        name=PersonName(first="Mia", last="Santos"),
    )
    other = Employee(
        company_id=str(company.id),
        employee_no="EMP-2",
        name=PersonName(first="Jon", last="Cruz"),
    )
    await employee.insert()
    await other.insert()
    staff = await make_user(
        email="ee@portal.example.com",
        company=company,
        role_name="Employee",
    )
    staff.employee_id = str(employee.id)
    await staff.save()
    await make_user(email="hr@portal.example.com", company=company, role_name="HR Admin")
    group = PayGroup(company_id=str(company.id), name="Monthly", frequency="monthly")
    await group.insert()
    period = PayrollPeriod(
        company_id=str(company.id),
        pay_group_id=str(group.id),
        start=date(2026, 10, 1),
        end=date(2026, 10, 31),
        attendance_cutoff=date(2026, 10, 31),
        pay_date=date(2026, 10, 31),
        status="released",
    )
    await period.insert()
    mine = _slip(str(company.id), str(employee.id), str(period.id), published=True)
    hidden = _slip(str(company.id), str(employee.id), str(period.id), published=False)
    theirs = _slip(str(company.id), str(other.id), str(period.id), published=True)
    hidden.run_id = "run-hidden"
    theirs.run_id = "run-other"
    await mine.insert()
    await hidden.insert()
    await theirs.insert()
    await AttendanceLog(
        company_id=str(company.id),
        employee_id=str(employee.id),
        logged_at=datetime(2026, 11, 5, 1, 0, tzinfo=UTC),
        type="in",
        source="pwa",
    ).insert()
    await AttendanceLog(
        company_id=str(company.id),
        employee_id=str(other.id),
        logged_at=datetime(2026, 11, 5, 1, 5, tzinfo=UTC),
        type="in",
        source="pwa",
    ).insert()

    await _login(client, "ee@portal.example.com")
    slips = await client.get("/api/v1/payslips")
    assert slips.status_code == 200, slips.text
    ids = {item["id"] for item in slips.json()["items"]}
    assert ids == {str(mine.id)}
    assert slips.json()["items"][0]["pay_date"] == "2026-10-31"
    logs = await client.get("/api/v1/attendance-logs")
    assert logs.status_code == 200, logs.text
    assert len(logs.json()["items"]) == 1
    assert logs.json()["items"][0]["employee_id"] == str(employee.id)

    await _login(client, "hr@portal.example.com")
    catalog = await client.get("/api/v1/reports")
    assert catalog.status_code == 200, catalog.text
    names = {item["id"] for item in catalog.json()["items"]}
    assert "headcount" in names
    assert "payroll-register" in names
    all_slips = await client.get("/api/v1/payslips")
    assert all_slips.json()["total"] == 3
