"""Payroll compute entry point. Celery imports compute_run; HTTP may call it too."""

from __future__ import annotations


async def compute_run(run_id: str) -> None:
    from app.modules.payroll.service import execute_compute

    await execute_compute(run_id)
