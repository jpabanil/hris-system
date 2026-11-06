"""Year-end tasks. HTTP calls the service directly; this is the worker entry."""

from __future__ import annotations


async def annualize_company(company_id: str, year: int, actor_id: str) -> dict:
    from app.core.actor import Actor
    from app.modules.compliance.service import annualize_year

    actor = Actor(
        user_id=actor_id,
        email="",
        company_id=company_id,
        permissions={"payroll.compute", "payroll.view"},
    )
    return await annualize_year(actor, year)
