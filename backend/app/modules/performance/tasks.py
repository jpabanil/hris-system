from __future__ import annotations

from app.core.clock import utcnow
from app.modules.employees.models import Employee
from app.modules.organization.models import Company
from app.modules.performance.policies import due_within


async def probation_reminders() -> list[str]:
    """Employees whose probation ends within the next 14 days."""
    today = utcnow().date()
    found: list[str] = []
    companies = await Company.find({"deleted_at": None, "is_active": True}).to_list()
    for company in companies:
        employees = await Employee.find(
            {
                "company_id": str(company.id),
                "deleted_at": None,
                "probation_end_date": {"$ne": None},
            }
        ).to_list()
        for employee in employees:
            if due_within(employee.probation_end_date, today, 14):
                found.append(str(employee.id))
    return found
