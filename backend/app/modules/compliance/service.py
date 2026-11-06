"""Year-end tax, 2316 data sheets, alphalist, remittances, and 13th month."""

from __future__ import annotations

import io
from collections import defaultdict
from datetime import date
from decimal import Decimal
from html import escape

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.money import D, money, money_str
from app.core.repository import TenantRepo, api
from app.domain.annualization import (
    TaxBracket,
    annualize,
    thirteenth_month,
    thirteenth_month_taxable_excess,
)
from app.modules.compliance import policies
from app.modules.compliance.models import (
    AlphalistExport,
    Bir2316,
    Remittance,
    TaxAnnualization,
    ThirteenthMonthLine,
    ThirteenthMonthRun,
)
from app.modules.compliance.schemas import RemittanceWrite
from app.modules.employees.models import Employee, EmployeeSensitive
from app.modules.payroll.models import (
    PayrollPeriod,
    PayrollRun,
    Payslip,
    PreviousEmployerIncome,
    TaxTable,
    YtdOpening,
)
from app.shared.settings_store import PayrollSettings, get_settings_model

_AGENCIES = {"sss", "philhealth", "pagibig"}


def _parse_month(value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2 or len(parts[0]) != 4:
        raise AppError("bad_month", "Month must be YYYY-MM", 400)
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError as exc:
        raise AppError("bad_month", "Month must be YYYY-MM", 400) from exc
    if month < 1 or month > 12:
        raise AppError("bad_month", "Month must be YYYY-MM", 400)
    return year, month


def _agency(value: str) -> str:
    agency = value.lower()
    if agency not in _AGENCIES:
        raise AppError("bad_agency", "Agency must be sss, philhealth, or pagibig", 400)
    return agency


async def _settings(company_id: str) -> PayrollSettings:
    loaded = await get_settings_model(company_id, "payroll")
    if isinstance(loaded, PayrollSettings):
        return loaded
    return PayrollSettings.model_validate(loaded.model_dump())


async def _annual_table(company_id: str, year: int) -> TaxTable:
    as_of = date(year, 12, 31)
    rows = await TaxTable.find({"company_id": company_id, "frequency": "annual"}).to_list()
    chosen = [row for row in rows if row.effective_from <= as_of]
    if not chosen:
        raise AppError("tax_table_missing", "Annual tax table is missing", 400)
    chosen.sort(key=lambda row: row.effective_from, reverse=True)
    table = chosen[0]
    if not table.brackets:
        raise AppError("tax_table_missing", "Annual tax table has no brackets", 400)
    return table


def _brackets(table: TaxTable) -> tuple[TaxBracket, ...]:
    return tuple(
        TaxBracket(start=D(row.start), base_tax=D(row.base_tax), rate=D(row.rate))
        for row in table.brackets
    )


async def _latest_runs(company_id: str, period_ids: list[str]) -> dict[str, PayrollRun]:
    if not period_ids:
        return {}
    runs = await PayrollRun.find(
        {"company_id": company_id, "period_id": {"$in": period_ids}}
    ).to_list()
    chosen: dict[str, PayrollRun] = {}
    for run in runs:
        current = chosen.get(run.period_id)
        if current is None or run.version > current.version:
            chosen[run.period_id] = run
    return chosen


async def _year_context(company_id: str, year: int) -> dict:
    periods = await PayrollPeriod.find({"company_id": company_id}).to_list()
    year_periods = [item for item in periods if item.end.year == year]
    runs = await _latest_runs(company_id, [str(item.id) for item in year_periods])
    slips: list[Payslip] = []
    if runs:
        slips = await Payslip.find(
            {"company_id": company_id, "run_id": {"$in": [str(item.id) for item in runs.values()]}}
        ).to_list()
    period_end = {str(item.id): item.end for item in year_periods}
    run_period = {str(run.id): run.period_id for run in runs.values()}
    latest: dict[str, Payslip] = {}
    latest_end: dict[str, date] = {}
    by_employee: dict[str, list[Payslip]] = defaultdict(list)
    for slip in slips:
        by_employee[slip.employee_id].append(slip)
        period_id = run_period.get(slip.run_id)
        end = period_end.get(period_id or "")
        if end is None:
            continue
        current = latest_end.get(slip.employee_id)
        if current is None or end >= current:
            latest[slip.employee_id] = slip
            latest_end[slip.employee_id] = end
    openings = {
        item.employee_id: item
        for item in await YtdOpening.find({"company_id": company_id, "year": year}).to_list()
    }
    previous = {
        item.employee_id: item
        for item in await PreviousEmployerIncome.find(
            {"company_id": company_id, "year": year}
        ).to_list()
    }
    employees = await Employee.find({"company_id": company_id, "deleted_at": None}).to_list()
    return {
        "employees": employees,
        "latest": latest,
        "by_employee": by_employee,
        "openings": openings,
        "previous": previous,
    }


def _bases(
    slip: Payslip | None,
    opening: YtdOpening | None,
    previous: PreviousEmployerIncome | None,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """YtdOpening is added when the payslip snapshot did not already fold it in."""
    taxable = Decimal("0")
    withheld = Decimal("0")
    if slip is not None and slip.ytd:
        taxable = D(slip.ytd.get("taxable") or 0)
        withheld = D(slip.ytd.get("tax_withheld") or 0)
    includes = bool(slip and (slip.snapshot or {}).get("includes_opening"))
    if opening is not None and not includes:
        taxable = money(taxable + D(opening.taxable))
        withheld = money(withheld + D(opening.tax_withheld))
    prev_tax = D(previous.taxable) if previous is not None else Decimal("0")
    prev_withheld = D(previous.tax_withheld) if previous is not None else Decimal("0")
    return taxable, withheld, prev_tax, prev_withheld


def _reveal(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if not value.startswith("v1:"):
        return value
    from app.core.encryption import decrypt

    try:
        return decrypt(value)
    except Exception:
        return ""


async def annualize_year(actor: Actor, year: int) -> dict:
    policies.require_compute(actor)
    company = policies.company_id(actor)
    table = await _annual_table(company, year)
    brackets = _brackets(table)
    context = await _year_context(company, year)
    saved: list[dict] = []
    for employee in context["employees"]:
        emp_id = str(employee.id)
        taxable, withheld, prev_tax, prev_withheld = _bases(
            context["latest"].get(emp_id),
            context["openings"].get(emp_id),
            context["previous"].get(emp_id),
        )
        result = annualize(
            ytd_taxable=taxable,
            previous_employer_taxable=prev_tax,
            ytd_withheld=withheld,
            previous_employer_withheld=prev_withheld,
            brackets=brackets,
        )
        existing = await TaxAnnualization.find_one(
            {"company_id": company, "employee_id": emp_id, "year": year}
        )
        if existing is None:
            existing = TaxAnnualization(
                company_id=company,
                employee_id=emp_id,
                year=year,
                annual_taxable=result.annual_taxable,
                annual_tax_due=result.annual_tax_due,
                total_withheld=result.total_withheld,
                refund_or_payable=result.refund_or_payable,
                created_by=actor.user_id,
                updated_by=actor.user_id,
            )
            await existing.insert()
        else:
            existing.annual_taxable = result.annual_taxable
            existing.annual_tax_due = result.annual_tax_due
            existing.total_withheld = result.total_withheld
            existing.refund_or_payable = result.refund_or_payable
            existing.updated_at = utcnow()
            existing.updated_by = actor.user_id
            await existing.save()
        saved.append(api(existing))
    return {"year": year, "items": saved, "total": len(saved)}


def _sheet_html(employee: Employee, year: int, data: dict[str, str]) -> str:
    rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"
        for label, value in data.items()
    )
    return (
        "<html><body>"
        "<h1>Compensation data sheet</h1>"
        "<p>Source data for BIR Form 2316. This is not a copy of the official form.</p>"
        f"<p>{escape(employee.name.full_name)} ({escape(employee.employee_no)})</p>"
        f"<p>Year {year}</p><table>{rows}</table></body></html>"
    )


async def generate_2316(actor: Actor, year: int) -> dict:
    policies.require_view(actor)
    company = policies.company_id(actor)
    context = await _year_context(company, year)
    stored = {
        item.employee_id: item
        for item in await TaxAnnualization.find({"company_id": company, "year": year}).to_list()
    }
    sensitive = {
        item.employee_id: item
        for item in await EmployeeSensitive.find({"company_id": company}).to_list()
    }
    brackets = None
    if any(str(item.id) not in stored for item in context["employees"]):
        brackets = _brackets(await _annual_table(company, year))
    from app.shared import documents, files

    items = []
    for employee in context["employees"]:
        emp_id = str(employee.id)
        record = stored.get(emp_id)
        if record is None:
            assert brackets is not None
            taxable, withheld, prev_tax, prev_withheld = _bases(
                context["latest"].get(emp_id),
                context["openings"].get(emp_id),
                context["previous"].get(emp_id),
            )
            result = annualize(
                ytd_taxable=taxable,
                previous_employer_taxable=prev_tax,
                ytd_withheld=withheld,
                previous_employer_withheld=prev_withheld,
                brackets=brackets,
            )
            figures = {
                "annual_taxable": money_str(result.annual_taxable),
                "annual_tax_due": money_str(result.annual_tax_due),
                "total_withheld": money_str(result.total_withheld),
                "refund_or_payable": money_str(result.refund_or_payable),
            }
        else:
            figures = {
                "annual_taxable": money_str(record.annual_taxable),
                "annual_tax_due": money_str(record.annual_tax_due),
                "total_withheld": money_str(record.total_withheld),
                "refund_or_payable": money_str(record.refund_or_payable),
            }
        tin_row = sensitive.get(emp_id)
        tin = _reveal(tin_row.tin) if tin_row else ""
        data = {"tin": tin, "employee_no": employee.employee_no, **figures}
        pdf = documents.html_to_pdf(_sheet_html(employee, year, data))
        uploaded = await files.save_upload(
            actor,
            filename=f"2316-{employee.employee_no}-{year}.pdf",
            content_type="application/pdf",
            data=pdf,
            confidential=True,
        )
        existing = await Bir2316.find_one(
            {"company_id": company, "employee_id": emp_id, "year": year}
        )
        if existing is None:
            existing = Bir2316(
                company_id=company,
                employee_id=emp_id,
                year=year,
                data=data,
                file_key=uploaded.key,
                created_by=actor.user_id,
                updated_by=actor.user_id,
            )
            await existing.insert()
        else:
            existing.data = data
            existing.file_key = uploaded.key
            existing.updated_at = utcnow()
            existing.updated_by = actor.user_id
            await existing.save()
        items.append({"employee_id": emp_id, "file_key": uploaded.key, "id": str(existing.id)})
    return {"year": year, "items": items, "total": len(items)}


async def _alphalist_rows(actor: Actor, year: int) -> list[dict[str, str]]:
    company = policies.company_id(actor)
    context = await _year_context(company, year)
    stored = {
        item.employee_id: item
        for item in await TaxAnnualization.find({"company_id": company, "year": year}).to_list()
    }
    sensitive = {
        item.employee_id: item
        for item in await EmployeeSensitive.find({"company_id": company}).to_list()
    }
    brackets = None
    rows: list[dict[str, str]] = []
    for employee in sorted(context["employees"], key=lambda item: item.name.last):
        emp_id = str(employee.id)
        record = stored.get(emp_id)
        if record is None:
            if brackets is None:
                brackets = _brackets(await _annual_table(company, year))
            taxable, withheld, prev_tax, prev_withheld = _bases(
                context["latest"].get(emp_id),
                context["openings"].get(emp_id),
                context["previous"].get(emp_id),
            )
            result = annualize(
                ytd_taxable=taxable,
                previous_employer_taxable=prev_tax,
                ytd_withheld=withheld,
                previous_employer_withheld=prev_withheld,
                brackets=brackets,
            )
            annual_taxable = money_str(result.annual_taxable)
            annual_tax_due = money_str(result.annual_tax_due)
            total_withheld = money_str(result.total_withheld)
            refund = money_str(result.refund_or_payable)
        else:
            annual_taxable = money_str(record.annual_taxable)
            annual_tax_due = money_str(record.annual_tax_due)
            total_withheld = money_str(record.total_withheld)
            refund = money_str(record.refund_or_payable)
        tin_row = sensitive.get(emp_id)
        rows.append(
            {
                "employee_id": emp_id,
                "employee_no": employee.employee_no,
                "name": employee.name.full_name,
                "tin": _reveal(tin_row.tin) if tin_row else "",
                "annual_taxable": annual_taxable,
                "annual_tax_due": annual_tax_due,
                "total_withheld": total_withheld,
                "refund_or_payable": refund,
            }
        )
    return rows


async def alphalist(actor: Actor, year: int, export_format: str) -> dict:
    policies.require_view(actor)
    rows = await _alphalist_rows(actor, year)
    body: dict = {"year": year, "rows": rows, "total": len(rows)}
    if export_format != "xlsx":
        return body
    from openpyxl import Workbook  # type: ignore[import-untyped]

    from app.shared import files

    book = Workbook()
    sheet = book.active
    sheet.title = "Alphalist"
    headers = [
        "employee_no",
        "name",
        "tin",
        "annual_taxable",
        "annual_tax_due",
        "total_withheld",
        "refund_or_payable",
    ]
    sheet.append(headers)
    for row in rows:
        sheet.append([row[key] for key in headers])
    buffer = io.BytesIO()
    book.save(buffer)
    uploaded = await files.save_upload(
        actor,
        filename=f"alphalist-{year}.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        data=buffer.getvalue(),
        confidential=True,
    )
    export = AlphalistExport(
        company_id=policies.company_id(actor),
        year=year,
        type="annual",
        file_key=uploaded.key,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await export.insert()
    body["file_key"] = uploaded.key
    body["export_id"] = str(export.id)
    return body


async def list_remittances(actor: Actor, page: int, page_size: int) -> dict:
    policies.require_view(actor)
    return await TenantRepo(Remittance, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("agency", "month", "reference_no"),
        sort_fields={"created_at", "month", "agency"},
        q=None,
        sort="-month",
    )


async def create_remittance(actor: Actor, body: RemittanceWrite) -> dict:
    policies.require_compute(actor)
    agency = _agency(body.agency)
    _parse_month(body.month)
    company = policies.company_id(actor)
    existing = await Remittance.find_one(
        {"company_id": company, "agency": agency, "month": body.month}
    )
    if existing is not None:
        raise AppError("conflict", "A remittance for this agency and month already exists", 409)
    doc = Remittance(
        company_id=company,
        agency=agency,
        month=body.month,
        ee_total=money(body.ee_total),
        er_total=money(body.er_total),
        reference_no=body.reference_no,
        paid_at=body.paid_at,
        proof_key=body.proof_key,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await doc.insert()
    return api(doc)


async def get_remittance(actor: Actor, remittance_id: str) -> dict:
    policies.require_view(actor)
    return api(await TenantRepo(Remittance, actor).get(remittance_id))


async def update_remittance(actor: Actor, remittance_id: str, body: RemittanceWrite) -> dict:
    policies.require_compute(actor)
    agency = _agency(body.agency)
    _parse_month(body.month)
    doc = await TenantRepo(Remittance, actor).get(remittance_id)
    if not isinstance(doc, Remittance):
        raise AppError("not_found", "Remittance not found", 404)
    company = policies.company_id(actor)
    clash = await Remittance.find_one(
        {"company_id": company, "agency": agency, "month": body.month}
    )
    if clash is not None and str(clash.id) != str(doc.id):
        raise AppError("conflict", "A remittance for this agency and month already exists", 409)
    doc.agency = agency
    doc.month = body.month
    doc.ee_total = money(body.ee_total)
    doc.er_total = money(body.er_total)
    doc.reference_no = body.reference_no
    doc.paid_at = body.paid_at
    doc.proof_key = body.proof_key
    doc.updated_at = utcnow()
    doc.updated_by = actor.user_id
    await doc.save()
    return api(doc)


async def delete_remittance(actor: Actor, remittance_id: str) -> None:
    policies.require_compute(actor)
    doc = await TenantRepo(Remittance, actor).get(remittance_id)
    await doc.delete()


def _employer_share(snapshot: dict, agency: str) -> Decimal:
    block = snapshot.get(agency) if isinstance(snapshot, dict) else None
    if not isinstance(block, dict):
        return Decimal("0")
    er = D(block.get("er_period") or block.get("er") or 0)
    if agency == "sss":
        er += D(block.get("ec_period") or block.get("ec") or 0)
    return er


async def remittance_report(actor: Actor, agency: str, month: str) -> dict:
    policies.require_view(actor)
    agency = _agency(agency)
    year, month_n = _parse_month(month)
    company = policies.company_id(actor)
    periods = await PayrollPeriod.find({"company_id": company}).to_list()
    matched = [
        item
        for item in periods
        if item.pay_date.year == year and item.pay_date.month == month_n
    ]
    runs = await _latest_runs(company, [str(item.id) for item in matched])
    slips: list[Payslip] = []
    if runs:
        slips = await Payslip.find(
            {"company_id": company, "run_id": {"$in": [str(item.id) for item in runs.values()]}}
        ).to_list()
    ee = Decimal("0")
    er = Decimal("0")
    for slip in slips:
        for line in slip.lines:
            if line.code == agency and line.type == "deduction" and not line.deferred:
                ee += D(line.amount)
        er += _employer_share(slip.snapshot or {}, agency)
    return {
        "agency": agency,
        "month": f"{year:04d}-{month_n:02d}",
        "ee_total": money_str(money(ee)),
        "er_total": money_str(money(er)),
        "headcount": len({item.employee_id for item in slips}),
    }


async def compute_thirteenth(actor: Actor, year: int) -> dict:
    policies.require_compute(actor)
    company = policies.company_id(actor)
    settings = await _settings(company)
    ceiling = D(settings.thirteenth_month_nontax_ceiling)
    context = await _year_context(company, year)
    ids = {str(item.id) for item in context["employees"]}
    ids.update(context["by_employee"].keys())
    ids.update(context["openings"].keys())
    run = await ThirteenthMonthRun.find_one({"company_id": company, "year": year})
    if run is None:
        run = ThirteenthMonthRun(
            company_id=company,
            year=year,
            status="computed",
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await run.insert()
    else:
        old = await ThirteenthMonthLine.find(
            {"company_id": company, "run_id": str(run.id)}
        ).to_list()
        for line in old:
            await line.delete()
    total = Decimal("0")
    lines: list[dict] = []
    for emp_id in sorted(ids):
        slips = context["by_employee"].get(emp_id, [])
        opening = context["openings"].get(emp_id)
        if slips:
            earned = money(sum((D(item.basic_pay) for item in slips), Decimal("0")))
        else:
            earned = money(D(opening.basic) if opening is not None else 0)
        amount = thirteenth_month(earned)
        other = D(opening.thirteenth_and_other_benefits) if opening is not None else Decimal("0")
        excess = thirteenth_month_taxable_excess(money(D(amount) + other), ceiling)
        line = ThirteenthMonthLine(
            company_id=company,
            run_id=str(run.id),
            employee_id=emp_id,
            basic_earned=earned,
            amount=amount,
            taxable_excess=excess,
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await line.insert()
        total += D(amount)
        lines.append(api(line))
    run.total = money(total)
    run.status = "computed"
    run.computed_at = utcnow()
    run.updated_at = utcnow()
    run.updated_by = actor.user_id
    await run.save()
    body = api(run)
    body["lines"] = lines
    return body
