"""Resignation approval, clearance accountabilities, and final pay."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.errors import AppError
from app.core.money import money
from app.core.repository import TenantRepo, api
from app.domain.annualization import thirteenth_month
from app.domain.final_pay import FinalPayInput, compute_final_pay
from app.modules.assets.models import AssetAssignment
from app.modules.claims.models import CashAdvance
from app.modules.employees.models import Employee
from app.modules.offboarding import policies
from app.modules.offboarding.models import (
    Clearance,
    ClearanceItem,
    ExitInterview,
    FinalPay,
    Resignation,
)
from app.modules.offboarding.schemas import (
    ClearancePatch,
    ExitInterviewWrite,
    FinalPayRequest,
    ResignationWrite,
)
from app.modules.payroll.models import Loan, Payslip
from app.modules.training.models import TrainingBond
from app.shared.approvals import handles, start_request
from app.shared.models import ApprovalRequest
from app.shared.settings_store import GeneralSettings, get_settings_model


async def _page(
    actor: Actor,
    model,
    search: tuple[str, ...],
    page: int,
    page_size: int,
    q: str | None,
) -> dict:
    policies.require_view(actor)
    return await TenantRepo(model, actor).list(
        page=page,
        page_size=page_size,
        search_fields=search,
        sort_fields={"created_at", "filed_at", "status"},
        q=q,
        sort="-created_at",
    )


async def list_resignations(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    extra = None
    if not actor.has("offboarding.view") and not actor.has("offboarding.manage"):
        if not actor.employee_id:
            raise AppError("forbidden", "You do not have access to this action", 403)
        extra = {"employee_id": actor.employee_id}
    policies.require_view(actor)
    return await TenantRepo(Resignation, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("reason", "employee_id", "status"),
        sort_fields={"created_at", "filed_at"},
        q=q,
        sort="-created_at",
        extra=extra,
    )


async def get_resignation(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    doc = await TenantRepo(Resignation, actor).get(doc_id)
    if not actor.has("offboarding.view") and not actor.has("offboarding.manage"):
        if doc.employee_id != actor.employee_id:
            raise AppError("forbidden", "You do not have access to this action", 403)
    return api(doc)


async def create_resignation(actor: Actor, body: ResignationWrite) -> dict:
    policies.company_id(actor)
    if not policies.can_file_resignation(actor, body.employee_id):
        raise AppError("forbidden", "You do not have access to this action", 403)
    policies.assert_notice(body.filed_at, body.last_working_day)
    async with transaction() as session:
        doc = await TenantRepo(Resignation, actor).create(body, session=session)
        request = await start_request(
            actor=actor,
            module="offboarding",
            subject_type="resignation",
            subject_id=str(doc.id),
            context={
                "employee_id": doc.employee_id,
                "last_working_day": doc.last_working_day.isoformat(),
            },
            session=session,
        )
        doc.approval_request_id = str(request.id)
        doc.status = request.status
        doc.updated_at = utcnow()
        await doc.save(session=session)
    return api(doc)


async def update_resignation(actor: Actor, doc_id: str, body: ResignationWrite) -> dict:
    policies.require_manage(actor)
    policies.assert_notice(body.filed_at, body.last_working_day)
    return api(await TenantRepo(Resignation, actor).update(doc_id, body))


@handles("resignation")
async def on_resignation_decided(
    request: ApprovalRequest,
    session: AsyncClientSession | None,
) -> None:
    doc = await Resignation.get(request.subject_id, session=session)
    if doc is None or doc.company_id != request.company_id:
        return
    doc.status = request.status
    doc.updated_at = utcnow()
    await doc.save(session=session)


async def _employee(company: str, employee_id: str, session=None) -> Employee:
    employee = await Employee.get(employee_id, session=session)
    if employee is None or employee.company_id != company or employee.deleted_at is not None:
        raise AppError("not_found", "Employee not found", 404)
    return employee


def _has_item(items: list[ClearanceItem], key: str) -> bool:
    return any(item.remarks == key for item in items)


async def _unreturned(company: str, employee_id: str) -> list[AssetAssignment]:
    return await AssetAssignment.find(
        {"company_id": company, "employee_id": employee_id, "returned_at": None}
    ).to_list()


async def _sync_items(clearance: Clearance, company: str, employee_id: str) -> bool:
    today = utcnow().date()
    assignments = await _unreturned(company, employee_id)
    for assignment in assignments:
        key = f"asset:{assignment.asset_id}"
        if not _has_item(clearance.items, key):
            clearance.items.append(
                ClearanceItem(
                    department="Admin",
                    item=f"Unreturned asset {assignment.asset_id}",
                    remarks=key,
                    blocking=True,
                )
            )
    advances = await CashAdvance.find({"company_id": company, "employee_id": employee_id}).to_list()
    for advance in advances:
        if money(advance.balance) <= 0:
            continue
        key = f"cash_advance:{advance.id}"
        if not _has_item(clearance.items, key):
            amount = format(money(advance.balance), "f")
            clearance.items.append(
                ClearanceItem(
                    department="Finance",
                    item=f"Cash advance balance {amount}",
                    remarks=key,
                    blocking=True,
                )
            )
    loans = await Loan.find({"company_id": company, "employee_id": employee_id}).to_list()
    for loan in loans:
        if money(loan.balance) <= 0:
            continue
        key = f"loan:{loan.id}"
        if not _has_item(clearance.items, key):
            amount = format(money(loan.balance), "f")
            clearance.items.append(
                ClearanceItem(
                    department="Finance",
                    item=f"Loan balance {amount}",
                    remarks=key,
                    blocking=True,
                )
            )
    bonds = await TrainingBond.find({"company_id": company, "employee_id": employee_id}).to_list()
    for bond in bonds:
        if bond.bond_until <= today:
            continue
        key = f"bond:{bond.id}"
        if not _has_item(clearance.items, key):
            clearance.items.append(
                ClearanceItem(
                    department="HR",
                    item=f"Unserved training bond until {bond.bond_until.isoformat()}",
                    remarks=key,
                    blocking=True,
                )
            )
    return bool(assignments)


async def get_clearance(actor: Actor, employee_id: str) -> dict:
    company = policies.require_view(actor)
    if not actor.has("offboarding.view") and not actor.has("offboarding.manage"):
        if actor.employee_id != employee_id:
            raise AppError("forbidden", "You do not have access to this action", 403)
    await _employee(company, employee_id)
    clearance = await Clearance.find_one({"company_id": company, "employee_id": employee_id})
    if clearance is None:
        clearance = Clearance(
            company_id=company,
            employee_id=employee_id,
            items=[],
            status="open",
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await clearance.insert()
    unreturned = await _sync_items(clearance, company, employee_id)
    clearance.status = policies.clearance_status(clearance.items, unreturned)
    clearance.updated_at = utcnow()
    clearance.updated_by = actor.user_id
    await clearance.save()
    return api(clearance)


async def patch_clearance_item(
    actor: Actor,
    employee_id: str,
    item_id: str,
    body: ClearancePatch,
) -> dict:
    company = policies.require_manage(actor)
    await _employee(company, employee_id)
    clearance = await Clearance.find_one({"company_id": company, "employee_id": employee_id})
    if clearance is None:
        raise AppError("not_found", "Clearance not found", 404)
    unreturned = await _sync_items(clearance, company, employee_id)
    index = policies.parse_index(item_id, len(clearance.items))
    item = clearance.items[index]
    item.cleared_by = actor.user_id
    item.cleared_at = utcnow()
    if body.remarks and ":" not in item.remarks:
        item.remarks = body.remarks
    clearance.status = policies.clearance_status(clearance.items, unreturned)
    clearance.updated_at = utcnow()
    clearance.updated_by = actor.user_id
    await clearance.save()
    return api(clearance)


async def list_interviews(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, ExitInterview, ("employee_id",), page, page_size, q)


async def get_interview(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(ExitInterview, actor).get(doc_id))


async def create_interview(actor: Actor, body: ExitInterviewWrite) -> dict:
    company = policies.require_manage(actor)
    existing = await ExitInterview.find_one(
        {"company_id": company, "employee_id": body.employee_id}
    )
    if existing is not None:
        raise AppError("conflict", "An exit interview already exists", 409)
    return api(await TenantRepo(ExitInterview, actor).create(body))


async def update_interview(actor: Actor, doc_id: str, body: ExitInterviewWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(ExitInterview, actor).update(doc_id, body))


async def _resignation_for(company: str, employee_id: str) -> Resignation | None:
    rows = await Resignation.find({"company_id": company, "employee_id": employee_id}).to_list()
    approved = [row for row in rows if row.status == "approved"]
    pool = approved or [row for row in rows if row.status not in {"rejected", "returned"}]
    if not pool:
        return None
    return max(pool, key=lambda row: row.last_working_day)


def _daily_rate(employee: Employee) -> Decimal:
    comp = employee.current_compensation
    if comp is None:
        return Decimal("0.00")
    daily = money(comp.daily_rate)
    if daily > 0:
        return daily
    if comp.pay_basis == "monthly":
        return money(money(comp.basic_salary) / Decimal(22))
    if comp.pay_basis == "hourly":
        return money(money(comp.hourly_rate) * Decimal(8))
    return money(comp.basic_salary)


async def _accountabilities(company: str, employee_id: str) -> Decimal:
    today = utcnow().date()
    amounts: list[Decimal] = []
    loans = await Loan.find({"company_id": company, "employee_id": employee_id}).to_list()
    amounts.extend(money(loan.balance) for loan in loans)
    advances = await CashAdvance.find({"company_id": company, "employee_id": employee_id}).to_list()
    amounts.extend(money(advance.balance) for advance in advances)
    bonds = await TrainingBond.find({"company_id": company, "employee_id": employee_id}).to_list()
    amounts.extend(money(bond.amount) for bond in bonds if bond.bond_until > today)
    return policies.accountability_total(amounts)


async def compute_employee_final_pay(actor: Actor, employee_id: str, body: FinalPayRequest) -> dict:
    company = policies.require_manage(actor)
    employee = await _employee(company, employee_id)
    existing = await FinalPay.find_one({"company_id": company, "employee_id": employee_id})
    if existing is not None and existing.status == "released":
        raise AppError("conflict", "Final pay is already released", 409)
    resignation = await _resignation_for(company, employee_id)
    today = utcnow().date()
    last_day = resignation.last_working_day if resignation else today
    if body.unpaid_salary is not None:
        unpaid = money(body.unpaid_salary)
    else:
        days = policies.remaining_days(last_day, today, body.remaining_days)
        unpaid = policies.prorate_salary(_daily_rate(employee), days)
    slips = await Payslip.find({"company_id": company, "employee_id": employee_id}).to_list()
    basic = Decimal("0.00")
    for slip in slips:
        if slip.created_at.year == today.year:
            basic += money(slip.basic_pay)
    basic += unpaid
    prorated = thirteenth_month(basic)
    owed = await _accountabilities(company, employee_id)
    result = compute_final_pay(
        FinalPayInput(
            unpaid_salary=unpaid,
            prorated_thirteenth=prorated,
            leave_conversion=money(body.leave_conversion),
            annualization_refund_or_payable=money(body.annualization_refund_or_payable),
            accountabilities=owed,
        )
    )
    raw = await get_settings_model(company, "general")
    general = raw if isinstance(raw, GeneralSettings) else GeneralSettings()
    target = last_day + timedelta(days=general.final_pay_release_days)
    components = [
        {"code": line.code, "label": line.label, "amount": format(line.amount, "f")}
        for line in result.lines
    ]
    if existing is None:
        existing = FinalPay(
            company_id=company,
            employee_id=employee_id,
            components=components,
            net=result.net,
            status="computed",
            target_release_date=target,
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await existing.insert()
    else:
        existing.components = components
        existing.net = result.net
        existing.status = "computed"
        existing.target_release_date = target
        existing.updated_at = utcnow()
        existing.updated_by = actor.user_id
        await existing.save()
    return api(existing)


async def approve_final_pay(actor: Actor, employee_id: str) -> dict:
    company = policies.require_manage(actor)
    final = await FinalPay.find_one({"company_id": company, "employee_id": employee_id})
    if final is None:
        raise AppError("not_found", "Final pay not found", 404)
    if final.status == "released":
        raise AppError("conflict", "Final pay is already released", 409)
    if final.status not in {"computed", "approved"}:
        raise AppError("conflict", "Compute final pay before approval", 409)
    final.status = "approved"
    final.updated_at = utcnow()
    final.updated_by = actor.user_id
    await final.save()
    return api(final)


async def release_final_pay(actor: Actor, employee_id: str) -> dict:
    company = policies.require_manage(actor)
    final = await FinalPay.find_one({"company_id": company, "employee_id": employee_id})
    if final is None:
        raise AppError("not_found", "Final pay not found", 404)
    if final.status != "approved":
        raise AppError("conflict", "Approve final pay before release", 409)
    resignation = await _resignation_for(company, employee_id)
    if resignation is None:
        raise AppError("conflict", "File a resignation before releasing final pay", 409)
    async with transaction() as session:
        current = await FinalPay.get(final.id, session=session)
        employee = await _employee(company, employee_id, session=session)
        if current is None or current.company_id != company:
            raise AppError("not_found", "Final pay not found", 404)
        current.status = "released"
        current.updated_at = utcnow()
        current.updated_by = actor.user_id
        await current.save(session=session)
        employee.employment_status = "separated"
        employee.separation_date = resignation.last_working_day
        if resignation.reason:
            employee.separation_reason = resignation.reason
        employee.revision += 1
        employee.updated_at = utcnow()
        employee.updated_by = actor.user_id
        await employee.save(session=session)
    return api(current)
