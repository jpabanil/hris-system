"""Login, CSRF, company isolation, permissions, and multi-document transactions."""

from __future__ import annotations

from datetime import timedelta

import httpx
from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.modules.organization.models import Company
from app.shared.approvals import HANDLERS, act, start_request
from app.shared.models import ApprovalDelegation, ApprovalFlow, FlowStep
from tests.api.conftest import csrf
from tests.api.factories import DEV_PASSWORD, make_company, make_user


async def _login(http: httpx.AsyncClient, email: str) -> None:
    response = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEV_PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mfa_required"] is False
    assert body["user"]["email"] == email


async def test_login_me_refresh_logout(client: httpx.AsyncClient) -> None:
    company = await make_company("Acme", "acme")
    await make_user(email="hr@acme.example.com", company=company, role_name="HR Admin")

    await _login(client, "hr@acme.example.com")
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "hr@acme.example.com"
    assert "org.manage" in me.json()["permissions"]

    missing = await client.post("/api/v1/auth/refresh")
    assert missing.status_code == 403
    assert missing.json()["code"] == "csrf"

    refreshed = await client.post("/api/v1/auth/refresh", headers=csrf(client))
    assert refreshed.status_code == 200, refreshed.text
    me_again = await client.get("/api/v1/auth/me")
    assert me_again.status_code == 200

    logged_out = await client.post("/api/v1/auth/logout", headers=csrf(client))
    assert logged_out.status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mongo"] == "ok"
    assert body["ok"] is True


async def test_employee_cannot_manage_org(client: httpx.AsyncClient) -> None:
    company = await make_company("Staff Co", "staff-co")
    await make_user(email="ee@staff.example.com", company=company, role_name="Employee")
    await _login(client, "ee@staff.example.com")
    response = await client.post(
        "/api/v1/branches",
        json={"name": "HQ"},
        headers=csrf(client),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_company_isolation(client: httpx.AsyncClient) -> None:
    alpha = await make_company("Alpha", "alpha")
    beta = await make_company("Beta", "beta")
    await make_user(email="hr@alpha.example.com", company=alpha, role_name="HR Admin")
    await make_user(email="hr@beta.example.com", company=beta, role_name="HR Admin")

    await _login(client, "hr@alpha.example.com")
    created = await client.post(
        "/api/v1/branches",
        json={"name": "Manila", "city": "Manila"},
        headers=csrf(client),
    )
    assert created.status_code == 201, created.text
    branch_id = created.json()["id"]

    await client.post("/api/v1/auth/logout", headers=csrf(client))
    await _login(client, "hr@beta.example.com")
    listing = await client.get("/api/v1/branches")
    assert listing.status_code == 200
    assert listing.json()["items"] == []
    stolen = await client.put(
        f"/api/v1/branches/{branch_id}",
        json={"name": "Taken", "revision": 1},
        headers=csrf(client),
    )
    assert stolen.status_code == 404

    companies = await client.get("/api/v1/companies")
    assert [item["slug"] for item in companies.json()["items"]] == ["beta"]


async def test_transaction_commits_and_rolls_back(client: httpx.AsyncClient) -> None:
    async with transaction() as session:
        await Company(name="Kept", slug="kept-tx").insert(session=session)
        await Company(name="Kept Two", slug="kept-tx-2").insert(session=session)
    assert await Company.find_one(Company.slug == "kept-tx") is not None
    assert await Company.find_one(Company.slug == "kept-tx-2") is not None

    try:
        async with transaction() as session:
            await Company(name="Dropped", slug="dropped-tx").insert(session=session)
            raise RuntimeError("force rollback")
    except RuntimeError:
        pass
    assert await Company.find_one(Company.slug == "dropped-tx") is None


async def test_two_step_approval_with_delegation(client: httpx.AsyncClient) -> None:
    company = await make_company("Flow Co", "flow-co")
    requester = await make_user(email="req@flow.example.com", company=company, role_name="Employee")
    first = await make_user(
        email="one@flow.example.com", company=company, role_name="Department Manager"
    )
    delegate = await make_user(email="del@flow.example.com", company=company, role_name="HR Admin")
    second = await make_user(email="two@flow.example.com", company=company, role_name="HR Admin")
    company_id = str(company.id)
    flow = ApprovalFlow(
        company_id=company_id,
        module="dummy",
        name="Two step",
        steps=[
            FlowStep(order=1, approver_type="specific_user", approver_value=str(first.id)),
            FlowStep(order=2, approver_type="specific_user", approver_value=str(second.id)),
        ],
    )
    await flow.insert()
    now = utcnow()
    await ApprovalDelegation(
        company_id=company_id,
        approver_id=str(first.id),
        delegate_id=str(delegate.id),
        starts_on=now - timedelta(days=1),
        ends_on=now + timedelta(days=1),
    ).insert()

    seen: list[str] = []

    async def on_dummy(request, session) -> None:
        seen.append(request.status)

    HANDLERS["dummy_subject"] = on_dummy
    actor = Actor(user_id=str(requester.id), email=requester.email, company_id=company_id)
    request = await start_request(
        actor=actor,
        module="dummy",
        subject_type="dummy_subject",
        subject_id="subject-1",
        context={},
    )
    assert request.status == "pending"
    assert str(delegate.id) in request.pending_approver_ids
    assert str(first.id) in request.pending_approver_ids

    delegate_actor = Actor(
        user_id=str(delegate.id),
        email=delegate.email,
        company_id=company_id,
        permissions={"approvals.act"},
    )
    request = await act(
        actor=delegate_actor,
        request_id=str(request.id),
        action="approve",
        remarks="ok",
    )
    assert request.status == "pending"
    assert request.current_step == 2
    assert request.pending_approver_ids == [str(second.id)]

    second_actor = Actor(user_id=str(second.id), email=second.email, company_id=company_id)
    request = await act(actor=second_actor, request_id=str(request.id), action="approve")
    assert request.status == "approved"
    assert seen == ["approved"]
