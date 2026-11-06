"""Requisitions, openings, applicants, offers, and hire conversion."""

from __future__ import annotations

import time
from datetime import timedelta
from decimal import Decimal

from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.errors import AppError
from app.core.money import money
from app.core.repository import TenantRepo, api
from app.modules.employees.models import CompensationSnapshot, Employee, PersonName
from app.modules.onboarding.models import ChecklistTask, OnboardingChecklist, OnboardingTemplate
from app.modules.organization.models import Company
from app.modules.recruitment import policies
from app.modules.recruitment.models import Applicant, JobOffer, JobOpening, ManpowerRequisition
from app.modules.recruitment.schemas import (
    ApplicantWrite,
    OfferWrite,
    OpeningWrite,
    PublicApplication,
    RequisitionWrite,
    ScorecardWrite,
    StageWrite,
)
from app.shared.approvals import handles, start_request
from app.shared.models import ApprovalRequest
from app.shared.sequences import next_number

_ip_counts: dict[str, tuple[int, int]] = {}


def enforce_public_rate(ip: str) -> None:
    bucket = int(time.time() // 3600)
    hour, count = _ip_counts.get(ip, (bucket, 0))
    if hour != bucket:
        hour, count = bucket, 0
    if count >= 30:
        raise AppError("rate_limited", "Too many requests from this network. Try again later.", 429)
    _ip_counts[ip] = (hour, count + 1)


async def _page(
    actor: Actor,
    model,
    search: tuple[str, ...],
    page: int,
    page_size: int,
    q: str | None,
    extra=None,
):
    policies.require_view(actor)
    return await TenantRepo(model, actor).list(
        page=page,
        page_size=page_size,
        search_fields=search,
        sort_fields={"created_at", "title", "name", "status"},
        q=q,
        sort="-created_at",
        extra=extra,
    )


async def list_requisitions(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, ManpowerRequisition, ("reason", "status"), page, page_size, q)


async def get_requisition(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(ManpowerRequisition, actor).get(doc_id))


async def create_requisition(actor: Actor, body: RequisitionWrite) -> dict:
    policies.require_manage(actor)
    policies.valid_headcount(body.headcount)
    async with transaction() as session:
        doc = await TenantRepo(ManpowerRequisition, actor).create(body, session=session)
        request = await start_request(
            actor=actor,
            module="requisition",
            subject_type="requisition",
            subject_id=str(doc.id),
            context={
                "department_id": doc.department_id,
                "headcount": doc.headcount,
                "budget": format(money(doc.budget), "f"),
            },
            session=session,
        )
        doc.approval_request_id = str(request.id)
        doc.status = request.status
        doc.updated_at = utcnow()
        await doc.save(session=session)
    return api(doc)


async def update_requisition(actor: Actor, doc_id: str, body: RequisitionWrite) -> dict:
    policies.require_manage(actor)
    policies.valid_headcount(body.headcount)
    return api(await TenantRepo(ManpowerRequisition, actor).update(doc_id, body))


@handles("requisition")
async def on_requisition_decided(
    request: ApprovalRequest,
    session: AsyncClientSession | None,
) -> None:
    doc = await ManpowerRequisition.get(request.subject_id, session=session)
    if doc is None or doc.company_id != request.company_id:
        return
    doc.status = request.status
    doc.updated_at = utcnow()
    await doc.save(session=session)


async def list_openings(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, JobOpening, ("title", "location"), page, page_size, q)


async def get_opening(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(JobOpening, actor).get(doc_id))


async def create_opening(actor: Actor, body: OpeningWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(JobOpening, actor).create(body))


async def update_opening(actor: Actor, doc_id: str, body: OpeningWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(JobOpening, actor).update(doc_id, body))


async def delete_opening(actor: Actor, doc_id: str) -> None:
    policies.require_manage(actor)
    await TenantRepo(JobOpening, actor).soft_delete(doc_id)


async def list_applicants(
    actor: Actor,
    page: int,
    page_size: int,
    q: str | None,
    stage: str | None,
) -> dict:
    token = policies.safe_token(stage)
    extra = {"stage": token} if token else None
    return await _page(actor, Applicant, ("name", "email"), page, page_size, q, extra)


async def get_applicant(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(Applicant, actor).get(doc_id))


async def create_applicant(actor: Actor, body: ApplicantWrite) -> dict:
    policies.require_manage(actor)
    policies.split_name(body.name)
    return api(await TenantRepo(Applicant, actor).create(body))


async def update_applicant(actor: Actor, doc_id: str, body: ApplicantWrite) -> dict:
    policies.require_manage(actor)
    policies.split_name(body.name)
    return api(await TenantRepo(Applicant, actor).update(doc_id, body))


async def move_stage(actor: Actor, doc_id: str, body: StageWrite) -> dict:
    policies.require_manage(actor)
    applicant = await TenantRepo(Applicant, actor).get(doc_id)
    activity = {
        "type": "stage_change",
        "from_stage": applicant.stage,
        "to_stage": body.stage,
        "note": body.note,
        "actor_id": actor.user_id,
        "at": utcnow().isoformat(),
    }
    applicant.activities = [*applicant.activities, activity]
    applicant.stage = body.stage
    applicant.updated_at = utcnow()
    applicant.updated_by = actor.user_id
    await applicant.save()
    return api(applicant)


async def add_scorecard(actor: Actor, doc_id: str, body: ScorecardWrite) -> dict:
    policies.require_manage(actor)
    applicant = await TenantRepo(Applicant, actor).get(doc_id)
    card = {
        "interviewer_id": body.interviewer_id or actor.user_id,
        "criteria": body.criteria,
        "recommendation": body.recommendation,
        "at": utcnow().isoformat(),
    }
    applicant.scorecards = [*applicant.scorecards, card]
    applicant.updated_at = utcnow()
    applicant.updated_by = actor.user_id
    await applicant.save()
    return api(applicant)


async def _first_template(company: str) -> OnboardingTemplate | None:
    rows = (
        await OnboardingTemplate.find({"company_id": company, "deleted_at": None})
        .sort("+created_at")
        .to_list()
    )
    return rows[0] if rows else None


async def hire_applicant(actor: Actor, doc_id: str) -> dict:
    company = policies.require_manage(actor)
    applicant = await TenantRepo(Applicant, actor).get(doc_id)
    if applicant.stage == "hired":
        raise AppError("conflict", "Applicant is already hired", 409)
    first, last = policies.split_name(applicant.name)
    opening = await JobOpening.get(applicant.job_opening_id)
    employment_type = "regular"
    department_id = None
    position_id = None
    if opening is not None and opening.company_id == company and opening.deleted_at is None:
        employment_type = opening.employment_type or "regular"
        if opening.requisition_id:
            requisition = await ManpowerRequisition.get(opening.requisition_id)
            if requisition is not None and requisition.company_id == company:
                department_id = requisition.department_id
                position_id = requisition.position_id
    offer = await JobOffer.find_one({"company_id": company, "applicant_id": str(applicant.id)})
    compensation = None
    date_hired = utcnow().date()
    if offer is not None and offer.company_id == company:
        salary = money(offer.salary)
        daily = money(salary / Decimal(22))
        compensation = CompensationSnapshot(
            basic_salary=salary,
            pay_basis="monthly",
            daily_rate=daily,
            hourly_rate=money(daily / Decimal(8)),
        )
        date_hired = offer.start_date
    template = await _first_template(company)
    number = await next_number(company, "employee", "EMP-")
    async with transaction() as session:
        employee = Employee(
            company_id=company,
            user_id=None,
            employee_no=number,
            name=PersonName(first=first, last=last),
            contact={"personal_email": applicant.email, "mobile": applicant.mobile},
            department_id=department_id,
            position_id=position_id,
            employment_type=employment_type,
            employment_status="active",
            date_hired=date_hired,
            current_compensation=compensation,
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await employee.insert(session=session)
        if template is not None:
            today = utcnow().date()
            tasks = [
                ChecklistTask(
                    task=item.task,
                    due_date=today + timedelta(days=item.due_offset_days),
                    status="open",
                )
                for item in template.tasks
            ]
            checklist = OnboardingChecklist(
                company_id=company,
                employee_id=str(employee.id),
                template_id=str(template.id),
                tasks=tasks,
                created_by=actor.user_id,
                updated_by=actor.user_id,
            )
            await checklist.insert(session=session)
        applicant.activities = [
            *applicant.activities,
            {
                "type": "hired",
                "from_stage": applicant.stage,
                "to_stage": "hired",
                "employee_id": str(employee.id),
                "actor_id": actor.user_id,
                "at": utcnow().isoformat(),
            },
        ]
        applicant.stage = "hired"
        applicant.updated_at = utcnow()
        applicant.updated_by = actor.user_id
        await applicant.save(session=session)
    return {"employee": api(employee), "applicant": api(applicant)}


async def list_offers(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, JobOffer, ("status", "applicant_id"), page, page_size, q)


async def get_offer(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(JobOffer, actor).get(doc_id))


async def create_offer(actor: Actor, body: OfferWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(JobOffer, actor).create(body))


async def update_offer(actor: Actor, doc_id: str, body: OfferWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(JobOffer, actor).update(doc_id, body))


async def _public_company(slug: str) -> Company:
    company = await Company.find_one(Company.slug == slug)
    if company is None or company.deleted_at is not None or not company.is_active:
        raise AppError("not_found", "Company not found", 404)
    return company


async def public_jobs(slug: str, ip: str) -> dict:
    enforce_public_rate(ip)
    company = await _public_company(slug)
    openings = await JobOpening.find(
        {
            "company_id": str(company.id),
            "is_public": True,
            "status": "open",
            "deleted_at": None,
        }
    ).to_list()
    items = [
        policies.redact_public_opening(api(opening), salary_visible=opening.salary_visible)
        for opening in openings
    ]
    return {"items": items, "total": len(items)}


async def public_apply(slug: str, opening_id: str, body: PublicApplication, ip: str) -> dict:
    enforce_public_rate(ip)
    company = await _public_company(slug)
    policies.split_name(body.name)
    opening = await JobOpening.get(opening_id)
    company_key = str(company.id)
    if (
        opening is None
        or opening.company_id != company_key
        or opening.deleted_at is not None
        or not opening.is_public
        or opening.status != "open"
    ):
        raise AppError("not_found", "Job opening not found", 404)
    applicant = Applicant(
        company_id=company_key,
        job_opening_id=str(opening.id),
        name=body.name.strip(),
        email=body.email.strip(),
        mobile=body.mobile,
        resume_key=body.resume_key,
        source=body.source or "public",
        stage="applied",
        consent_given_at=utcnow(),
    )
    await applicant.insert()
    return api(applicant)
