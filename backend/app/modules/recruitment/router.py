from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.actor import Actor
from app.core.deps import require
from app.modules.recruitment.schemas import (
    ApplicantWrite,
    OfferWrite,
    OpeningWrite,
    PublicApplication,
    RequisitionWrite,
    ScorecardWrite,
    StageWrite,
)
from app.modules.recruitment.service import (
    add_scorecard,
    create_applicant,
    create_offer,
    create_opening,
    create_requisition,
    delete_opening,
    get_applicant,
    get_offer,
    get_opening,
    get_requisition,
    hire_applicant,
    list_applicants,
    list_offers,
    list_openings,
    list_requisitions,
    move_stage,
    public_apply,
    public_jobs,
    update_applicant,
    update_offer,
    update_opening,
    update_requisition,
)

router = APIRouter(tags=["recruitment"])


def _ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


@router.get("/manpower-requisitions")
async def requisitions_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("recruitment.view")),
) -> dict:
    return await list_requisitions(actor, page, page_size, q)


@router.post("/manpower-requisitions", status_code=201)
async def requisitions_create(
    body: RequisitionWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await create_requisition(actor, body)


@router.get("/manpower-requisitions/{id}")
async def requisitions_get(id: str, actor: Actor = Depends(require("recruitment.view"))) -> dict:
    return await get_requisition(actor, id)


@router.put("/manpower-requisitions/{id}")
async def requisitions_update(
    id: str,
    body: RequisitionWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await update_requisition(actor, id, body)


@router.get("/job-openings")
async def openings_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("recruitment.view")),
) -> dict:
    return await list_openings(actor, page, page_size, q)


@router.post("/job-openings", status_code=201)
async def openings_create(
    body: OpeningWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await create_opening(actor, body)


@router.get("/job-openings/{id}")
async def openings_get(id: str, actor: Actor = Depends(require("recruitment.view"))) -> dict:
    return await get_opening(actor, id)


@router.put("/job-openings/{id}")
async def openings_update(
    id: str,
    body: OpeningWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await update_opening(actor, id, body)


@router.delete("/job-openings/{id}", status_code=204)
async def openings_delete(
    id: str,
    actor: Actor = Depends(require("recruitment.manage")),
) -> Response:
    await delete_opening(actor, id)
    return Response(status_code=204)


@router.get("/applicants")
async def applicants_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    stage: str | None = None,
    actor: Actor = Depends(require("recruitment.view")),
) -> dict:
    return await list_applicants(actor, page, page_size, q, stage)


@router.post("/applicants", status_code=201)
async def applicants_create(
    body: ApplicantWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await create_applicant(actor, body)


@router.get("/applicants/{id}")
async def applicants_get(id: str, actor: Actor = Depends(require("recruitment.view"))) -> dict:
    return await get_applicant(actor, id)


@router.put("/applicants/{id}")
async def applicants_update(
    id: str,
    body: ApplicantWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await update_applicant(actor, id, body)


@router.post("/applicants/{id}/move-stage")
async def applicants_move(
    id: str,
    body: StageWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await move_stage(actor, id, body)


@router.post("/applicants/{id}/scorecards")
async def applicants_score(
    id: str,
    body: ScorecardWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await add_scorecard(actor, id, body)


@router.post("/applicants/{id}/hire")
async def applicants_hire(id: str, actor: Actor = Depends(require("recruitment.manage"))) -> dict:
    return await hire_applicant(actor, id)


@router.get("/job-offers")
async def offers_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("recruitment.view")),
) -> dict:
    return await list_offers(actor, page, page_size, q)


@router.post("/job-offers", status_code=201)
async def offers_create(
    body: OfferWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await create_offer(actor, body)


@router.get("/job-offers/{id}")
async def offers_get(id: str, actor: Actor = Depends(require("recruitment.view"))) -> dict:
    return await get_offer(actor, id)


@router.put("/job-offers/{id}")
async def offers_update(
    id: str,
    body: OfferWrite,
    actor: Actor = Depends(require("recruitment.manage")),
) -> dict:
    return await update_offer(actor, id, body)


@router.get("/public/{company_slug}/jobs")
async def public_jobs_route(company_slug: str, request: Request) -> dict:
    return await public_jobs(company_slug, _ip(request))


@router.post("/public/{company_slug}/jobs/{id}/apply", status_code=201)
async def public_apply_route(
    company_slug: str,
    id: str,
    body: PublicApplication,
    request: Request,
) -> dict:
    return await public_apply(company_slug, id, body, _ip(request))
