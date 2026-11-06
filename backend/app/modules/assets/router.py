"""Asset routes. Permission checks stay here; rules stay in the service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.assets.schemas import (
    AssetWrite,
    AssignmentCreate,
    AssignmentReturn,
    AssignmentUpdate,
)
from app.modules.assets.service import (
    create_asset,
    create_assignment,
    delete_asset,
    delete_assignment,
    get_asset,
    get_assignment,
    list_assets,
    list_assignments,
    my_assets,
    return_assignment,
    update_asset,
    update_assignment,
)

router = APIRouter(tags=["assets"])


@router.get("/me/assets")
async def me_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(require("self.service")),
) -> dict:
    return await my_assets(actor, page, page_size)


@router.get("/assets")
async def assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    sort: str | None = None,
    status: str | None = None,
    actor: Actor = Depends(require("assets.view")),
) -> dict:
    return await list_assets(actor, page, page_size, q, sort, status)


@router.post("/assets", status_code=201)
async def assets_create(body: AssetWrite, actor: Actor = Depends(require("assets.manage"))) -> dict:
    return await create_asset(actor, body)


@router.get("/assets/{asset_id}")
async def assets_get(asset_id: str, actor: Actor = Depends(require("assets.view"))) -> dict:
    return await get_asset(actor, asset_id)


@router.put("/assets/{asset_id}")
async def assets_update(
    asset_id: str,
    body: AssetWrite,
    actor: Actor = Depends(require("assets.manage")),
) -> dict:
    return await update_asset(actor, asset_id, body)


@router.delete("/assets/{asset_id}", status_code=204)
async def assets_delete(
    asset_id: str,
    actor: Actor = Depends(require("assets.manage")),
) -> Response:
    await delete_asset(actor, asset_id)
    return Response(status_code=204)


@router.get("/asset-assignments")
async def assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    employee_id: str | None = None,
    asset_id: str | None = None,
    open_only: bool = False,
    sort: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_assignments(actor, page, page_size, employee_id, asset_id, open_only, sort)


@router.post("/asset-assignments", status_code=201)
async def assignments_create(
    body: AssignmentCreate,
    actor: Actor = Depends(require("assets.manage")),
) -> dict:
    return await create_assignment(actor, body)


@router.get("/asset-assignments/{assignment_id}")
async def assignments_get(assignment_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_assignment(actor, assignment_id)


@router.put("/asset-assignments/{assignment_id}")
async def assignments_update(
    assignment_id: str,
    body: AssignmentUpdate,
    actor: Actor = Depends(require("assets.manage")),
) -> dict:
    return await update_assignment(actor, assignment_id, body)


@router.post("/asset-assignments/{assignment_id}/return")
async def assignments_return(
    assignment_id: str,
    body: AssignmentReturn,
    actor: Actor = Depends(require("assets.manage")),
) -> dict:
    return await return_assignment(actor, assignment_id, body)


@router.delete("/asset-assignments/{assignment_id}", status_code=204)
async def assignments_delete(
    assignment_id: str,
    actor: Actor = Depends(require("assets.manage")),
) -> Response:
    await delete_assignment(actor, assignment_id)
    return Response(status_code=204)
