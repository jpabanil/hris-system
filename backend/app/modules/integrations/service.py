"""Webhooks. The secret is stored as given and is not written to logs."""

from __future__ import annotations

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.repository import TenantRepo, api
from app.modules.integrations import policies
from app.modules.integrations.models import Webhook, WebhookDelivery
from app.modules.integrations.schemas import WebhookUpdate, WebhookWrite


async def list_webhooks(actor: Actor, page: int, page_size: int, q: str | None) -> dict:
    policies.require_manage(actor)
    page_data = await TenantRepo(Webhook, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("event", "url"),
        sort_fields={"created_at", "event"},
        q=q,
        sort="-created_at",
    )
    page_data["items"] = [policies.redact_webhook(item) for item in page_data["items"]]
    return page_data


async def get_webhook(actor: Actor, doc_id: str) -> dict:
    policies.require_manage(actor)
    return policies.redact_webhook(api(await TenantRepo(Webhook, actor).get(doc_id)))


async def create_webhook(actor: Actor, body: WebhookWrite) -> dict:
    policies.require_manage(actor)
    policies.require_secret(body.secret)
    doc = await TenantRepo(Webhook, actor).create(body)
    return policies.redact_webhook(api(doc))


async def update_webhook(actor: Actor, doc_id: str, body: WebhookUpdate) -> dict:
    policies.require_manage(actor)
    if body.secret is not None:
        policies.require_secret(body.secret)
    doc = await TenantRepo(Webhook, actor).update(doc_id, body)
    return policies.redact_webhook(api(doc))


async def delete_webhook(actor: Actor, doc_id: str) -> None:
    policies.require_manage(actor)
    hook = await TenantRepo(Webhook, actor).get(doc_id)
    hook.is_active = False
    hook.updated_at = utcnow()
    hook.updated_by = actor.user_id
    await hook.save()


async def test_webhook(actor: Actor, doc_id: str) -> dict:
    company = policies.require_manage(actor)
    hook = await TenantRepo(Webhook, actor).get(doc_id)
    delivery = WebhookDelivery(
        company_id=company,
        webhook_id=str(hook.id),
        event=hook.event,
        status="test",
        attempts=0,
        response="",
        created_at=utcnow(),
    )
    await delivery.insert()
    return api(delivery)


async def deliver(event: str, company_id: str, payload: dict) -> int:
    if not isinstance(payload, dict):
        return 0
    hooks = await Webhook.find(
        {"company_id": company_id, "event": event, "is_active": True}
    ).to_list()
    recorded = 0
    for hook in hooks:
        delivery = WebhookDelivery(
            company_id=company_id,
            webhook_id=str(hook.id),
            event=event,
            status="recorded",
            attempts=1,
            response="recorded",
            created_at=utcnow(),
        )
        await delivery.insert()
        recorded += 1
    return recorded
