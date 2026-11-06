from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import require
from app.modules.integrations.schemas import WebhookUpdate, WebhookWrite
from app.modules.integrations.service import (
    create_webhook,
    delete_webhook,
    get_webhook,
    list_webhooks,
    test_webhook,
    update_webhook,
)

router = APIRouter(tags=["integrations"])


@router.get("/webhooks")
async def webhooks_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("settings.manage")),
) -> dict:
    return await list_webhooks(actor, page, page_size, q)


@router.post("/webhooks", status_code=201)
async def webhooks_create(
    body: WebhookWrite,
    actor: Actor = Depends(require("settings.manage")),
) -> dict:
    return await create_webhook(actor, body)


@router.get("/webhooks/{id}")
async def webhooks_get(id: str, actor: Actor = Depends(require("settings.manage"))) -> dict:
    return await get_webhook(actor, id)


@router.put("/webhooks/{id}")
async def webhooks_update(
    id: str,
    body: WebhookUpdate,
    actor: Actor = Depends(require("settings.manage")),
) -> dict:
    return await update_webhook(actor, id, body)


@router.delete("/webhooks/{id}", status_code=204)
async def webhooks_delete(id: str, actor: Actor = Depends(require("settings.manage"))) -> Response:
    await delete_webhook(actor, id)
    return Response(status_code=204)


@router.post("/webhooks/{id}/test", status_code=201)
async def webhooks_test(id: str, actor: Actor = Depends(require("settings.manage"))) -> dict:
    return await test_webhook(actor, id)
