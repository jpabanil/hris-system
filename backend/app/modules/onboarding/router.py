from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import require
from app.modules.onboarding.schemas import TaskPatch, TemplateWrite
from app.modules.onboarding.service import (
    create_template,
    delete_template,
    get_checklist,
    get_template,
    list_templates,
    patch_task,
    update_template,
)

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding-templates")
async def templates_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("onboarding.view")),
) -> dict:
    return await list_templates(actor, page, page_size, q)


@router.post("/onboarding-templates", status_code=201)
async def templates_create(
    body: TemplateWrite,
    actor: Actor = Depends(require("onboarding.manage")),
) -> dict:
    return await create_template(actor, body)


@router.get("/onboarding-templates/{id}")
async def templates_get(id: str, actor: Actor = Depends(require("onboarding.view"))) -> dict:
    return await get_template(actor, id)


@router.put("/onboarding-templates/{id}")
async def templates_update(
    id: str,
    body: TemplateWrite,
    actor: Actor = Depends(require("onboarding.manage")),
) -> dict:
    return await update_template(actor, id, body)


@router.delete("/onboarding-templates/{id}", status_code=204)
async def templates_delete(
    id: str,
    actor: Actor = Depends(require("onboarding.manage")),
) -> Response:
    await delete_template(actor, id)
    return Response(status_code=204)


@router.get("/onboarding/{employee_id}")
async def checklist_get(
    employee_id: str,
    actor: Actor = Depends(require("onboarding.view")),
) -> dict:
    return await get_checklist(actor, employee_id)


@router.patch("/onboarding/{employee_id}/tasks/{task_id}")
async def checklist_task(
    employee_id: str,
    task_id: str,
    body: TaskPatch,
    actor: Actor = Depends(require("onboarding.manage")),
) -> dict:
    return await patch_task(actor, employee_id, task_id, body)
