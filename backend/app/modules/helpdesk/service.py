from __future__ import annotations

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.repository import TenantRepo, api
from app.modules.employees.models import Employee
from app.modules.helpdesk import policies
from app.modules.helpdesk.models import HrTicket
from app.modules.helpdesk.schemas import CommentWrite, TicketUpdate, TicketWrite


async def _employee(company: str, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if employee is None or employee.company_id != company or employee.deleted_at is not None:
        raise AppError("not_found", "Employee not found", 404)
    return employee


async def list_tickets(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_file(actor)
    extra = None
    if not policies.can_view_all(actor):
        if not actor.employee_id:
            raise AppError("forbidden", "You do not have access to this action", 403)
        extra = {"employee_id": actor.employee_id}
    return await TenantRepo(HrTicket, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("subject", "category", "status"),
        sort_fields={"created_at", "sla_due", "status"},
        q=q,
        sort="-created_at",
        extra=extra,
    )


async def get_ticket(actor: Actor, doc_id: str) -> dict:
    policies.company_id(actor)
    ticket = await TenantRepo(HrTicket, actor).get(doc_id)
    if not policies.can_see(actor, ticket.employee_id):
        raise AppError("forbidden", "You do not have access to this action", 403)
    return api(ticket)


async def create_ticket(actor: Actor, body: TicketWrite) -> dict:
    company = policies.require_file(actor)
    employee_id = (
        body.employee_id if policies.can_manage(actor) and body.employee_id else actor.employee_id
    )
    if not employee_id:
        raise AppError("bad_request", "No employee is linked to this user", 400)
    await _employee(company, employee_id)
    payload = body.model_copy(update={"employee_id": employee_id})
    ticket = await TenantRepo(HrTicket, actor).create(payload)
    ticket.sla_due = policies.add_business_days(utcnow(), 2)
    ticket.updated_at = utcnow()
    await ticket.save()
    return api(ticket)


async def update_ticket(actor: Actor, doc_id: str, body: TicketUpdate) -> dict:
    if not policies.can_manage(actor):
        raise AppError("forbidden", "You do not have access to this action", 403)
    policies.company_id(actor)
    return api(await TenantRepo(HrTicket, actor).update(doc_id, body))


async def add_comment(actor: Actor, doc_id: str, body: CommentWrite) -> dict:
    policies.company_id(actor)
    ticket = await TenantRepo(HrTicket, actor).get(doc_id)
    if not policies.can_see(actor, ticket.employee_id):
        raise AppError("forbidden", "You do not have access to this action", 403)
    ticket.comments = [
        *ticket.comments,
        {"author_id": actor.user_id, "body": body.body, "at": utcnow().isoformat()},
    ]
    ticket.updated_at = utcnow()
    ticket.updated_by = actor.user_id
    await ticket.save()
    return api(ticket)
