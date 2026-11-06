from __future__ import annotations

from pydantic import BaseModel


class ReportFilters(BaseModel):
    department_id: str | None = None
    year: int | None = None
    status: str | None = None
    employee_id: str | None = None
