"""One approval engine for every module. Handlers run inside the caller's transaction."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.repository import api
from app.shared.models import (
    ApprovalAction,
    ApprovalDelegation,
    ApprovalFlow,
    ApprovalRequest,
    FlowCondition,
)

Handler = Callable[[ApprovalRequest, AsyncClientSession | None], Awaitable[None]]
HANDLERS: dict[str, Handler] = {}


def handles(subject_type: str) -> Callable[[Handler], Handler]:
    def decorate(fn: Handler) -> Handler:
        HANDLERS[subject_type] = fn
        return fn

    return decorate


def _match(conditions: list[FlowCondition], context: dict[str, Any]) -> bool:
    for condition in conditions:
        left = context.get(condition.field)
        if condition.op in {"gt", "gte", "lt", "lte"}:
            try:
                number = Decimal(str(left))
                target = Decimal(condition.value)
            except Exception:
                return False
            if condition.op == "gt" and not number > target:
                return False
            if condition.op == "gte" and not number >= target:
                return False
            if condition.op == "lt" and not number < target:
                return False
            if condition.op == "lte" and not number <= target:
                return False
        elif str(left) != condition.value:
            return False
    return True


async def _users_for_role(company_id: str, role_name: str) -> list[str]:
    from app.modules.identity.models import Role, User

    role = await Role.find_one(Role.company_id == company_id, Role.name == role_name)
    if role is None:
        return []
    users = await User.find(
        {"role_ids": str(role.id), "is_active": True, "company_id": company_id}
    ).to_list()
    return [str(user.id) for user in users]


async def _resolve_step(company_id: str, step: Any, context: dict[str, Any]) -> list[str]:
    kind = step.approver_type
    if kind == "specific_user" and step.approver_value:
        return [step.approver_value]
    if kind == "specific_role" and step.approver_value:
        return await _users_for_role(company_id, step.approver_value)
    if kind == "hr_admin":
        return await _users_for_role(company_id, "HR Admin")
    employee_id = str(context.get("employee_id") or "")
    if not employee_id:
        return []
    from app.modules.employees.models import Employee

    employee = await Employee.get(employee_id)
    if employee is None:
        return []
    if kind == "direct_manager" and employee.reports_to:
        manager = await Employee.get(employee.reports_to)
        if manager and manager.user_id:
            return [manager.user_id]
    if kind == "department_head" and employee.department_id:
        from app.modules.organization.models import Department

        department = await Department.get(employee.department_id)
        if department and department.head_employee_id:
            head = await Employee.get(department.head_employee_id)
            if head and head.user_id:
                return [head.user_id]
    return []


async def _with_delegates(company_id: str, approver_ids: list[str]) -> list[str]:
    now = utcnow()
    found = list(approver_ids)
    if not approver_ids:
        return found
    delegations = await ApprovalDelegation.find(
        {
            "company_id": company_id,
            "approver_id": {"$in": approver_ids},
            "starts_on": {"$lte": now},
            "ends_on": {"$gte": now},
        }
    ).to_list()
    for item in delegations:
        if item.delegate_id not in found:
            found.append(item.delegate_id)
    return found


async def _pending(request: ApprovalRequest) -> list[str]:
    flow = await ApprovalFlow.get(request.flow_id) if request.flow_id else None
    if flow is None:
        return []
    steps = [step for step in flow.steps if step.order == request.current_step]
    ids: list[str] = []
    for step in steps:
        ids.extend(await _resolve_step(request.company_id, step, request.context))
    return await _with_delegates(request.company_id, ids)


async def start_request(
    *,
    actor: Actor,
    module: str,
    subject_type: str,
    subject_id: str,
    context: dict[str, Any] | None = None,
    session: AsyncClientSession | None = None,
) -> ApprovalRequest:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    payload = context or {}
    flows = await ApprovalFlow.find(
        {"company_id": actor.company_id, "module": module, "is_active": True, "deleted_at": None}
    ).to_list()
    chosen = next((flow for flow in flows if _match(flow.conditions, payload)), None)
    if chosen is None:
        chosen = next((flow for flow in flows if not flow.conditions), None)
    request = ApprovalRequest(
        company_id=actor.company_id,
        module=module,
        subject_type=subject_type,
        subject_id=subject_id,
        flow_id=str(chosen.id) if chosen else None,
        requester_id=actor.user_id,
        context=payload,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    if chosen is None or not chosen.steps:
        request.status = "approved"
    await request.insert(session=session)
    if request.status == "pending":
        request.pending_approver_ids = await _pending(request)
        await request.save(session=session)
    else:
        handler = HANDLERS.get(subject_type)
        if handler is not None:
            await handler(request, session)
    return request


async def act(
    *,
    actor: Actor,
    request_id: str,
    action: str,
    remarks: str = "",
    session: AsyncClientSession | None = None,
) -> ApprovalRequest:
    if action not in {"approve", "reject", "return"}:
        raise AppError("bad_action", "Action must be approve, reject, or return", 400)
    request = await ApprovalRequest.get(request_id, session=session)
    if request is None or request.company_id != actor.company_id:
        raise AppError("not_found", "Approval not found", 404)
    if request.status != "pending":
        raise AppError("conflict", "This approval is already finished", 409)
    if actor.user_id not in request.pending_approver_ids and not actor.is_superadmin:
        raise AppError("forbidden", "This approval is not waiting for you", 403)
    request.actions.append(
        ApprovalAction(
            step=request.current_step,
            actor_id=actor.user_id,
            action=action,
            remarks=remarks,
            acted_at=utcnow(),
        )
    )
    if action == "approve":
        flow = await ApprovalFlow.get(request.flow_id) if request.flow_id else None
        orders = sorted({step.order for step in flow.steps}) if flow else []
        later = [order for order in orders if order > request.current_step]
        if later:
            request.current_step = later[0]
            request.pending_approver_ids = await _pending(request)
        else:
            request.status = "approved"
            request.pending_approver_ids = []
    else:
        request.status = "rejected" if action == "reject" else "returned"
        request.pending_approver_ids = []
    request.updated_at = utcnow()
    request.updated_by = actor.user_id
    await request.save(session=session)
    if request.status in {"approved", "rejected", "returned"}:
        handler = HANDLERS.get(request.subject_type)
        if handler is not None:
            await handler(request, session)
    return request


async def inbox(actor: Actor) -> list[dict[str, Any]]:
    if not actor.company_id:
        return []
    items = await ApprovalRequest.find(
        {
            "company_id": actor.company_id,
            "status": "pending",
            "pending_approver_ids": actor.user_id,
        }
    ).sort("-created_at").to_list()
    return [api(item) for item in items]


async def escalate_overdue(hours: int = 48) -> int:
    """Remind approvers. The hour threshold is the default; companies override it in settings."""
    cutoff = utcnow() - timedelta(hours=hours)
    stale = await ApprovalRequest.find(
        {"status": "pending", "updated_at": {"$lt": cutoff}}
    ).to_list()
    from app.shared.notify import notify

    for request in stale:
        for user_id in request.pending_approver_ids:
            await notify(
                company_id=request.company_id,
                user_id=user_id,
                event_key="approval.overdue",
                title="Approval still waiting",
                body=f"{request.module} request is still pending.",
            )
    return len(stale)
