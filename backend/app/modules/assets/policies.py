"""Asset visibility. Self-service users only see assignments issued to them."""

from __future__ import annotations

from app.core.actor import Actor
from app.modules.assets.models import Asset, AssetAssignment


def can_view_asset(actor: Actor, asset: Asset) -> bool:
    if asset.deleted_at is not None:
        return False
    if actor.company_id and asset.company_id != actor.company_id:
        return False
    return actor.has("assets.view") or actor.has("assets.manage")


def can_view_assignment(actor: Actor, assignment: AssetAssignment) -> bool:
    if actor.company_id and assignment.company_id != actor.company_id:
        return False
    if actor.has("assets.view") or actor.has("assets.manage"):
        return True
    return bool(
        actor.has("self.service")
        and actor.employee_id
        and assignment.employee_id == actor.employee_id
    )
