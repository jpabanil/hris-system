"""Claims HTTP routes. Mounted at /api/v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.claims.schemas import (
    CashAdvanceWrite,
    ClaimTypeWrite,
    ClaimWrite,
    LiquidationWrite,
)
from app.modules.claims.service import (
    create_advance,
    create_claim,
    create_claim_type,
    delete_claim,
    delete_claim_type,
    get_advance,
    get_claim,
    liquidate_advance,
    list_advances,
    list_claim_types,
    list_claims,
    update_advance,
    update_claim,
    update_claim_type,
)

router = APIRouter(tags=["claims"])


@router.get("/claim-types")
async def claim_types(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("claims.view")),
) -> dict:
    return await list_claim_types(actor, page, page_size, q)


@router.post("/claim-types", status_code=201)
async def claim_types_create(
    body: ClaimTypeWrite, actor: Actor = Depends(require("claims.manage"))
) -> dict:
    return await create_claim_type(actor, body)


@router.put("/claim-types/{type_id}")
async def claim_types_update(
    type_id: str, body: ClaimTypeWrite, actor: Actor = Depends(require("claims.manage"))
) -> dict:
    return await update_claim_type(actor, type_id, body)


@router.delete("/claim-types/{type_id}", status_code=204)
async def claim_types_delete(
    type_id: str, actor: Actor = Depends(require("claims.manage"))
) -> Response:
    await delete_claim_type(actor, type_id)
    return Response(status_code=204)


@router.get("/claims")
async def claims(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    employee_id: str | None = None,
    status: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_claims(actor, page, page_size, q, employee_id, status)


@router.post("/claims", status_code=201)
async def claims_create(body: ClaimWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_claim(actor, body)


@router.get("/claims/{claim_id}")
async def claims_get(claim_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_claim(actor, claim_id)


@router.put("/claims/{claim_id}")
async def claims_update(claim_id: str, body: ClaimWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await update_claim(actor, claim_id, body)


@router.delete("/claims/{claim_id}", status_code=204)
async def claims_delete(claim_id: str, actor: Actor = Depends(get_actor)) -> Response:
    await delete_claim(actor, claim_id)
    return Response(status_code=204)


@router.get("/cash-advances")
async def cash_advances(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    employee_id: str | None = None,
    status: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_advances(actor, page, page_size, q, employee_id, status)


@router.post("/cash-advances", status_code=201)
async def cash_advances_create(body: CashAdvanceWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_advance(actor, body)


@router.get("/cash-advances/{advance_id}")
async def cash_advances_get(advance_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_advance(actor, advance_id)


@router.put("/cash-advances/{advance_id}")
async def cash_advances_update(
    advance_id: str, body: CashAdvanceWrite, actor: Actor = Depends(require("claims.manage"))
) -> dict:
    return await update_advance(actor, advance_id, body)


@router.post("/cash-advances/{advance_id}/liquidations")
async def cash_advances_liquidate(
    advance_id: str, body: LiquidationWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await liquidate_advance(actor, advance_id, body)
