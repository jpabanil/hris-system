from __future__ import annotations

from dateutil.relativedelta import relativedelta

from app.core.clock import utcnow
from app.modules.employees.models import Employee, PersonName
from app.modules.privacy.models import RetentionPolicy
from app.modules.privacy.policies import due_for_anonymization

_EMPLOYEE_TYPES = {"employee", "employees"}


async def apply_retention() -> None:
    today = utcnow().date()
    policies = await RetentionPolicy.find({"action": "anonymize"}).to_list()
    for policy in policies:
        if policy.record_type not in _EMPLOYEE_TYPES or not policy.company_id:
            continue
        if policy.retain_years < 0:
            continue
        cutoff = today - relativedelta(years=policy.retain_years)
        employees = await Employee.find(
            {
                "company_id": policy.company_id,
                "deleted_at": None,
                "employment_status": "separated",
                "separation_date": {"$ne": None},
            }
        ).to_list()
        for employee in employees:
            if not due_for_anonymization(employee.separation_date, cutoff):
                continue
            employee.name = PersonName(first="", last="")
            employee.contact = {}
            employee.present_address = ""
            employee.permanent_address = ""
            employee.updated_at = utcnow()
            await employee.save()
