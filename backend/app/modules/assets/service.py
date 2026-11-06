"""Asset use cases. No FastAPI imports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.errors import AppError
from app.core.repository import TenantRepo, api, guard_keys
from app.modules.assets.models import Asset, AssetAssignment
from app.modules.assets.policies import can_view_asset, can_view_assignment
from app.modules.assets.schemas import (
    AssetWrite,
    AssignmentCreate,
    AssignmentReturn,
    AssignmentUpdate,
)
from app.modules.employees.models import Employee
from app.shared.audit import write_audit

_STATUSES = {"available", "issued", "repair", "retired"}
_ASSET_SORT = {"created_at", "tag", "name", "status"}
_ASSIGNMENT_SORT = {"created_at", "issued_at", "returned_at"}


def _missing() -> AppError:
    return AppError("not_found", "Record not found", 404)


def _forbid() -> AppError:
    return AppError("forbidden", "You do not have access to this action", 403)


def _aware(value: datetime | None) -> datetime:
    current = value or utcnow()
    if current.tzinfo is None:
        return current.replace(tzinfo=UTC)
    return current


async def _audit(
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    session: Any = None,
) -> None:
    await write_audit(
        company_id=actor.company_id,
        actor_id=actor.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        session=session,
    )


def _check_status(status: str) -> None:
    if status not in _STATUSES:
        raise AppError("bad_request", "Unknown asset status", 400)


async def _open_assignment(company_id: str, asset_id: str) -> AssetAssignment | None:
    return await AssetAssignment.find_one(
        {"company_id": company_id, "asset_id": asset_id, "returned_at": None}
    )


def _asset_brief(asset: Asset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "tag": asset.tag,
        "name": asset.name,
        "serial_no": asset.serial_no,
        "status": asset.status,
    }


async def _attach_assets(actor: Actor, items: list[dict[str, Any]]) -> None:
    ids: list[PydanticObjectId] = []
    for item in items:
        try:
            ids.append(PydanticObjectId(item["asset_id"]))
        except Exception:
            continue
    if not ids:
        return
    found = await Asset.find(
        {"company_id": actor.company_id, "_id": {"$in": ids}, "deleted_at": None}
    ).to_list()
    by_id = {str(asset.id): asset for asset in found}
    for item in items:
        asset = by_id.get(item.get("asset_id", ""))
        item["asset"] = _asset_brief(asset) if asset is not None else None


async def list_assets(
    actor: Actor,
    page: int,
    page_size: int,
    q: str | None,
    sort: str | None,
    status: str | None,
) -> dict[str, Any]:
    if not (actor.has("assets.view") or actor.has("assets.manage")):
        raise _forbid()
    if status:
        _check_status(status)
    extra = {"status": status} if status else None
    return await TenantRepo(Asset, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("tag", "name", "serial_no"),
        sort_fields=_ASSET_SORT,
        q=q,
        sort=sort or "tag",
        extra=extra,
    )


async def create_asset(actor: Actor, body: AssetWrite) -> dict[str, Any]:
    _check_status(body.status)
    if body.status == "issued":
        raise AppError("bad_request", "Issue an asset through an assignment", 400)
    try:
        doc = await TenantRepo(Asset, actor).create(body)
    except DuplicateKeyError:
        raise AppError("conflict", "That asset tag is already used", 409) from None
    return api(doc)


async def get_asset(actor: Actor, asset_id: str) -> dict[str, Any]:
    asset = await TenantRepo(Asset, actor).get(asset_id)
    if not can_view_asset(actor, asset):
        raise _missing()
    return api(asset)


async def update_asset(actor: Actor, asset_id: str, body: AssetWrite) -> dict[str, Any]:
    asset = await TenantRepo(Asset, actor).get(asset_id)
    if "status" in body.model_fields_set:
        _check_status(body.status)
        open_row = await _open_assignment(asset.company_id, str(asset.id))
        if body.status == "issued" and open_row is None:
            raise AppError("bad_request", "Issue an asset through an assignment", 400)
        if body.status == "available" and open_row is not None:
            raise AppError(
                "conflict",
                "Return the open assignment before marking it available",
                409,
            )
    try:
        saved = await TenantRepo(Asset, actor).update(asset_id, body)
    except DuplicateKeyError:
        raise AppError("conflict", "That asset tag is already used", 409) from None
    return api(saved)


async def delete_asset(actor: Actor, asset_id: str) -> None:
    asset = await TenantRepo(Asset, actor).get(asset_id)
    if await _open_assignment(asset.company_id, str(asset.id)):
        raise AppError("conflict", "Return the asset before deleting it", 409)
    await TenantRepo(Asset, actor).soft_delete(asset_id)


async def _page_assignments(
    actor: Actor,
    extra: dict[str, Any],
    page: int,
    page_size: int,
    sort: str | None,
) -> dict[str, Any]:
    result = await TenantRepo(AssetAssignment, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields=_ASSIGNMENT_SORT,
        q=None,
        sort=sort or "-issued_at",
        extra=extra,
    )
    await _attach_assets(actor, result["items"])
    return result


async def assignments_for_employee(
    actor: Actor,
    employee_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    return await _page_assignments(
        actor,
        {"employee_id": employee_id},
        page,
        page_size,
        "-issued_at",
    )


async def list_assignments(
    actor: Actor,
    page: int,
    page_size: int,
    employee_id: str | None,
    asset_id: str | None,
    open_only: bool,
    sort: str | None,
) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = []
    if actor.has("assets.view") or actor.has("assets.manage"):
        if employee_id:
            clauses.append({"employee_id": employee_id})
    elif actor.has("self.service") and actor.employee_id:
        clauses.append({"employee_id": actor.employee_id})
    else:
        raise _forbid()
    if asset_id:
        clauses.append({"asset_id": asset_id})
    if open_only:
        clauses.append({"returned_at": None})
    extra = {"$and": clauses} if clauses else None
    return await _page_assignments(actor, extra or {}, page, page_size, sort)


async def my_assets(actor: Actor, page: int, page_size: int) -> dict[str, Any]:
    if not actor.employee_id:
        raise _missing()
    await TenantRepo(Employee, actor).get(actor.employee_id)
    return await assignments_for_employee(actor, actor.employee_id, page, page_size)


async def create_assignment(actor: Actor, body: AssignmentCreate) -> dict[str, Any]:
    asset = await TenantRepo(Asset, actor).get(body.asset_id)
    employee = await TenantRepo(Employee, actor).get(body.employee_id)
    if asset.status != "available":
        raise AppError("conflict", "Asset is not available", 409)
    if await _open_assignment(asset.company_id, str(asset.id)):
        raise AppError("conflict", "Asset is not available", 409)
    assignment = AssetAssignment(
        company_id=asset.company_id,
        asset_id=str(asset.id),
        employee_id=str(employee.id),
        issued_at=_aware(body.issued_at),
        condition_out=body.condition_out,
        acknowledgment_key=body.acknowledgment_key,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    before = api(asset)
    asset.status = "issued"
    asset.updated_at = utcnow()
    asset.updated_by = actor.user_id
    async with transaction() as session:
        await assignment.insert(session=session)
        await asset.save(session=session)
        await _audit(
            actor,
            "create",
            "asset_assignments",
            str(assignment.id),
            after=api(assignment),
            session=session,
        )
        await _audit(
            actor,
            "update",
            "assets",
            str(asset.id),
            before=before,
            after=api(asset),
            session=session,
        )
    payload = api(assignment)
    payload["asset"] = _asset_brief(asset)
    return payload


async def get_assignment(actor: Actor, assignment_id: str) -> dict[str, Any]:
    row = await TenantRepo(AssetAssignment, actor).get(assignment_id)
    if not can_view_assignment(actor, row):
        raise _missing()
    payload = api(row)
    asset = await Asset.get(row.asset_id)
    if asset is not None and asset.deleted_at is None and asset.company_id == row.company_id:
        payload["asset"] = _asset_brief(asset)
    else:
        payload["asset"] = None
    return payload


async def update_assignment(
    actor: Actor,
    assignment_id: str,
    body: AssignmentUpdate,
) -> dict[str, Any]:
    row = await TenantRepo(AssetAssignment, actor).get(assignment_id)
    before = api(row)
    data = guard_keys(body.model_dump(exclude_unset=True))
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    row.updated_by = actor.user_id
    await row.save()
    await _audit(
        actor,
        "update",
        "asset_assignments",
        str(row.id),
        before=before,
        after=api(row),
    )
    return await get_assignment(actor, str(row.id))


async def return_assignment(
    actor: Actor,
    assignment_id: str,
    body: AssignmentReturn,
) -> dict[str, Any]:
    row = await TenantRepo(AssetAssignment, actor).get(assignment_id)
    if row.returned_at is not None:
        raise AppError("conflict", "Asset was already returned", 409)
    asset = await TenantRepo(Asset, actor).get(row.asset_id)
    before_row = api(row)
    before_asset = api(asset)
    row.returned_at = _aware(body.returned_at)
    row.condition_in = body.condition_in
    row.updated_at = utcnow()
    row.updated_by = actor.user_id
    asset.status = "available"
    asset.updated_at = utcnow()
    asset.updated_by = actor.user_id
    async with transaction() as session:
        await row.save(session=session)
        await asset.save(session=session)
        await _audit(
            actor,
            "update",
            "asset_assignments",
            str(row.id),
            before=before_row,
            after=api(row),
            session=session,
        )
        await _audit(
            actor,
            "update",
            "assets",
            str(asset.id),
            before=before_asset,
            after=api(asset),
            session=session,
        )
    payload = api(row)
    payload["asset"] = _asset_brief(asset)
    return payload


async def delete_assignment(actor: Actor, assignment_id: str) -> None:
    row = await TenantRepo(AssetAssignment, actor).get(assignment_id)
    before = api(row)
    async with transaction() as session:
        if row.returned_at is None:
            asset = await Asset.get(row.asset_id, session=session)
            if (
                asset is not None
                and asset.company_id == row.company_id
                and asset.deleted_at is None
            ):
                before_asset = api(asset)
                asset.status = "available"
                asset.updated_at = utcnow()
                asset.updated_by = actor.user_id
                await asset.save(session=session)
                await _audit(
                    actor,
                    "update",
                    "assets",
                    str(asset.id),
                    before=before_asset,
                    after=api(asset),
                    session=session,
                )
        await row.delete(session=session)
        await _audit(
            actor,
            "delete",
            "asset_assignments",
            str(row.id),
            before=before,
            session=session,
        )
