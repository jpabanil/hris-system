"""Leave approval writes the ledger, cancel reverses it, and rebuild matches."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
from app.modules.employees.models import Employee, PersonName
from app.modules.leave.models import LeaveBalance
from app.modules.leave.service import rebuild_balances
from tests.api.conftest import csrf
from tests.api.factories import DEV_PASSWORD, make_company, make_user

DAY = "2026-11-04"


async def _login(http: httpx.AsyncClient, email: str) -> None:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEV_PASSWORD},
    )
    assert response.status_code == 200, response.text


def _used(items: list[dict], employee_id: str) -> Decimal:
    match = [item for item in items if item["employee_id"] == employee_id]
    assert len(match) == 1, items
    return Decimal(match[0]["used"])


async def test_leave_approve_cancel_refile_and_rebuild(client: httpx.AsyncClient) -> None:
    company = await make_company("Leave Co", "leave-co")
    await make_user(email="hr@leave.example.com", company=company, role_name="HR Admin")
    employee = Employee(
        company_id=str(company.id),
        employee_no="EMP-001",
        name=PersonName(first="Ana", last="Cruz"),
        date_hired=date(2024, 1, 15),
    )
    await employee.insert()
    employee_id = str(employee.id)

    await _login(client, "hr@leave.example.com")
    created = await client.post(
        "/api/v1/leave-types",
        headers=csrf(client),
        json={
            "code": "VL",
            "name": "Vacation",
            "annual_entitlement": "15",
            "attachment_required_after_days": "99",
            "min_notice_days": 0,
        },
    )
    assert created.status_code == 201, created.text
    type_id = created.json()["id"]

    adjusted = await client.post(
        "/api/v1/leave-balances/adjust",
        headers=csrf(client),
        json={
            "employee_id": employee_id,
            "leave_type_id": type_id,
            "year": 2026,
            "days": "5",
            "reason": "opening",
        },
    )
    assert adjusted.status_code == 200, adjusted.text
    assert Decimal(adjusted.json()["adjusted"]) == Decimal("5")
    assert Decimal(adjusted.json()["used"]) == Decimal("0")

    filed = await client.post(
        "/api/v1/leave-requests",
        headers=csrf(client),
        json={
            "employee_id": employee_id,
            "leave_type_id": type_id,
            "start_date": DAY,
            "end_date": DAY,
            "reason": "errand",
        },
    )
    assert filed.status_code == 201, filed.text
    assert filed.json()["status"] == "approved"
    request_id = filed.json()["id"]

    shown = await client.get(
        "/api/v1/leave/calendar",
        params={"start": "2026-11-01", "end": "2026-11-30"},
    )
    assert shown.status_code == 200, shown.text
    assert request_id in [item["id"] for item in shown.json()["items"]]

    balances = await client.get(
        "/api/v1/leave-balances",
        params={"employee_id": employee_id, "year": 2026},
    )
    assert balances.status_code == 200, balances.text
    assert _used(balances.json()["items"], employee_id) == Decimal("1")

    cancelled = await client.post(
        f"/api/v1/leave-requests/{request_id}/cancel",
        headers=csrf(client),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    balances = await client.get(
        "/api/v1/leave-balances",
        params={"employee_id": employee_id, "year": 2026},
    )
    assert _used(balances.json()["items"], employee_id) == Decimal("0")

    again = await client.post(
        "/api/v1/leave-requests",
        headers=csrf(client),
        json={
            "employee_id": employee_id,
            "leave_type_id": type_id,
            "start_date": DAY,
            "end_date": DAY,
            "reason": "errand again",
        },
    )
    assert again.status_code == 201, again.text
    assert again.json()["status"] == "approved"

    stored = await LeaveBalance.find_one({"employee_id": employee_id, "year": 2026})
    assert stored is not None
    stored.used = "9.00"
    await stored.save()

    await rebuild_balances(str(company.id))
    balances = await client.get(
        "/api/v1/leave-balances",
        params={"employee_id": employee_id, "year": 2026},
    )
    assert _used(balances.json()["items"], employee_id) == Decimal("1")
    refreshed = await LeaveBalance.get(stored.id)
    assert refreshed is not None
    assert Decimal(refreshed.adjusted) == Decimal("5")


async def test_year_end_carries_the_cap_and_is_idempotent(client: httpx.AsyncClient) -> None:
    company = await make_company("Carry Co", "carry-co")
    await make_user(email="hr@carry.example.com", company=company, role_name="HR Admin")
    employee = Employee(
        company_id=str(company.id),
        employee_no="EMP-009",
        name=PersonName(first="Nilo", last="Garcia"),
        date_hired=date(2022, 2, 1),
    )
    await employee.insert()
    await _login(client, "hr@carry.example.com")
    created = await client.post(
        "/api/v1/leave-types",
        headers=csrf(client),
        json={
            "code": "VL",
            "name": "Vacation",
            "annual_entitlement": "15",
            "carry_over_max": "2",
            "attachment_required_after_days": "99",
        },
    )
    assert created.status_code == 201, created.text
    adjusted = await client.post(
        "/api/v1/leave-balances/adjust",
        headers=csrf(client),
        json={
            "employee_id": str(employee.id),
            "leave_type_id": created.json()["id"],
            "year": 2026,
            "days": "5",
            "reason": "opening",
        },
    )
    assert adjusted.status_code == 200, adjusted.text

    closed = await client.post(
        "/api/v1/leave-balances/close-year",
        params={"year": 2026},
        headers=csrf(client),
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["closed"] == 1
    again = await client.post(
        "/api/v1/leave-balances/close-year",
        params={"year": 2026},
        headers=csrf(client),
    )
    assert again.json()["closed"] == 0

    this_year = await client.get(
        "/api/v1/leave-balances",
        params={"employee_id": str(employee.id), "year": 2026},
    )
    next_year = await client.get(
        "/api/v1/leave-balances",
        params={"employee_id": str(employee.id), "year": 2027},
    )
    assert Decimal(this_year.json()["items"][0]["available"]) == Decimal("0")
    assert Decimal(next_year.json()["items"][0]["carried_over"]) == Decimal("2")
    assert Decimal(next_year.json()["items"][0]["available"]) == Decimal("2")
