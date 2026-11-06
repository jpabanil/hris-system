"""Approvals, settings, files, notifications, templates, and the audit log."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.deps import get_actor, require
from app.core.errors import AppError
from app.core.repository import TenantRepo, api
from app.shared.approvals import act, inbox
from app.shared.documents import generate_document
from app.shared.files import read_signed, save_upload, signed_url
from app.shared.models import (
    ApprovalDelegation,
    ApprovalFlow,
    AuditLog,
    DocumentTemplate,
    GeneratedDocument,
    Notification,
)
from app.shared.notify import unread_count
from app.shared.settings_store import SCHEMAS, get_settings_model, save_settings

router = APIRouter(tags=["platform"])


class ActBody(BaseModel):
    remarks: str = ""


class BulkBody(BaseModel):
    ids: list[str]
    action: str
    remarks: str = ""


class DelegationWrite(BaseModel):
    approver_id: str
    delegate_id: str
    starts_on: str
    ends_on: str


class FlowWrite(BaseModel):
    module: str
    name: str
    conditions: list[dict] = []
    steps: list[dict] = []
    is_active: bool = True
    revision: int | None = None


class GenerateBody(BaseModel):
    doc_type: str
    employee_id: str | None = None
    merge: dict = {}


class TemplateWrite(BaseModel):
    type: str
    name: str
    body: str
    is_active: bool = True
    revision: int | None = None


@router.get("/approvals/inbox")
async def approvals_inbox(actor: Actor = Depends(require("approvals.act"))) -> dict:
    items = await inbox(actor)
    return {"items": items, "total": len(items)}


@router.post("/approvals/{request_id}/approve")
async def approve(
    request_id: str, body: ActBody, actor: Actor = Depends(require("approvals.act"))
) -> dict:
    return api(
        await act(
            actor=actor, request_id=request_id, action="approve", remarks=body.remarks
        )
    )


@router.post("/approvals/{request_id}/reject")
async def reject(
    request_id: str, body: ActBody, actor: Actor = Depends(require("approvals.act"))
) -> dict:
    return api(await act(actor=actor, request_id=request_id, action="reject", remarks=body.remarks))


@router.post("/approvals/{request_id}/return")
async def return_request(
    request_id: str, body: ActBody, actor: Actor = Depends(require("approvals.act"))
) -> dict:
    return api(await act(actor=actor, request_id=request_id, action="return", remarks=body.remarks))


@router.post("/approvals/bulk")
async def bulk(body: BulkBody, actor: Actor = Depends(require("approvals.act"))) -> dict:
    results = []
    for request_id in body.ids:
        results.append(
            api(
                await act(
                    actor=actor,
                    request_id=request_id,
                    action=body.action,
                    remarks=body.remarks,
                )
            )
        )
    return {"items": results}


@router.get("/approval-flows")
async def flows(actor: Actor = Depends(require("settings.view"))) -> dict:
    return await TenantRepo(ApprovalFlow, actor).list(
        page=1,
        page_size=100,
        search_fields=("name", "module"),
        sort_fields={"name", "module", "created_at"},
        q=None,
        sort="module",
    )


@router.post("/approval-flows", status_code=201)
async def flows_create(body: FlowWrite, actor: Actor = Depends(require("settings.manage"))) -> dict:
    return api(await TenantRepo(ApprovalFlow, actor).create(body))


@router.post("/approval-delegations", status_code=201)
async def delegations_create(body: DelegationWrite, actor: Actor = Depends(get_actor)) -> dict:
    from datetime import datetime

    item = ApprovalDelegation(
        company_id=actor.company_id or "",
        approver_id=body.approver_id,
        delegate_id=body.delegate_id,
        starts_on=datetime.fromisoformat(body.starts_on),
        ends_on=datetime.fromisoformat(body.ends_on),
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await item.insert()
    return api(item)


@router.get("/settings/{module}")
async def read_settings(module: str, actor: Actor = Depends(require("settings.view"))) -> dict:
    if module not in SCHEMAS or not actor.company_id:
        raise AppError("not_found", "Unknown settings module", 404)
    parsed = await get_settings_model(actor.company_id, module)
    return {"module": module, "values": parsed.model_dump(mode="json")}


@router.put("/settings/{module}")
async def write_settings(
    module: str, body: dict, actor: Actor = Depends(require("settings.manage"))
) -> dict:
    if module not in SCHEMAS:
        raise AppError("not_found", "Unknown settings module", 404)
    parsed = await save_settings(actor, module, body)
    return {"module": module, "values": parsed.model_dump(mode="json")}


@router.post("/files", status_code=201)
async def upload(
    upload: UploadFile = File(...),
    confidential: bool = Form(False),
    actor: Actor = Depends(get_actor),
) -> dict:
    data = await upload.read()
    stored = await save_upload(
        actor,
        filename=upload.filename or "upload",
        content_type=upload.content_type or "application/octet-stream",
        data=data,
        confidential=confidential,
    )
    return {"key": stored.key, "filename": stored.filename, "size": stored.size}


@router.get("/files/url")
async def file_url(key: str, actor: Actor = Depends(get_actor)) -> dict:
    if actor.company_id and not key.startswith(f"{actor.company_id}/"):
        raise AppError("forbidden", "You cannot open this file", 403)
    return {"url": signed_url(key)}


@router.get("/files/content")
async def file_content(key: str, exp: int, sig: str) -> Response:
    data, _name, _content_type = read_signed(key, exp, sig)
    return Response(content=data, media_type="application/octet-stream")


@router.get("/notifications")
async def notifications(actor: Actor = Depends(get_actor)) -> dict:
    if not actor.company_id:
        return {"items": [], "unread": 0}
    items = (
        await Notification.find({"company_id": actor.company_id, "user_id": actor.user_id})
        .sort("-created_at")
        .limit(50)
        .to_list()
    )
    return {
        "items": [api(item) for item in items],
        "unread": await unread_count(actor.company_id, actor.user_id),
    }


@router.patch("/notifications/read")
async def notifications_read(actor: Actor = Depends(get_actor)) -> dict:
    await Notification.find(
        {"company_id": actor.company_id, "user_id": actor.user_id, "read_at": None}
    ).update({"$set": {"read_at": utcnow()}})
    return {"ok": True}


@router.get("/notifications/stream")
async def notifications_stream(
    request: Request, actor: Actor = Depends(get_actor)
) -> StreamingResponse:
    async def events():
        while True:
            if await request.is_disconnected():
                break
            count = 0
            if actor.company_id:
                count = await unread_count(actor.company_id, actor.user_id)
            yield f"data: {json.dumps({'unread': count})}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/document-templates")
async def templates(actor: Actor = Depends(require("documents.manage"))) -> dict:
    return await TenantRepo(DocumentTemplate, actor).list(
        page=1,
        page_size=100,
        search_fields=("name", "type"),
        sort_fields={"name", "type", "created_at"},
        q=None,
        sort="name",
    )


@router.post("/document-templates", status_code=201)
async def templates_create(
    body: TemplateWrite, actor: Actor = Depends(require("documents.manage"))
) -> dict:
    return api(await TenantRepo(DocumentTemplate, actor).create(body))


@router.post("/documents/generate", status_code=201)
async def documents_generate(
    body: GenerateBody, actor: Actor = Depends(require("documents.manage"))
) -> dict:
    generated = await generate_document(
        actor, doc_type=body.doc_type, merge=body.merge, employee_id=body.employee_id
    )
    return api(generated)


@router.get("/public/documents/verify/{code}")
async def verify_document(code: str) -> dict:
    found = await GeneratedDocument.find_one(GeneratedDocument.verification_code == code)
    if found is None:
        raise AppError("not_found", "Document not found", 404)
    return {
        "doc_type": found.doc_type,
        "sequence_no": found.sequence_no,
        "employee_id": found.employee_id,
        "issued_at": found.created_at.isoformat(),
    }


@router.get("/audit-logs")
async def audit_logs(
    page: int = Query(1, ge=1),
    actor: Actor = Depends(require("audit.view")),
) -> dict:
    query = {"company_id": actor.company_id} if not actor.is_superadmin else {}
    if actor.company_id and actor.is_superadmin:
        query = {"company_id": actor.company_id}
    total = await AuditLog.find(query).count()
    items = await AuditLog.find(query).sort("-at").skip((page - 1) * 50).limit(50).to_list()
    return {"items": [api(item) for item in items], "total": total, "page": page, "page_size": 50}


