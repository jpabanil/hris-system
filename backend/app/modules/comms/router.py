from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor
from app.modules.comms.schemas import AnnouncementWrite
from app.modules.comms.service import (
    create_announcement,
    delete_announcement,
    get_announcement,
    list_announcements,
    mark_read,
    update_announcement,
)

router = APIRouter(tags=["comms"])


@router.get("/announcements")
async def announcements_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_announcements(actor, page, page_size, q)


@router.post("/announcements", status_code=201)
async def announcements_create(body: AnnouncementWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_announcement(actor, body)


@router.get("/announcements/{id}")
async def announcements_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_announcement(actor, id)


@router.put("/announcements/{id}")
async def announcements_update(
    id: str,
    body: AnnouncementWrite,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await update_announcement(actor, id, body)


@router.delete("/announcements/{id}", status_code=204)
async def announcements_delete(id: str, actor: Actor = Depends(get_actor)) -> Response:
    await delete_announcement(actor, id)
    return Response(status_code=204)


@router.post("/announcements/{id}/read")
async def announcements_read(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await mark_read(actor, id)
