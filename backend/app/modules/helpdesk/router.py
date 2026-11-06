from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.actor import Actor
from app.core.deps import get_actor
from app.modules.helpdesk.schemas import CommentWrite, TicketUpdate, TicketWrite
from app.modules.helpdesk.service import (
    add_comment,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket,
)

router = APIRouter(tags=["helpdesk"])


@router.get("/hr-tickets")
async def tickets_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_tickets(actor, page, page_size, q)


@router.post("/hr-tickets", status_code=201)
async def tickets_create(body: TicketWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_ticket(actor, body)


@router.get("/hr-tickets/{id}")
async def tickets_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_ticket(actor, id)


@router.put("/hr-tickets/{id}")
async def tickets_update(id: str, body: TicketUpdate, actor: Actor = Depends(get_actor)) -> dict:
    return await update_ticket(actor, id, body)


@router.post("/hr-tickets/{id}/comments", status_code=201)
async def tickets_comment(id: str, body: CommentWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await add_comment(actor, id, body)
