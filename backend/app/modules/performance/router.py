from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.actor import Actor
from app.core.deps import require
from app.modules.performance.schemas import (
    CycleWrite,
    GoalWrite,
    OneOnOneWrite,
    ProbationWrite,
    ReviewWrite,
    TemplateWrite,
)
from app.modules.performance.service import (
    create_cycle,
    create_goal,
    create_one_on_one,
    create_probation,
    create_review,
    create_template,
    get_cycle,
    get_goal,
    get_one_on_one,
    get_probation,
    get_review,
    get_template,
    list_cycles,
    list_goals,
    list_one_on_ones,
    list_probations,
    list_reviews,
    list_templates,
    update_cycle,
    update_goal,
    update_one_on_one,
    update_probation,
    update_review,
    update_template,
)

router = APIRouter(tags=["performance"])


@router.get("/review-cycles")
async def cycles_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("performance.view")),
) -> dict:
    return await list_cycles(actor, page, page_size, q)


@router.post("/review-cycles", status_code=201)
async def cycles_create(
    body: CycleWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await create_cycle(actor, body)


@router.get("/review-cycles/{id}")
async def cycles_get(id: str, actor: Actor = Depends(require("performance.view"))) -> dict:
    return await get_cycle(actor, id)


@router.put("/review-cycles/{id}")
async def cycles_update(
    id: str,
    body: CycleWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await update_cycle(actor, id, body)


@router.get("/review-templates")
async def templates_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("performance.view")),
) -> dict:
    return await list_templates(actor, page, page_size, q)


@router.post("/review-templates", status_code=201)
async def templates_create(
    body: TemplateWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await create_template(actor, body)


@router.get("/review-templates/{id}")
async def templates_get(id: str, actor: Actor = Depends(require("performance.view"))) -> dict:
    return await get_template(actor, id)


@router.put("/review-templates/{id}")
async def templates_update(
    id: str,
    body: TemplateWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await update_template(actor, id, body)


@router.get("/performance-reviews")
async def reviews_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("performance.view")),
) -> dict:
    return await list_reviews(actor, page, page_size, q)


@router.post("/performance-reviews", status_code=201)
async def reviews_create(
    body: ReviewWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await create_review(actor, body)


@router.get("/performance-reviews/{id}")
async def reviews_get(id: str, actor: Actor = Depends(require("performance.view"))) -> dict:
    return await get_review(actor, id)


@router.put("/performance-reviews/{id}")
async def reviews_update(
    id: str,
    body: ReviewWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await update_review(actor, id, body)


@router.get("/goals")
async def goals_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("performance.view")),
) -> dict:
    return await list_goals(actor, page, page_size, q)


@router.post("/goals", status_code=201)
async def goals_create(
    body: GoalWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await create_goal(actor, body)


@router.get("/goals/{id}")
async def goals_get(id: str, actor: Actor = Depends(require("performance.view"))) -> dict:
    return await get_goal(actor, id)


@router.put("/goals/{id}")
async def goals_update(
    id: str,
    body: GoalWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await update_goal(actor, id, body)


@router.get("/probation-evaluations")
async def probations_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("performance.view")),
) -> dict:
    return await list_probations(actor, page, page_size, q)


@router.post("/probation-evaluations", status_code=201)
async def probations_create(
    body: ProbationWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await create_probation(actor, body)


@router.get("/probation-evaluations/{id}")
async def probations_get(id: str, actor: Actor = Depends(require("performance.view"))) -> dict:
    return await get_probation(actor, id)


@router.put("/probation-evaluations/{id}")
async def probations_update(
    id: str,
    body: ProbationWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await update_probation(actor, id, body)


@router.get("/one-on-ones")
async def meetings_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("performance.view")),
) -> dict:
    return await list_one_on_ones(actor, page, page_size, q)


@router.post("/one-on-ones", status_code=201)
async def meetings_create(
    body: OneOnOneWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await create_one_on_one(actor, body)


@router.get("/one-on-ones/{id}")
async def meetings_get(id: str, actor: Actor = Depends(require("performance.view"))) -> dict:
    return await get_one_on_one(actor, id)


@router.put("/one-on-ones/{id}")
async def meetings_update(
    id: str,
    body: OneOnOneWrite,
    actor: Actor = Depends(require("performance.manage")),
) -> dict:
    return await update_one_on_one(actor, id, body)
