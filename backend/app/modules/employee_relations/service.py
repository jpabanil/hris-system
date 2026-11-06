"""Offenses, incidents, the twin-notice case machine, grievances, and policies."""

from __future__ import annotations

from datetime import timedelta

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.encryption import decrypt, encrypt
from app.core.errors import AppError
from app.core.repository import TenantRepo, api
from app.modules.employee_relations import policies
from app.modules.employee_relations.models import (
    DisciplinaryCase,
    Grievance,
    IncidentReport,
    Offense,
    Policy,
    PolicyAcknowledgment,
)
from app.modules.employee_relations.schemas import (
    CaseWrite,
    DecisionBody,
    ExplanationBody,
    GrievanceWrite,
    HearingBody,
    IncidentWrite,
    NteBody,
    OffenseWrite,
    PolicyWrite,
)
from app.modules.employees.models import Employee
from app.shared.documents import generate_document
from app.shared.sequences import next_number
from app.shared.settings_store import OffboardingSettings, get_settings_model


def _reveal(stored: str) -> str:
    if not stored or not stored.startswith("v1:"):
        return ""
    try:
        return decrypt(stored)
    except Exception:
        return ""


_EVENT_KEYS = {
    "step",
    "at",
    "actor_id",
    "sanction_type",
    "suspension_days",
    "response_deadline",
    "document_id",
    "schedule",
}


def present_case(actor: Actor, case: DisciplinaryCase) -> dict:
    data = api(case)
    if policies.can_view_details(actor):
        data["details"] = _reveal(data.get("details") or "")
    else:
        data.pop("details", None)
        data["events"] = [
            {key: value for key, value in event.items() if key in _EVENT_KEYS}
            for event in data.get("events") or []
            if isinstance(event, dict)
        ]
    return data


async def list_offenses(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_case_read(actor)
    return await TenantRepo(Offense, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("offense", "category"),
        sort_fields={"created_at", "offense"},
        q=q,
        sort="offense",
    )


async def get_offense(actor: Actor, doc_id: str) -> dict:
    policies.require_case_read(actor)
    return api(await TenantRepo(Offense, actor).get(doc_id))


async def create_offense(actor: Actor, body: OffenseWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Offense, actor).create(body))


async def update_offense(actor: Actor, doc_id: str, body: OffenseWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Offense, actor).update(doc_id, body))


async def delete_offense(actor: Actor, doc_id: str) -> None:
    policies.require_manage(actor)
    await TenantRepo(Offense, actor).soft_delete(doc_id)


async def list_incidents(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_case_read(actor)
    return await TenantRepo(IncidentReport, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("description", "employee_id"),
        sort_fields={"created_at", "date"},
        q=q,
        sort="-created_at",
    )


async def get_incident(actor: Actor, doc_id: str) -> dict:
    policies.require_case_read(actor)
    return api(await TenantRepo(IncidentReport, actor).get(doc_id))


async def create_incident(actor: Actor, body: IncidentWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(IncidentReport, actor).create(body))


async def update_incident(actor: Actor, doc_id: str, body: IncidentWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(IncidentReport, actor).update(doc_id, body))


async def _case(actor: Actor, doc_id: str) -> DisciplinaryCase:
    company = policies.company_id(actor)
    case = await DisciplinaryCase.get(doc_id)
    if case is None or case.company_id != company:
        raise AppError("not_found", "Record not found", 404)
    return case


async def list_cases(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    company = policies.require_case_read(actor)
    query: dict = {"company_id": company}
    if q:
        query["case_no"] = {"$regex": q, "$options": "i"}
    total = await DisciplinaryCase.find(query).count()
    rows = (
        await DisciplinaryCase.find(query)
        .sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )
    return {
        "items": [present_case(actor, row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_case(actor: Actor, doc_id: str) -> dict:
    policies.require_case_read(actor)
    return present_case(actor, await _case(actor, doc_id))


async def create_case(actor: Actor, body: CaseWrite) -> dict:
    company = policies.require_manage(actor)
    if body.status not in (None, "", "open"):
        raise AppError("conflict", "New cases start at open", 409)
    case_no = body.case_no or await next_number(company, "case", "CASE-")
    case = DisciplinaryCase(
        company_id=company,
        employee_id=body.employee_id,
        incident_report_id=body.incident_report_id,
        offense_id=body.offense_id,
        case_no=case_no,
        status="open",
        sanction_type=body.sanction_type,
        suspension_days=body.suspension_days if body.sanction_type == "suspension" else 0,
        details=encrypt(body.details) if body.details else "",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await case.insert()
    return present_case(actor, case)


async def update_case(actor: Actor, doc_id: str, body: CaseWrite) -> dict:
    policies.require_manage(actor)
    case = await _case(actor, doc_id)
    if body.status and body.status != case.status:
        policies.assert_manual_close(case.status, body.status)
        case.status = body.status
    case.employee_id = body.employee_id
    case.incident_report_id = body.incident_report_id
    case.offense_id = body.offense_id
    if body.case_no:
        case.case_no = body.case_no
    case.sanction_type = body.sanction_type
    case.suspension_days = body.suspension_days if body.sanction_type == "suspension" else 0
    if "details" in body.model_fields_set and body.details is not None:
        case.details = encrypt(body.details) if body.details else ""
    case.updated_at = utcnow()
    case.updated_by = actor.user_id
    await case.save()
    return present_case(actor, case)


def _stamp(actor: Actor, step: str, extra: dict) -> dict:
    return {"step": step, "at": utcnow().isoformat(), "actor_id": actor.user_id, **extra}


async def _employee(company: str, employee_id: str) -> Employee:
    employee = await Employee.get(employee_id)
    if employee is None or employee.company_id != company or employee.deleted_at is not None:
        raise AppError("not_found", "Employee not found", 404)
    return employee


async def issue_nte(actor: Actor, doc_id: str, body: NteBody) -> dict:
    company = policies.require_manage(actor)
    case = await _case(actor, doc_id)
    nxt = policies.transition("issue-nte", case.status)
    employee = await _employee(company, case.employee_id)
    raw = await get_settings_model(company, "offboarding")
    settings = raw if isinstance(raw, OffboardingSettings) else OffboardingSettings()
    deadline = utcnow() + timedelta(days=settings.nte_response_days)
    generated = await generate_document(
        actor,
        doc_type="NTE",
        employee_id=str(employee.id),
        merge={
            "employee": {"full_name": employee.name.full_name, "employee_no": employee.employee_no},
            "case_no": case.case_no,
            "response_deadline": deadline.date().isoformat(),
            "details": body.details,
        },
    )
    if body.details:
        case.details = encrypt(body.details)
    case.status = nxt
    case.events = [
        *case.events,
        _stamp(
            actor,
            "nte_issued",
            {
                "response_deadline": deadline.isoformat(),
                "document_id": str(generated.id),
            },
        ),
    ]
    case.updated_at = utcnow()
    case.updated_by = actor.user_id
    await case.save()
    return present_case(actor, case)


async def record_explanation(actor: Actor, doc_id: str, body: ExplanationBody) -> dict:
    policies.require_manage(actor)
    case = await _case(actor, doc_id)
    case.status = policies.transition("record-explanation", case.status)
    case.events = [
        *case.events,
        _stamp(actor, "explanation_received", {"explanation": body.explanation}),
    ]
    case.updated_at = utcnow()
    case.updated_by = actor.user_id
    await case.save()
    return present_case(actor, case)


async def schedule_hearing(actor: Actor, doc_id: str, body: HearingBody) -> dict:
    policies.require_manage(actor)
    case = await _case(actor, doc_id)
    case.status = policies.transition("schedule-hearing", case.status)
    case.events = [
        *case.events,
        _stamp(actor, "hearing", {"schedule": body.schedule, "notes": body.notes}),
    ]
    case.updated_at = utcnow()
    case.updated_by = actor.user_id
    await case.save()
    return present_case(actor, case)


async def decide_case(actor: Actor, doc_id: str, body: DecisionBody) -> dict:
    policies.require_manage(actor)
    case = await _case(actor, doc_id)
    case.status = policies.transition("decide", case.status)
    case.sanction_type = body.sanction_type
    case.suspension_days = body.suspension_days if body.sanction_type == "suspension" else 0
    case.events = [
        *case.events,
        _stamp(
            actor,
            "decided",
            {
                "sanction_type": case.sanction_type,
                "suspension_days": case.suspension_days,
                "notes": body.notes,
            },
        ),
    ]
    case.updated_at = utcnow()
    case.updated_by = actor.user_id
    await case.save()
    return present_case(actor, case)


async def list_grievances(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_case_read(actor)
    return await TenantRepo(Grievance, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("category", "description"),
        sort_fields={"created_at", "status"},
        q=q,
        sort="-created_at",
    )


async def get_grievance(actor: Actor, doc_id: str) -> dict:
    policies.require_case_read(actor)
    return api(await TenantRepo(Grievance, actor).get(doc_id))


async def create_grievance(actor: Actor, body: GrievanceWrite) -> dict:
    if not policies.can_file_grievance(actor):
        raise AppError("forbidden", "You do not have access to this action", 403)
    policies.company_id(actor)
    payload = body
    if body.anonymous:
        payload = body.model_copy(update={"submitted_by": None})
    elif not body.submitted_by:
        if not actor.employee_id:
            raise AppError("bad_request", "submitted_by is required", 400)
        payload = body.model_copy(update={"submitted_by": actor.employee_id})
    return api(await TenantRepo(Grievance, actor).create(payload))


async def update_grievance(actor: Actor, doc_id: str, body: GrievanceWrite) -> dict:
    policies.require_manage(actor)
    payload = body.model_copy(update={"submitted_by": None}) if body.anonymous else body
    return api(await TenantRepo(Grievance, actor).update(doc_id, payload))


async def list_policies(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    if not (
        actor.has("relations.view") or actor.has("relations.manage") or actor.has("self.service")
    ):
        raise AppError("forbidden", "You do not have access to this action", 403)
    policies.company_id(actor)
    return await TenantRepo(Policy, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("title",),
        sort_fields={"created_at", "title"},
        q=q,
        sort="title",
    )


async def get_policy(actor: Actor, doc_id: str) -> dict:
    if not (
        actor.has("relations.view") or actor.has("relations.manage") or actor.has("self.service")
    ):
        raise AppError("forbidden", "You do not have access to this action", 403)
    policies.company_id(actor)
    return api(await TenantRepo(Policy, actor).get(doc_id))


async def create_policy(actor: Actor, body: PolicyWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Policy, actor).create(body))


async def update_policy(actor: Actor, doc_id: str, body: PolicyWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Policy, actor).update(doc_id, body))


async def delete_policy(actor: Actor, doc_id: str) -> None:
    policies.require_manage(actor)
    await TenantRepo(Policy, actor).soft_delete(doc_id)


async def acknowledge_policy(actor: Actor, policy_id: str, ip: str) -> dict:
    company = policies.company_id(actor)
    if not policies.can_acknowledge(actor):
        raise AppError("forbidden", "You do not have access to this action", 403)
    policy = await TenantRepo(Policy, actor).get(policy_id)
    employee_id = actor.employee_id or ""
    existing = await PolicyAcknowledgment.find_one(
        {
            "company_id": company,
            "policy_id": str(policy.id),
            "employee_id": employee_id,
            "version": policy.version,
        }
    )
    if existing is not None:
        raise AppError("conflict", "You already acknowledged this policy version", 409)
    row = PolicyAcknowledgment(
        company_id=company,
        policy_id=str(policy.id),
        version=policy.version,
        employee_id=employee_id,
        acknowledged_at=utcnow(),
        ip=ip or None,
    )
    await row.insert()
    return api(row)
