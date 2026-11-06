"""Payroll HTTP routes. Mounted at /api/v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.payroll.schemas import (
    AdjustmentWrite,
    ContributionTableWrite,
    LoanWrite,
    PayGroupWrite,
    PayrollPeriodWrite,
    RecurringDeductionWrite,
    TaxTableWrite,
)
from app.modules.payroll.service import (
    approve_period,
    bank_file_csv,
    compute_period,
    create_adjustment,
    create_contribution_table,
    create_loan,
    create_pay_group,
    create_period,
    create_recurring,
    create_tax_table,
    delete_adjustment,
    delete_loan,
    delete_pay_group,
    delete_period,
    delete_recurring,
    get_loan,
    get_pay_group,
    get_period,
    journal_report,
    list_adjustments,
    list_contribution_tables,
    list_loans,
    list_pay_groups,
    list_payslips,
    list_periods,
    list_recurring,
    list_tax_tables,
    lock_period,
    payslip_pdf_bytes,
    progress_report,
    register_report,
    release_period,
    submit_period,
    update_adjustment,
    update_contribution_table,
    update_loan,
    update_pay_group,
    update_period,
    update_recurring,
    update_tax_table,
    variance_report,
)

router = APIRouter(tags=["payroll"])


@router.get("/pay-groups")
async def pay_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_pay_groups(actor, page, page_size, q)


@router.post("/pay-groups", status_code=201)
async def pay_groups_create(
    body: PayGroupWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await create_pay_group(actor, body)


@router.get("/pay-groups/{group_id}")
async def pay_groups_get(group_id: str, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await get_pay_group(actor, group_id)


@router.put("/pay-groups/{group_id}")
async def pay_groups_update(
    group_id: str, body: PayGroupWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await update_pay_group(actor, group_id, body)


@router.delete("/pay-groups/{group_id}", status_code=204)
async def pay_groups_delete(
    group_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> Response:
    await delete_pay_group(actor, group_id)
    return Response(status_code=204)


@router.get("/payroll-periods")
async def payroll_periods(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    pay_group_id: str | None = None,
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_periods(actor, page, page_size, q, pay_group_id)


@router.post("/payroll-periods", status_code=201)
async def payroll_periods_create(
    body: PayrollPeriodWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await create_period(actor, body)


@router.get("/payroll-periods/{period_id}")
async def payroll_periods_get(
    period_id: str, actor: Actor = Depends(require("payroll.view"))
) -> dict:
    return await get_period(actor, period_id)


@router.put("/payroll-periods/{period_id}")
async def payroll_periods_update(
    period_id: str, body: PayrollPeriodWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await update_period(actor, period_id, body)


@router.delete("/payroll-periods/{period_id}", status_code=204)
async def payroll_periods_delete(
    period_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> Response:
    await delete_period(actor, period_id)
    return Response(status_code=204)


@router.post("/payroll-periods/{period_id}/compute")
async def payroll_compute(
    period_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await compute_period(actor, period_id)


@router.post("/payroll-periods/{period_id}/submit")
async def payroll_submit(
    period_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await submit_period(actor, period_id)


@router.post("/payroll-periods/{period_id}/approve")
async def payroll_approve(
    period_id: str, actor: Actor = Depends(require("payroll.approve"))
) -> dict:
    return await approve_period(actor, period_id)


@router.post("/payroll-periods/{period_id}/release")
async def payroll_release(
    period_id: str, actor: Actor = Depends(require("payroll.approve"))
) -> dict:
    return await release_period(actor, period_id)


@router.post("/payroll-periods/{period_id}/lock")
async def payroll_lock(
    period_id: str, actor: Actor = Depends(require("payroll.approve"))
) -> dict:
    return await lock_period(actor, period_id)


@router.get("/payroll-periods/{period_id}/payslips")
async def payroll_payslips(period_id: str, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await list_payslips(actor, period_id)


@router.get("/payroll-periods/{period_id}/variance")
async def payroll_variance(period_id: str, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await variance_report(actor, period_id)


@router.get("/payroll-periods/{period_id}/register")
async def payroll_register(period_id: str, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await register_report(actor, period_id)


@router.get("/payroll-periods/{period_id}/bank-file")
async def payroll_bank_file(
    period_id: str, actor: Actor = Depends(require("payroll.view"))
) -> Response:
    text = await bank_file_csv(actor, period_id)
    return Response(content=text, media_type="text/csv")


@router.get("/payroll-periods/{period_id}/journal")
async def payroll_journal(period_id: str, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await journal_report(actor, period_id)


@router.get("/payroll-periods/{period_id}/progress")
async def payroll_progress(period_id: str, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await progress_report(actor, period_id)


@router.get("/payslips/{payslip_id}/pdf")
async def payslip_pdf(payslip_id: str, actor: Actor = Depends(get_actor)) -> Response:
    payload = await payslip_pdf_bytes(actor, payslip_id)
    return Response(content=payload, media_type="application/pdf")


@router.get("/loans")
async def loans(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    employee_id: str | None = None,
    status: str | None = None,
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_loans(actor, page, page_size, q, employee_id, status)


@router.post("/loans", status_code=201)
async def loans_create(
    body: LoanWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await create_loan(actor, body)


@router.get("/loans/{loan_id}")
async def loans_get(loan_id: str, actor: Actor = Depends(require("payroll.view"))) -> dict:
    return await get_loan(actor, loan_id)


@router.put("/loans/{loan_id}")
async def loans_update(
    loan_id: str, body: LoanWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await update_loan(actor, loan_id, body)


@router.delete("/loans/{loan_id}", status_code=204)
async def loans_delete(
    loan_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> Response:
    await delete_loan(actor, loan_id)
    return Response(status_code=204)


@router.get("/recurring-deductions")
async def recurring(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    employee_id: str | None = None,
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_recurring(actor, page, page_size, q, employee_id)


@router.post("/recurring-deductions", status_code=201)
async def recurring_create(
    body: RecurringDeductionWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await create_recurring(actor, body)


@router.put("/recurring-deductions/{deduction_id}")
async def recurring_update(
    deduction_id: str,
    body: RecurringDeductionWrite,
    actor: Actor = Depends(require("payroll.compute")),
) -> dict:
    return await update_recurring(actor, deduction_id, body)


@router.delete("/recurring-deductions/{deduction_id}", status_code=204)
async def recurring_delete(
    deduction_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> Response:
    await delete_recurring(actor, deduction_id)
    return Response(status_code=204)


@router.get("/adjustments")
async def adjustments(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    period_id: str | None = None,
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_adjustments(actor, page, page_size, q, period_id)


@router.post("/adjustments", status_code=201)
async def adjustments_create(
    body: AdjustmentWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await create_adjustment(actor, body)


@router.put("/adjustments/{adjustment_id}")
async def adjustments_update(
    adjustment_id: str, body: AdjustmentWrite, actor: Actor = Depends(require("payroll.compute"))
) -> dict:
    return await update_adjustment(actor, adjustment_id, body)


@router.delete("/adjustments/{adjustment_id}", status_code=204)
async def adjustments_delete(
    adjustment_id: str, actor: Actor = Depends(require("payroll.compute"))
) -> Response:
    await delete_adjustment(actor, adjustment_id)
    return Response(status_code=204)


@router.get("/contribution-tables")
async def contribution_tables(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_contribution_tables(actor, page, page_size)


@router.post("/contribution-tables", status_code=201)
async def contribution_tables_create(
    body: ContributionTableWrite, actor: Actor = Depends(require("payroll.tables"))
) -> dict:
    return await create_contribution_table(actor, body)


@router.put("/contribution-tables/{table_id}")
async def contribution_tables_update(
    table_id: str, body: ContributionTableWrite, actor: Actor = Depends(require("payroll.tables"))
) -> dict:
    return await update_contribution_table(actor, table_id, body)


@router.get("/tax-tables")
async def tax_tables(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(require("payroll.view")),
) -> dict:
    return await list_tax_tables(actor, page, page_size)


@router.post("/tax-tables", status_code=201)
async def tax_tables_create(
    body: TaxTableWrite, actor: Actor = Depends(require("payroll.tables"))
) -> dict:
    return await create_tax_table(actor, body)


@router.put("/tax-tables/{table_id}")
async def tax_tables_update(
    table_id: str, body: TaxTableWrite, actor: Actor = Depends(require("payroll.tables"))
) -> dict:
    return await update_tax_table(actor, table_id, body)
