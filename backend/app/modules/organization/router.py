from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.core.repository import TenantRepo, api
from app.modules.organization.models import Branch, CostCenter, Department, Position, SalaryGrade
from app.modules.organization.schemas import (
    BranchWrite,
    CompanyWrite,
    CostCenterWrite,
    DepartmentWrite,
    PositionWrite,
    SalaryGradeWrite,
)
from app.modules.organization.service import (
    create_company,
    list_companies,
    list_model,
    org_chart,
    save_branch,
    save_department,
    update_company,
    update_simple,
)

router = APIRouter(tags=["organization"])


@router.get("/companies")
async def companies(actor: Actor = Depends(get_actor)) -> dict:
    return await list_companies(actor)


@router.post("/companies", status_code=201)
async def companies_create(
    body: CompanyWrite, actor: Actor = Depends(require("companies.manage"))
) -> dict:
    return await create_company(actor, body)


@router.put("/companies/{company_id}")
async def companies_update(
    company_id: str, body: CompanyWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await update_company(actor, company_id, body)


@router.get("/branches")
async def branches(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("org.view")),
) -> dict:
    return await list_model(actor, Branch, ("name", "city"), page, page_size, q)


@router.post("/branches", status_code=201)
async def branches_create(body: BranchWrite, actor: Actor = Depends(require("org.manage"))) -> dict:
    return await save_branch(actor, body)


@router.put("/branches/{branch_id}")
async def branches_update(
    branch_id: str, body: BranchWrite, actor: Actor = Depends(require("org.manage"))
) -> dict:
    return await save_branch(actor, body, branch_id)


@router.delete("/branches/{branch_id}", status_code=204)
async def branches_delete(
    branch_id: str, actor: Actor = Depends(require("org.manage"))
) -> Response:
    await TenantRepo(Branch, actor).soft_delete(branch_id)
    return Response(status_code=204)


@router.get("/departments")
async def departments(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("org.view")),
) -> dict:
    return await list_model(actor, Department, ("name", "code"), page, page_size, q)


@router.post("/departments", status_code=201)
async def departments_create(
    body: DepartmentWrite, actor: Actor = Depends(require("org.manage"))
) -> dict:
    return await save_department(actor, body)


@router.put("/departments/{department_id}")
async def departments_update(
    department_id: str, body: DepartmentWrite, actor: Actor = Depends(require("org.manage"))
) -> dict:
    return await save_department(actor, body, department_id)


@router.get("/positions")
async def positions(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("org.view")),
) -> dict:
    return await list_model(actor, Position, ("title",), page, page_size, q)


@router.post("/positions", status_code=201)
async def positions_create(
    body: PositionWrite, actor: Actor = Depends(require("org.manage"))
) -> dict:
    return api(await TenantRepo(Position, actor).create(body))


@router.put("/positions/{position_id}")
async def positions_update(
    position_id: str, body: PositionWrite, actor: Actor = Depends(require("org.manage"))
) -> dict:
    return await update_simple(actor, Position, position_id, body)


@router.get("/salary-grades")
async def grades(actor: Actor = Depends(require("org.view"))) -> dict:
    return await list_model(actor, SalaryGrade, ("code",), 1, 100, None)


@router.post("/salary-grades", status_code=201)
async def grades_create(
    body: SalaryGradeWrite, actor: Actor = Depends(require("org.manage"))
) -> dict:
    return api(await TenantRepo(SalaryGrade, actor).create(body))


@router.get("/cost-centers")
async def centers(actor: Actor = Depends(require("org.view"))) -> dict:
    return await list_model(actor, CostCenter, ("code", "name"), 1, 100, None)


@router.post("/cost-centers", status_code=201)
async def centers_create(
    body: CostCenterWrite, actor: Actor = Depends(require("org.manage"))
) -> dict:
    return api(await TenantRepo(CostCenter, actor).create(body))


@router.get("/org-chart")
async def chart(actor: Actor = Depends(require("org.view"))) -> dict:
    return await org_chart(actor)
