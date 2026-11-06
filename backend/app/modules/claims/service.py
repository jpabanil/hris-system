"""Claims, reimbursements, and cash advances. No FastAPI imports."""

from __future__ import annotations

from decimal import Decimal

from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.money import D, money, money_str
from app.core.repository import TenantRepo, api
from app.modules.claims import policies
from app.modules.claims.models import CashAdvance, Claim, ClaimType
from app.modules.claims.schemas import (
    CashAdvanceWrite,
    ClaimTypeWrite,
    ClaimWrite,
    LiquidationWrite,
)
from app.modules.employees.models import Employee
from app.shared.approvals import handles, start_request
from app.shared.models import ApprovalRequest


async def _employee(actor: Actor, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if (
        employee is None
        or employee.company_id != actor.company_id
        or employee.deleted_at is not None
    ):
        raise AppError("not_found", "Employee not found", 404)
    return employee


@handles("claim")
async def apply_claim_decision(
    request: ApprovalRequest, session: AsyncClientSession | None
) -> None:
    claim = await Claim.get(request.subject_id, session=session)
    if claim is None or claim.company_id != request.company_id:
        return
    claim.status = request.status
    claim.updated_at = utcnow()
    await claim.save(session=session)


async def list_claim_types(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_view(actor)
    return await TenantRepo(ClaimType, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("name",),
        sort_fields={"created_at", "name"},
        q=q,
        sort="name",
    )


async def create_claim_type(actor: Actor, body: ClaimTypeWrite) -> dict:
    policies.require_manage(actor)
    doc = await TenantRepo(ClaimType, actor).create(body)
    return api(doc)


async def update_claim_type(actor: Actor, type_id: str, body: ClaimTypeWrite) -> dict:
    policies.require_manage(actor)
    doc = await TenantRepo(ClaimType, actor).update(type_id, body)
    return api(doc)


async def delete_claim_type(actor: Actor, type_id: str) -> None:
    policies.require_manage(actor)
    await TenantRepo(ClaimType, actor).soft_delete(type_id)


async def list_claims(
    actor: Actor,
    page: int,
    page_size: int,
    q: str | None,
    employee_id: str | None,
    status: str | None,
) -> dict:
    if actor.has("claims.view") or actor.has("claims.manage"):
        policies.require_view(actor)
    elif actor.has("self.service") and actor.employee_id:
        employee_id = actor.employee_id
    else:
        raise AppError("forbidden", "You do not have access to this action", 403)
    extra: dict[str, str] = {}
    if employee_id:
        extra["employee_id"] = employee_id
    if status:
        extra["status"] = status
    return await TenantRepo(Claim, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("description", "status"),
        sort_fields={"created_at", "date", "status"},
        q=q,
        sort="-created_at",
        extra=extra or None,
    )


async def create_claim(actor: Actor, body: ClaimWrite) -> dict:
    policies.require_file(actor, body.employee_id)
    if body.paid_via not in {"payroll", "separate"}:
        raise AppError("bad_paid_via", "paid_via must be payroll or separate", 400)
    await _employee(actor, body.employee_id)
    claim_type = await TenantRepo(ClaimType, actor).get(body.claim_type_id)
    if not isinstance(claim_type, ClaimType):
        raise AppError("not_found", "Claim type not found", 404)
    if claim_type.requires_receipt and not body.receipt_keys:
        raise AppError("receipt_required", "A receipt is required for this claim", 400)
    if claim_type.monthly_limit is not None:
        existing = await Claim.find(
            {
                "company_id": policies.company_id(actor),
                "employee_id": body.employee_id,
                "claim_type_id": body.claim_type_id,
            }
        ).to_list()
        spent = sum(
            (
                D(item.amount)
                for item in existing
                if item.date.year == body.date.year
                and item.date.month == body.date.month
                and item.status != "rejected"
            ),
            Decimal("0"),
        )
        if money(spent + D(body.amount)) > D(claim_type.monthly_limit):
            raise AppError("limit_exceeded", "Monthly claim limit exceeded", 400)
    claim = Claim(
        company_id=policies.company_id(actor),
        employee_id=body.employee_id,
        claim_type_id=body.claim_type_id,
        date=body.date,
        amount=money(body.amount),
        description=body.description,
        receipt_keys=list(body.receipt_keys),
        status="pending",
        paid_via=body.paid_via,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await claim.insert()
    request = await start_request(
        actor=actor,
        module="claim",
        subject_type="claim",
        subject_id=str(claim.id),
        context={
            "employee_id": body.employee_id,
            "amount": money_str(body.amount),
            "claim_type_id": body.claim_type_id,
        },
    )
    stored = await Claim.get(str(claim.id))
    if stored is None:
        raise AppError("not_found", "Claim not found", 404)
    stored.approval_request_id = str(request.id)
    stored.updated_at = utcnow()
    stored.updated_by = actor.user_id
    await stored.save()
    return api(stored)


async def get_claim(actor: Actor, claim_id: str) -> dict:
    claim = await TenantRepo(Claim, actor).get(claim_id)
    if not isinstance(claim, Claim):
        raise AppError("not_found", "Claim not found", 404)
    if not (actor.has("claims.view") or actor.has("claims.manage")):
        if not (actor.has("self.service") and actor.employee_id == claim.employee_id):
            raise AppError("forbidden", "You do not have access to this action", 403)
    return api(claim)


async def update_claim(actor: Actor, claim_id: str, body: ClaimWrite) -> dict:
    policies.require_file(actor, body.employee_id)
    claim = await TenantRepo(Claim, actor).get(claim_id)
    if not isinstance(claim, Claim):
        raise AppError("not_found", "Claim not found", 404)
    if claim.period_id or claim.status in {"approved", "rejected"}:
        raise AppError("conflict", "This claim can no longer be edited", 409)
    await _employee(actor, body.employee_id)
    claim.employee_id = body.employee_id
    claim.claim_type_id = body.claim_type_id
    claim.date = body.date
    claim.amount = money(body.amount)
    claim.description = body.description
    claim.receipt_keys = list(body.receipt_keys)
    claim.paid_via = body.paid_via
    claim.updated_at = utcnow()
    claim.updated_by = actor.user_id
    await claim.save()
    return api(claim)


async def delete_claim(actor: Actor, claim_id: str) -> None:
    claim = await TenantRepo(Claim, actor).get(claim_id)
    if not isinstance(claim, Claim):
        raise AppError("not_found", "Claim not found", 404)
    policies.require_file(actor, claim.employee_id)
    if claim.period_id or claim.status == "approved":
        raise AppError("conflict", "This claim can no longer be deleted", 409)
    await claim.delete()


async def list_advances(
    actor: Actor,
    page: int,
    page_size: int,
    q: str | None,
    employee_id: str | None,
    status: str | None,
) -> dict:
    if not (actor.has("claims.view") or actor.has("claims.manage")):
        if actor.has("self.service") and actor.employee_id:
            employee_id = actor.employee_id
        else:
            raise AppError("forbidden", "You do not have access to this action", 403)
    extra: dict[str, str] = {}
    if employee_id:
        extra["employee_id"] = employee_id
    if status:
        extra["status"] = status
    return await TenantRepo(CashAdvance, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("purpose", "status"),
        sort_fields={"created_at", "status"},
        q=q,
        sort="-created_at",
        extra=extra or None,
    )


async def create_advance(actor: Actor, body: CashAdvanceWrite) -> dict:
    policies.require_file(actor, body.employee_id)
    await _employee(actor, body.employee_id)
    balance = body.amount if body.balance is None else body.balance
    advance = CashAdvance(
        company_id=policies.company_id(actor),
        employee_id=body.employee_id,
        amount=money(body.amount),
        purpose=body.purpose,
        balance=money(balance),
        status=body.status or "open",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await advance.insert()
    return api(advance)


async def get_advance(actor: Actor, advance_id: str) -> dict:
    advance = await TenantRepo(CashAdvance, actor).get(advance_id)
    if not isinstance(advance, CashAdvance):
        raise AppError("not_found", "Cash advance not found", 404)
    if not (actor.has("claims.view") or actor.has("claims.manage")):
        if not (actor.has("self.service") and actor.employee_id == advance.employee_id):
            raise AppError("forbidden", "You do not have access to this action", 403)
    return api(advance)


async def update_advance(actor: Actor, advance_id: str, body: CashAdvanceWrite) -> dict:
    policies.require_manage(actor)
    advance = await TenantRepo(CashAdvance, actor).get(advance_id)
    if not isinstance(advance, CashAdvance):
        raise AppError("not_found", "Cash advance not found", 404)
    await _employee(actor, body.employee_id)
    advance.employee_id = body.employee_id
    advance.amount = money(body.amount)
    advance.purpose = body.purpose
    if body.balance is not None:
        advance.balance = money(body.balance)
    advance.status = body.status or advance.status
    advance.updated_at = utcnow()
    advance.updated_by = actor.user_id
    await advance.save()
    return api(advance)


async def liquidate_advance(actor: Actor, advance_id: str, body: LiquidationWrite) -> dict:
    advance = await TenantRepo(CashAdvance, actor).get(advance_id)
    if not isinstance(advance, CashAdvance):
        raise AppError("not_found", "Cash advance not found", 404)
    policies.require_file(actor, advance.employee_id)
    amount = money(body.amount)
    if amount <= 0:
        raise AppError("bad_amount", "Liquidation amount must be positive", 400)
    if amount > D(advance.balance):
        raise AppError("bad_amount", "Liquidation exceeds the balance", 400)
    when = body.at or utcnow().date()
    advance.liquidations.append(
        {"amount": money_str(amount), "remarks": body.remarks, "at": when.isoformat()}
    )
    advance.balance = money(D(advance.balance) - amount)
    if advance.balance == 0:
        advance.status = "liquidated"
    advance.updated_at = utcnow()
    advance.updated_by = actor.user_id
    await advance.save()
    return api(advance)
