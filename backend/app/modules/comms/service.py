from __future__ import annotations

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.repository import TenantRepo, api
from app.modules.comms import policies
from app.modules.comms.models import Announcement, AnnouncementRead
from app.modules.comms.schemas import AnnouncementWrite


async def list_announcements(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_read(actor)
    return await TenantRepo(Announcement, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("title", "body"),
        sort_fields={"created_at", "publish_at", "title"},
        q=q,
        sort="-created_at",
    )


async def get_announcement(actor: Actor, doc_id: str) -> dict:
    policies.require_read(actor)
    return api(await TenantRepo(Announcement, actor).get(doc_id))


async def create_announcement(actor: Actor, body: AnnouncementWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Announcement, actor).create(body))


async def update_announcement(actor: Actor, doc_id: str, body: AnnouncementWrite) -> dict:
    policies.require_manage(actor)
    return api(await TenantRepo(Announcement, actor).update(doc_id, body))


async def delete_announcement(actor: Actor, doc_id: str) -> None:
    policies.require_manage(actor)
    await TenantRepo(Announcement, actor).soft_delete(doc_id)


async def mark_read(actor: Actor, doc_id: str) -> dict:
    company = policies.require_read(actor)
    announcement = await TenantRepo(Announcement, actor).get(doc_id)
    existing = await AnnouncementRead.find_one(
        {"company_id": company, "announcement_id": str(announcement.id), "user_id": actor.user_id}
    )
    if existing is not None:
        return api(existing)
    row = AnnouncementRead(
        company_id=company,
        announcement_id=str(announcement.id),
        user_id=actor.user_id,
        read_at=utcnow(),
    )
    await row.insert()
    return api(row)
