from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.actor import Actor
from app.core.deps import require
from app.modules.privacy.schemas import ConsentWrite, DataSubjectWrite, RetentionWrite
from app.modules.privacy.service import (
    create_request,
    create_retention,
    export_request,
    get_request,
    get_retention,
    give_consent,
    list_consents,
    list_requests,
    list_retention,
    update_request,
    update_retention,
)

router = APIRouter(tags=["privacy"])


@router.get("/privacy/consents")
async def consents_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(require("privacy.view")),
) -> dict:
    return await list_consents(actor, page, page_size)


@router.post("/privacy/consents", status_code=201)
async def consents_create(
    body: ConsentWrite,
    actor: Actor = Depends(require("privacy.manage")),
) -> dict:
    return await give_consent(actor, body)


@router.get("/data-subject-requests")
async def requests_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("privacy.view")),
) -> dict:
    return await list_requests(actor, page, page_size, q)


@router.post("/data-subject-requests", status_code=201)
async def requests_create(
    body: DataSubjectWrite,
    actor: Actor = Depends(require("privacy.manage")),
) -> dict:
    return await create_request(actor, body)


@router.get("/data-subject-requests/{id}")
async def requests_get(id: str, actor: Actor = Depends(require("privacy.view"))) -> dict:
    return await get_request(actor, id)


@router.put("/data-subject-requests/{id}")
async def requests_update(
    id: str,
    body: DataSubjectWrite,
    actor: Actor = Depends(require("privacy.manage")),
) -> dict:
    return await update_request(actor, id, body)


@router.post("/data-subject-requests/{id}/export")
async def requests_export(id: str, actor: Actor = Depends(require("privacy.manage"))) -> dict:
    return await export_request(actor, id)


@router.get("/retention-policies")
async def retention_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("privacy.view")),
) -> dict:
    return await list_retention(actor, page, page_size, q)


@router.post("/retention-policies", status_code=201)
async def retention_create(
    body: RetentionWrite,
    actor: Actor = Depends(require("privacy.manage")),
) -> dict:
    return await create_retention(actor, body)


@router.get("/retention-policies/{id}")
async def retention_get(id: str, actor: Actor = Depends(require("privacy.view"))) -> dict:
    return await get_retention(actor, id)


@router.put("/retention-policies/{id}")
async def retention_update(
    id: str,
    body: RetentionWrite,
    actor: Actor = Depends(require("privacy.manage")),
) -> dict:
    return await update_retention(actor, id, body)
