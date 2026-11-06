from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.actor import Actor
from app.core.deps import require
from app.modules.training.schemas import AttendeeWrite, BondWrite, TrainingWrite
from app.modules.training.service import (
    create_attendee,
    create_bond,
    create_training,
    get_attendee,
    get_bond,
    get_training,
    list_attendees,
    list_bonds,
    list_trainings,
    update_attendee,
    update_bond,
    update_training,
)

router = APIRouter(tags=["training"])


@router.get("/trainings")
async def trainings_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("training.view")),
) -> dict:
    return await list_trainings(actor, page, page_size, q)


@router.post("/trainings", status_code=201)
async def trainings_create(
    body: TrainingWrite,
    actor: Actor = Depends(require("training.manage")),
) -> dict:
    return await create_training(actor, body)


@router.get("/trainings/{id}")
async def trainings_get(id: str, actor: Actor = Depends(require("training.view"))) -> dict:
    return await get_training(actor, id)


@router.put("/trainings/{id}")
async def trainings_update(
    id: str,
    body: TrainingWrite,
    actor: Actor = Depends(require("training.manage")),
) -> dict:
    return await update_training(actor, id, body)


@router.get("/training-attendees")
async def attendees_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("training.view")),
) -> dict:
    return await list_attendees(actor, page, page_size, q)


@router.post("/training-attendees", status_code=201)
async def attendees_create(
    body: AttendeeWrite,
    actor: Actor = Depends(require("training.manage")),
) -> dict:
    return await create_attendee(actor, body)


@router.get("/training-attendees/{id}")
async def attendees_get(id: str, actor: Actor = Depends(require("training.view"))) -> dict:
    return await get_attendee(actor, id)


@router.put("/training-attendees/{id}")
async def attendees_update(
    id: str,
    body: AttendeeWrite,
    actor: Actor = Depends(require("training.manage")),
) -> dict:
    return await update_attendee(actor, id, body)


@router.get("/training-bonds")
async def bonds_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("training.view")),
) -> dict:
    return await list_bonds(actor, page, page_size, q)


@router.post("/training-bonds", status_code=201)
async def bonds_create(body: BondWrite, actor: Actor = Depends(require("training.manage"))) -> dict:
    return await create_bond(actor, body)


@router.get("/training-bonds/{id}")
async def bonds_get(id: str, actor: Actor = Depends(require("training.view"))) -> dict:
    return await get_bond(actor, id)


@router.put("/training-bonds/{id}")
async def bonds_update(
    id: str,
    body: BondWrite,
    actor: Actor = Depends(require("training.manage")),
) -> dict:
    return await update_bond(actor, id, body)
