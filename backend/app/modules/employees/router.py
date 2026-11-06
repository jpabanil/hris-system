"""Employee routes. Permission checks stay here; rules stay in the service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.employees.schemas import (
    CompensationWrite,
    DocumentWrite,
    EmployeeCreate,
    EmployeeUpdate,
    MovementWrite,
    ProfileUpdateEdit,
    ProfileUpdateWrite,
    SensitiveWrite,
)
from app.modules.employees.service import (
    add_compensation,
    add_document,
    add_movement,
    create_employee,
    create_profile_update,
    delete_document,
    delete_employee,
    delete_profile_update,
    employee_assets,
    employee_timeline,
    get_employee,
    get_profile_update,
    get_sensitive,
    list_compensation,
    list_documents,
    list_employees,
    list_movements,
    list_profile_updates,
    my_profile,
    save_sensitive,
    update_employee,
    update_profile_update,
)

router = APIRouter(tags=["employees"])


@router.get("/me/profile")
async def me_profile(actor: Actor = Depends(require("self.service"))) -> dict:
    return await my_profile(actor)


@router.get("/employees")
async def employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    sort: str | None = None,
    department_id: str | None = None,
    branch_id: str | None = None,
    position_id: str | None = None,
    employment_status: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_employees(
        actor,
        page,
        page_size,
        q,
        sort,
        department_id=department_id,
        branch_id=branch_id,
        position_id=position_id,
        employment_status=employment_status,
    )


@router.post("/employees", status_code=201)
async def employees_create(
    body: EmployeeCreate,
    actor: Actor = Depends(require("employees.manage")),
) -> dict:
    return await create_employee(actor, body)


@router.get("/employees/{employee_id}")
async def employees_get(employee_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_employee(actor, employee_id)


@router.put("/employees/{employee_id}")
async def employees_update(
    employee_id: str,
    body: EmployeeUpdate,
    actor: Actor = Depends(require("employees.manage")),
) -> dict:
    return await update_employee(actor, employee_id, body)


@router.delete("/employees/{employee_id}", status_code=204)
async def employees_delete(
    employee_id: str,
    actor: Actor = Depends(require("employees.manage")),
) -> Response:
    await delete_employee(actor, employee_id)
    return Response(status_code=204)


@router.get("/employees/{employee_id}/timeline")
async def employees_timeline(employee_id: str, actor: Actor = Depends(get_actor)) -> list:
    return await employee_timeline(actor, employee_id)


@router.get("/employees/{employee_id}/compensation")
async def employees_compensation(
    employee_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_compensation(actor, employee_id, page, page_size)


@router.post("/employees/{employee_id}/compensation", status_code=201)
async def employees_compensation_add(
    employee_id: str,
    body: CompensationWrite,
    actor: Actor = Depends(require("employees.manage")),
) -> dict:
    return await add_compensation(actor, employee_id, body)


@router.get("/employees/{employee_id}/movements")
async def employees_movements(
    employee_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_movements(actor, employee_id, page, page_size)


@router.post("/employees/{employee_id}/movements", status_code=201)
async def employees_movements_add(
    employee_id: str,
    body: MovementWrite,
    actor: Actor = Depends(require("employees.manage")),
) -> dict:
    return await add_movement(actor, employee_id, body)


@router.get("/employees/{employee_id}/documents")
async def employees_documents(
    employee_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_documents(actor, employee_id, page, page_size)


@router.post("/employees/{employee_id}/documents", status_code=201)
async def employees_documents_add(
    employee_id: str,
    body: DocumentWrite,
    actor: Actor = Depends(require("employees.manage")),
) -> dict:
    return await add_document(actor, employee_id, body)


@router.delete("/employees/{employee_id}/documents/{document_id}", status_code=204)
async def employees_documents_delete(
    employee_id: str,
    document_id: str,
    actor: Actor = Depends(require("employees.manage")),
) -> Response:
    await delete_document(actor, employee_id, document_id)
    return Response(status_code=204)


@router.get("/employees/{employee_id}/assets")
async def employees_assets(
    employee_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await employee_assets(actor, employee_id, page, page_size)


@router.get("/employees/{employee_id}/sensitive")
async def employees_sensitive(employee_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_sensitive(actor, employee_id)


@router.put("/employees/{employee_id}/sensitive")
async def employees_sensitive_save(
    employee_id: str,
    body: SensitiveWrite,
    actor: Actor = Depends(require("employees.manage")),
) -> dict:
    return await save_sensitive(actor, employee_id, body)


@router.get("/profile-update-requests")
async def profile_updates(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    employee_id: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_profile_updates(actor, page, page_size, employee_id)


@router.post("/profile-update-requests", status_code=201)
async def profile_updates_create(
    body: ProfileUpdateWrite,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await create_profile_update(actor, body)


@router.get("/profile-update-requests/{request_id}")
async def profile_updates_get(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_profile_update(actor, request_id)


@router.put("/profile-update-requests/{request_id}")
async def profile_updates_update(
    request_id: str,
    body: ProfileUpdateEdit,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await update_profile_update(actor, request_id, body)


@router.delete("/profile-update-requests/{request_id}", status_code=204)
async def profile_updates_delete(request_id: str, actor: Actor = Depends(get_actor)) -> Response:
    await delete_profile_update(actor, request_id)
    return Response(status_code=204)
