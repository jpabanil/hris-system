from __future__ import annotations

from datetime import date

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.repository import TenantRepo, api
from app.modules.training import policies
from app.modules.training.models import Training, TrainingAttendee, TrainingBond
from app.modules.training.schemas import AttendeeWrite, BondWrite, TrainingWrite


async def _page(
    actor: Actor,
    model,
    search: tuple[str, ...],
    page: int,
    page_size: int,
    q: str | None,
) -> dict:
    policies.require_view(actor)
    return await TenantRepo(model, actor).list(
        page=page,
        page_size=page_size,
        search_fields=search,
        sort_fields={"created_at", "title", "date"},
        q=q,
        sort="-created_at",
    )


async def list_trainings(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, Training, ("title", "provider"), page, page_size, q)


async def get_training(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(Training, actor).get(doc_id))


async def create_training(actor: Actor, body: TrainingWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Training, actor).create(body))


async def update_training(actor: Actor, doc_id: str, body: TrainingWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Training, actor).update(doc_id, body))


async def list_attendees(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    return await _page(actor, TrainingAttendee, ("employee_id", "status"), page, page_size, q)


async def get_attendee(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(TrainingAttendee, actor).get(doc_id))


async def create_attendee(actor: Actor, body: AttendeeWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(TrainingAttendee, actor).create(body))


async def update_attendee(actor: Actor, doc_id: str, body: AttendeeWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(TrainingAttendee, actor).update(doc_id, body))


async def list_bonds(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_view(actor)
    page_data = await TenantRepo(TrainingBond, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("employee_id", "training_id"),
        sort_fields={"created_at", "bond_until"},
        q=q,
        sort="-created_at",
    )
    today = utcnow().date()
    for item in page_data["items"]:
        raw = item.get("bond_until")
        if isinstance(raw, str) and len(raw) >= 10:
            year, month, day = int(raw[0:4]), int(raw[5:7]), int(raw[8:10])
            item["open"] = policies.bond_still_open(date(year, month, day), today)
    return page_data


async def get_bond(actor: Actor, doc_id: str) -> dict:
    policies.require_view(actor)
    bond = await TenantRepo(TrainingBond, actor).get(doc_id)
    data = api(bond)
    data["open"] = policies.bond_still_open(bond.bond_until, utcnow().date())
    return data


async def create_bond(actor: Actor, body: BondWrite) -> dict:
    policies.require_manage(actor)
    policies.bond_still_open(body.bond_until, utcnow().date())
    return api(await TenantRepo(TrainingBond, actor).create(body))


async def update_bond(actor: Actor, doc_id: str, body: BondWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(TrainingBond, actor).update(doc_id, body))
