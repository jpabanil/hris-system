from __future__ import annotations

from app.core.clock import utcnow
from app.modules.organization.models import Company


async def deactivate_due_users() -> None:
    from app.modules.employees.models import Employee
    from app.modules.identity.models import User

    today = utcnow().date()
    companies = await Company.find({"deleted_at": None}).to_list()
    for company in companies:
        company_key = str(company.id)
        employees = await Employee.find(
            {
                "company_id": company_key,
                "deleted_at": None,
                "separation_date": {"$ne": None},
            }
        ).to_list()
        for employee in employees:
            if employee.separation_date is None or employee.separation_date > today:
                continue
            if not employee.user_id:
                continue
            user = await User.get(employee.user_id)
            if user is None or not user.is_active:
                continue
            if user.company_id and user.company_id != company_key:
                continue
            user.is_active = False
            user.updated_at = utcnow()
            await user.save()
