from __future__ import annotations

import logging

from app.core.clock import utcnow
from app.modules.comms.policies import is_birthday, is_hr_role, within_next_days
from app.modules.organization.models import Company

logger = logging.getLogger(__name__)


async def send_scheduled_reminders() -> None:
    try:
        await _send()
    except Exception:
        logger.exception("scheduled reminders failed")


async def _send() -> None:
    from app.modules.employees.models import Employee
    from app.modules.identity.models import Role, User
    from app.shared.notify import notify

    today = utcnow().date()
    companies = await Company.find({"deleted_at": None, "is_active": True}).to_list()
    for company in companies:
        company_key = str(company.id)
        try:
            roles = await Role.find({"company_id": company_key}).to_list()
            role_ids = [str(role.id) for role in roles if is_hr_role(role.name)]
            if not role_ids:
                continue
            users = await User.find(
                {"company_id": company_key, "is_active": True, "role_ids": {"$in": role_ids}}
            ).to_list()
            if not users:
                continue
            employees = await Employee.find(
                {"company_id": company_key, "deleted_at": None}
            ).to_list()
            for employee in employees:
                notes: list[tuple[str, str, str]] = []
                name = employee.name.full_name or employee.employee_no
                if is_birthday(employee.birth_date, today):
                    notes.append(
                        ("birthday.today", "Birthday today", f"{name} has a birthday today.")
                    )
                if within_next_days(employee.probation_end_date, today, 7):
                    end = employee.probation_end_date
                    when = end.isoformat() if end else ""
                    notes.append(
                        ("probation.ending", "Probation ending", f"{name} probation ends {when}.")
                    )
                for event_key, title, body in notes:
                    for user in users:
                        try:
                            await notify(
                                company_id=company_key,
                                user_id=str(user.id),
                                event_key=event_key,
                                title=title,
                                body=body,
                                email=user.email,
                            )
                        except Exception:
                            logger.info("reminder skipped for company %s", company_key)
        except Exception:
            logger.info("reminders skipped for company %s", company_key)
