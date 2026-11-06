"""Claim tasks. Approval side effects are registered from the service module."""

from __future__ import annotations


async def refresh_claim_status(claim_id: str) -> None:
    """Imported by workers if a claim decision needs to be reapplied. No-op placeholder."""
    from app.modules.claims.models import Claim

    claim = await Claim.get(claim_id)
    if claim is None:
        return
    _ = claim.status
