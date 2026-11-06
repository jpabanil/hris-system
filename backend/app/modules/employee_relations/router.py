from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.employee_relations.schemas import (
    CaseWrite,
    DecisionBody,
    ExplanationBody,
    GrievanceWrite,
    HearingBody,
    IncidentWrite,
    NteBody,
    OffenseWrite,
    PolicyWrite,
)
from app.modules.employee_relations.service import (
    acknowledge_policy,
    create_case,
    create_grievance,
    create_incident,
    create_offense,
    create_policy,
    decide_case,
    delete_offense,
    delete_policy,
    get_case,
    get_grievance,
    get_incident,
    get_offense,
    get_policy,
    issue_nte,
    list_cases,
    list_grievances,
    list_incidents,
    list_offenses,
    list_policies,
    record_explanation,
    schedule_hearing,
    update_case,
    update_grievance,
    update_incident,
    update_offense,
    update_policy,
)

router = APIRouter(tags=["employee-relations"])


def _ip(request: Request) -> str:
    if request.client is None:
        return ""
    return request.client.host


@router.get("/offenses")
async def offenses_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_offenses(actor, page, page_size, q)


@router.post("/offenses", status_code=201)
async def offenses_create(
    body: OffenseWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await create_offense(actor, body)


@router.get("/offenses/{id}")
async def offenses_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_offense(actor, id)


@router.put("/offenses/{id}")
async def offenses_update(
    id: str,
    body: OffenseWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await update_offense(actor, id, body)


@router.delete("/offenses/{id}", status_code=204)
async def offenses_delete(id: str, actor: Actor = Depends(require("relations.manage"))) -> Response:
    await delete_offense(actor, id)
    return Response(status_code=204)


@router.get("/incident-reports")
async def incidents_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_incidents(actor, page, page_size, q)


@router.post("/incident-reports", status_code=201)
async def incidents_create(
    body: IncidentWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await create_incident(actor, body)


@router.get("/incident-reports/{id}")
async def incidents_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_incident(actor, id)


@router.put("/incident-reports/{id}")
async def incidents_update(
    id: str,
    body: IncidentWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await update_incident(actor, id, body)


@router.get("/disciplinary-cases")
async def cases_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_cases(actor, page, page_size, q)


@router.post("/disciplinary-cases", status_code=201)
async def cases_create(
    body: CaseWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await create_case(actor, body)


@router.get("/disciplinary-cases/{id}")
async def cases_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_case(actor, id)


@router.put("/disciplinary-cases/{id}")
async def cases_update(
    id: str,
    body: CaseWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await update_case(actor, id, body)


@router.post("/disciplinary-cases/{id}/issue-nte")
async def cases_nte(
    id: str,
    body: NteBody,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await issue_nte(actor, id, body)


@router.post("/disciplinary-cases/{id}/record-explanation")
async def cases_explanation(
    id: str,
    body: ExplanationBody,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await record_explanation(actor, id, body)


@router.post("/disciplinary-cases/{id}/schedule-hearing")
async def cases_hearing(
    id: str,
    body: HearingBody,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await schedule_hearing(actor, id, body)


@router.post("/disciplinary-cases/{id}/decide")
async def cases_decide(
    id: str,
    body: DecisionBody,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await decide_case(actor, id, body)


@router.get("/grievances")
async def grievances_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_grievances(actor, page, page_size, q)


@router.post("/grievances", status_code=201)
async def grievances_create(body: GrievanceWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_grievance(actor, body)


@router.get("/grievances/{id}")
async def grievances_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_grievance(actor, id)


@router.put("/grievances/{id}")
async def grievances_update(
    id: str,
    body: GrievanceWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await update_grievance(actor, id, body)


@router.get("/policies")
async def policies_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_policies(actor, page, page_size, q)


@router.post("/policies", status_code=201)
async def policies_create(
    body: PolicyWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await create_policy(actor, body)


@router.get("/policies/{id}")
async def policies_get(id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_policy(actor, id)


@router.put("/policies/{id}")
async def policies_update(
    id: str,
    body: PolicyWrite,
    actor: Actor = Depends(require("relations.manage")),
) -> dict:
    return await update_policy(actor, id, body)


@router.delete("/policies/{id}", status_code=204)
async def policies_delete(id: str, actor: Actor = Depends(require("relations.manage"))) -> Response:
    await delete_policy(actor, id)
    return Response(status_code=204)


@router.post("/policies/{id}/acknowledge", status_code=201)
async def policies_ack(id: str, request: Request, actor: Actor = Depends(get_actor)) -> dict:
    return await acknowledge_policy(actor, id, _ip(request))
