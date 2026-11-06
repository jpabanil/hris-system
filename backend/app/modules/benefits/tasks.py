"""Benefit tasks. Dependent deductions are created in the service on enrollment."""

from __future__ import annotations


async def sync_enrollment_deduction(enrollment_id: str) -> None:
    from app.modules.benefits.service import ensure_deduction_for_enrollment

    await ensure_deduction_for_enrollment(enrollment_id)
