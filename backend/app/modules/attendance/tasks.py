"""Celery entry points. The worker imports compute_open_days."""

from __future__ import annotations

from app.modules.attendance.service import compute_open_days as _compute_open_days


async def compute_open_days() -> None:
    await _compute_open_days()
