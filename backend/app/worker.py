"""Celery worker. Tasks open their own event loop and reuse one Beanie init."""

from __future__ import annotations

import asyncio

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("hris", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.beat_schedule = {
    "approval-reminders": {"task": "hris.approval_reminders", "schedule": 3600.0},
    "attendance-nightly": {
        "task": "hris.attendance_nightly",
        "schedule": crontab(hour=2, minute=15),
    },
    "leave-accrual": {
        "task": "hris.leave_month",
        "schedule": crontab(hour=1, minute=10, day_of_month=1),
    },
    "reminders": {"task": "hris.reminders", "schedule": crontab(hour=7, minute=0)},
    "retention": {"task": "hris.retention", "schedule": crontab(hour=3, minute=30)},
    "deactivate-separated": {
        "task": "hris.deactivate_separated",
        "schedule": crontab(hour=0, minute=20),
    },
}
celery_app.conf.timezone = "Asia/Manila"

_loop: asyncio.AbstractEventLoop | None = None


def run_async(coro):
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()

        async def boot() -> None:
            from app.core.db import collect_documents, import_services, init_db

            import_services()
            await init_db(collect_documents())

        _loop.run_until_complete(boot())
    return _loop.run_until_complete(coro)


@celery_app.task(name="hris.approval_reminders")
def approval_reminders() -> int:
    from app.shared.approvals import escalate_overdue

    return run_async(escalate_overdue())


@celery_app.task(name="hris.attendance_nightly")
def attendance_nightly() -> None:
    async def _go() -> None:
        try:
            from app.modules.attendance.tasks import compute_open_days
        except Exception:
            return
        await compute_open_days()

    run_async(_go())


@celery_app.task(name="hris.leave_month")
def leave_month() -> None:
    async def _go() -> None:
        try:
            from app.modules.leave.tasks import run_monthly_accrual
        except Exception:
            return
        await run_monthly_accrual()

    run_async(_go())


@celery_app.task(name="hris.reminders")
def reminders() -> None:
    async def _go() -> None:
        try:
            from app.modules.comms.tasks import send_scheduled_reminders
        except Exception:
            return
        await send_scheduled_reminders()

    run_async(_go())


@celery_app.task(name="hris.retention")
def retention() -> None:
    async def _go() -> None:
        try:
            from app.modules.privacy.tasks import apply_retention
        except Exception:
            return
        await apply_retention()

    run_async(_go())


@celery_app.task(name="hris.deactivate_separated")
def deactivate_separated() -> None:
    async def _go() -> None:
        try:
            from app.modules.offboarding.tasks import deactivate_due_users
        except Exception:
            return
        await deactivate_due_users()

    run_async(_go())


@celery_app.task(name="hris.payroll_compute")
def payroll_compute(run_id: str) -> None:
    async def _go() -> None:
        from app.modules.payroll.tasks import compute_run

        await compute_run(run_id)

    run_async(_go())
