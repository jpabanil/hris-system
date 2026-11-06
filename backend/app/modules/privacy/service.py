"""Consents, data subject requests, and retention policies."""

from __future__ import annotations

import json

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.repository import TenantRepo, api
from app.modules.employees.models import Employee, EmployeeSensitive
from app.modules.privacy import policies
from app.modules.privacy.models import DataSubjectRequest, PrivacyConsent, RetentionPolicy
from app.modules.privacy.schemas import ConsentWrite, DataSubjectWrite, RetentionWrite
from app.shared.files import save_upload


async def list_consents(actor: Actor, page: int, page_size: int) -> dict:
    company = policies.require_view(actor)
    query = {"company_id": company}
    total = await PrivacyConsent.find(query).count()
    rows = (
        await PrivacyConsent.find(query)
        .sort("-given_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )
    return {
        "items": [api(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def give_consent(actor: Actor, body: ConsentWrite) -> dict:
    company = policies.require_manage(actor)
    row = PrivacyConsent(
        company_id=company,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        purpose=body.purpose,
        version=body.version,
        given_at=utcnow(),
    )
    await row.insert()
    return api(row)


async def list_requests(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_view(actor)
    return await TenantRepo(DataSubjectRequest, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("requester", "type", "status"),
        sort_fields={"created_at", "status"},
        q=q,
        sort="-created_at",
    )


async def get_request(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(DataSubjectRequest, actor).get(doc_id))


async def create_request(actor: Actor, body: DataSubjectWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(DataSubjectRequest, actor).create(body))


async def update_request(actor: Actor, doc_id: str, body: DataSubjectWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(DataSubjectRequest, actor).update(doc_id, body))


async def _employee_for(company: str, requester: str) -> Employee:
    employee = await Employee.get(requester)
    if employee is not None and employee.company_id == company and employee.deleted_at is None:
        return employee
    found = await Employee.find_one(
        {"company_id": company, "deleted_at": None, "employee_no": requester}
    )
    if found is not None:
        return found
    found = await Employee.find_one(
        {"company_id": company, "deleted_at": None, "user_id": requester}
    )
    if found is None:
        raise AppError("not_found", "Employee not found for this request", 404)
    return found


async def export_request(actor: Actor, doc_id: str) -> dict:
    company = policies.require_manage(actor)
    doc = await TenantRepo(DataSubjectRequest, actor).get(doc_id)
    employee = await _employee_for(company, doc.requester)
    payload = employee.model_dump(mode="json")
    payload["id"] = str(employee.id)
    sensitive = await EmployeeSensitive.find_one(
        {"company_id": company, "employee_id": str(employee.id)}
    )
    if sensitive is not None:
        accounts = []
        for account in sensitive.bank_accounts:
            copied = {key: value for key, value in account.items() if key != "account_no"}
            copied["account_no"] = policies.mask_value(str(account.get("account_no") or ""))
            accounts.append(copied)
        payload["sensitive"] = {
            "tin": policies.mask_value(sensitive.tin),
            "sss_no": policies.mask_value(sensitive.sss_no),
            "philhealth_no": policies.mask_value(sensitive.philhealth_no),
            "pagibig_no": policies.mask_value(sensitive.pagibig_no),
            "bank_accounts": accounts,
        }
    raw = json.dumps(payload, default=str).encode()
    # save_upload accepts text/csv but not application/json. The bytes are JSON.
    stored = await save_upload(
        actor,
        filename=f"data-subject-{doc.id}.json",
        content_type="text/csv",
        data=raw,
        confidential=True,
    )
    doc.export_key = stored.key
    doc.status = "completed"
    doc.completed_at = utcnow()
    doc.updated_at = utcnow()
    doc.updated_by = actor.user_id
    await doc.save()
    return api(doc)


async def list_retention(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_view(actor)
    return await TenantRepo(RetentionPolicy, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("record_type", "action"),
        sort_fields={"created_at", "record_type"},
        q=q,
        sort="record_type",
    )


async def get_retention(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(RetentionPolicy, actor).get(doc_id))


async def create_retention(actor: Actor, body: RetentionWrite) -> dict:
    company = policies.require_manage(actor)
    existing = await RetentionPolicy.find_one(
        {"company_id": company, "record_type": body.record_type}
    )
    if existing is not None:
        raise AppError("conflict", "A retention policy already exists for that record type", 409)
    return api(await TenantRepo(RetentionPolicy, actor).create(body))


async def update_retention(actor: Actor, doc_id: str, body: RetentionWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(RetentionPolicy, actor).update(doc_id, body))
