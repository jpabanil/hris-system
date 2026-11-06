from __future__ import annotations

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.repository import TenantRepo, api, guard_keys
from app.modules.organization.models import (
    Branch,
    Company,
    Department,
    GeoFence,
    Position,
)
from app.modules.organization.schemas import (
    BranchWrite,
    CompanyWrite,
    DepartmentWrite,
)
from app.shared.audit import write_audit


async def create_company(actor: Actor, body: CompanyWrite) -> dict:
    actor.require("companies.manage")
    exists = await Company.find_one(Company.slug == body.slug, Company.deleted_at == None)  # noqa: E711
    if exists:
        raise AppError("conflict", "That company slug is already used", 409)
    data = guard_keys(body.model_dump())
    company = Company(**data, created_by=actor.user_id, updated_by=actor.user_id)
    await company.insert()
    await write_audit(
        company_id=str(company.id),
        actor_id=actor.user_id,
        action="create",
        entity_type="companies",
        entity_id=str(company.id),
        after=api(company),
    )
    return api(company)


async def list_companies(actor: Actor) -> dict:
    if actor.is_superadmin:
        items = await Company.find(Company.deleted_at == None).to_list()  # noqa: E711
    elif actor.company_id:
        company = await Company.get(actor.company_id)
        items = [company] if company and company.deleted_at is None else []
    else:
        items = []
    return {
        "items": [api(item) for item in items],
        "total": len(items),
        "page": 1,
        "page_size": 100,
    }


async def update_company(actor: Actor, company_id: str, body: CompanyWrite) -> dict:
    if not actor.is_superadmin and actor.company_id != company_id:
        raise AppError("forbidden", "You cannot edit this company", 403)
    if not actor.has("org.manage") and not actor.has("companies.manage"):
        raise AppError("forbidden", "You do not have access to this action", 403)
    company = await Company.get(company_id)
    if company is None or company.deleted_at is not None:
        raise AppError("not_found", "Record not found", 404)
    if body.revision is None or body.revision != company.revision:
        raise AppError("conflict", "This record changed. Reload and try again.", 409)
    before = api(company)
    for key, value in guard_keys(body.model_dump()).items():
        setattr(company, key, value)
    company.revision += 1
    company.updated_at = utcnow()
    company.updated_by = actor.user_id
    await company.save()
    await write_audit(
        company_id=str(company.id),
        actor_id=actor.user_id,
        action="update",
        entity_type="companies",
        entity_id=str(company.id),
        before=before,
        after=api(company),
    )
    return api(company)


def _branch(body: BranchWrite) -> dict:
    data = guard_keys(body.model_dump())
    lat = data.pop("geofence_lat", None)
    lng = data.pop("geofence_lng", None)
    radius = data.pop("geofence_radius_m", None)
    if lat is not None and lng is not None:
        data["geofence"] = GeoFence(lat=lat, lng=lng, radius_m=radius or 150)
    return data


async def save_branch(actor: Actor, body: BranchWrite, branch_id: str | None = None) -> dict:
    repo = TenantRepo(Branch, actor)
    if branch_id is None:
        payload = BranchWrite.model_validate(body.model_dump())
        data = _branch(payload)
        branch = Branch(
            **data,
            company_id=actor.company_id,
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await branch.insert()
        return api(branch)
    branch = await repo.get(branch_id)
    if body.revision != branch.revision:
        raise AppError("conflict", "This record changed. Reload and try again.", 409)
    for key, value in _branch(body).items():
        setattr(branch, key, value)
    branch.revision += 1
    branch.updated_at = utcnow()
    await branch.save()
    return api(branch)


async def save_department(
    actor: Actor, body: DepartmentWrite, department_id: str | None = None
) -> dict:
    ancestors: list[str] = []
    if body.parent_id:
        parent = await TenantRepo(Department, actor).get(body.parent_id)
        ancestors = [*parent.ancestors, str(parent.id)]
    if department_id is None:
        department = Department(
            company_id=actor.company_id or "",
            name=body.name,
            code=body.code,
            parent_id=body.parent_id,
            ancestors=ancestors,
            head_employee_id=body.head_employee_id,
            cost_center_id=body.cost_center_id,
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await department.insert()
        return api(department)
    department = await TenantRepo(Department, actor).get(department_id)
    if body.revision != department.revision:
        raise AppError("conflict", "This record changed. Reload and try again.", 409)
    department.name = body.name
    department.code = body.code
    department.parent_id = body.parent_id
    department.ancestors = ancestors
    department.head_employee_id = body.head_employee_id
    department.cost_center_id = body.cost_center_id
    department.revision += 1
    department.updated_at = utcnow()
    await department.save()
    return api(department)


async def org_chart(actor: Actor) -> dict:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    departments = await Department.find(
        {"company_id": actor.company_id, "deleted_at": None}
    ).to_list()
    positions = await Position.find({"company_id": actor.company_id, "deleted_at": None}).to_list()
    people: list[dict] = []
    try:
        from app.modules.employees.models import Employee

        employees = await Employee.find(
            {"company_id": actor.company_id, "deleted_at": None}
        ).to_list()
        people = [
            {
                "id": str(employee.id),
                "employee_no": employee.employee_no,
                "name": employee.model_dump(mode="json").get("name"),
                "department_id": employee.department_id,
                "position_id": employee.position_id,
                "reports_to": employee.reports_to,
            }
            for employee in employees
        ]
    except Exception:
        people = []
    return {
        "departments": [api(item) for item in departments],
        "positions": [api(item) for item in positions],
        "employees": people,
    }


async def list_model(
    actor: Actor,
    model,
    search: tuple[str, ...],
    page: int,
    page_size: int,
    q: str | None,
):
    return await TenantRepo(model, actor).list(
        page=page,
        page_size=page_size,
        search_fields=search,
        sort_fields={"created_at", "name", "code", "title"},
        q=q,
        sort="name",
    )


async def create_simple(actor: Actor, model, body):
    doc = await TenantRepo(model, actor).create(body)
    return api(doc)


async def update_simple(actor: Actor, model, doc_id: str, body):
    doc = await TenantRepo(model, actor).update(doc_id, body)
    return api(doc)
