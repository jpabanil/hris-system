"""Demo company for local development.

Password for every seeded user is ChangeMe123!.
Contribution rows follow the formulas in app.domain.contributions.
2026 nationwide holidays follow Proclamation No. 1006 (regular and special days).
Eid dates are omitted because that proclamation left them for a later issuance.
The Cebu fiesta row is sample data so city-scoped holidays can be tried.
Confirm every table against the current agency circular before a real payroll.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.clock import utcnow
from app.core.encryption import encrypt
from app.core.money import money
from app.core.permissions import ROLE_PERMISSIONS
from app.core.security import hash_password
from app.domain.annualization import TaxBracket
from app.domain.contributions import pagibig_amount, philhealth_amount, sss_amount
from app.domain.payroll_engine import PayrollInput, Ytd, compute_payroll
from app.modules.assets.models import Asset, AssetAssignment, AssetCategory
from app.modules.attendance.models import (
    AttendanceDay,
    EmployeeSchedule,
    Holiday,
    Shift,
    WorkSchedule,
)
from app.modules.benefits.models import BenefitEnrollment, BenefitPlan
from app.modules.claims.models import CashAdvance, Claim, ClaimType
from app.modules.employee_relations.models import DisciplinaryCase, Offense
from app.modules.employees.models import (
    CompensationHistory,
    CompensationSnapshot,
    Employee,
    EmployeeSensitive,
    PersonName,
)
from app.modules.identity.models import Role, User
from app.modules.leave.models import LeaveBalance, LeaveLedger, LeaveRequest, LeaveType
from app.modules.offboarding.models import Clearance, ClearanceItem, FinalPay, Resignation
from app.modules.organization.models import (
    Branch,
    Company,
    CostCenter,
    Department,
    Position,
    SalaryGrade,
)
from app.modules.payroll.models import (
    ContributionBracket,
    ContributionTable,
    Loan,
    PayGroup,
    PayrollPeriod,
    PayrollRun,
    Payslip,
    PayslipLine,
    RecurringDeduction,
    TaxBracketRow,
    TaxTable,
)
from app.modules.recruitment.models import Applicant, JobOpening, ManpowerRequisition
from app.shared.models import ApprovalFlow, Counter, FlowStep, SettingDoc
from app.shared.settings_store import SCHEMAS

PASSWORD = "ChangeMe123!"
SLUG = "demo"

FIRST = (
    "Juan", "Maria", "Jose", "Ana", "Pedro", "Rosa", "Luis", "Carmen", "Andres", "Liza",
    "Mark", "Grace", "Paolo", "Elena", "Rafael", "Sofia", "Diego", "Isabel", "Miguel", "Patricia",
    "Carlo", "Bea", "Nico", "Andrea", "Gabriel", "Katrina", "Emilio", "Diana", "Hector", "Julia",
    "Ramon", "Teresa", "Felix", "Nora", "Oscar", "Helen", "Victor", "Irene", "Samuel", "Lourdes",
    "Benjamin", "Cynthia", "Eduardo", "Maricel", "Fernando", "Rowena", "Antonio", "Glenda", "Ricardo", "Fe",
)
LAST = (
    "Santos", "Reyes", "Cruz", "Bautista", "Garcia", "Mendoza", "Torres", "Flores", "Gonzales", "Ramos",
    "Villanueva", "Castro", "Domingo", "Aquino", "Navarro", "Del Rosario", "Salazar", "Pascual", "Fernandez", "Lim",
    "Tan", "Uy", "Chua", "Ocampo", "Diaz", "Morales", "Santiago", "Gutierrez", "Castillo", "Romero",
    "Aguilar", "Herrera", "Medina", "Cabrera", "Vargas", "Silva", "Ortega", "Jimenez", "Ruiz", "Alvarez",
    "Molina", "Delgado", "Vega", "Campos", "Fuentes", "Cortes", "Guerrero", "Nuñez", "Ibarra", "Padilla",
)

DEPTS = (
    ("Executive", "EXE"),
    ("Human Resources", "HR"),
    ("Finance", "FIN"),
    ("Operations", "OPS"),
    ("Sales", "SAL"),
    ("Engineering", "ENG"),
)
POSITIONS = (
    "Chief Executive Officer",
    "HR Manager",
    "HR Officer",
    "Payroll Officer",
    "Accountant",
    "Finance Manager",
    "Operations Manager",
    "Operations Supervisor",
    "Sales Manager",
    "Account Executive",
    "Engineering Manager",
    "Software Engineer",
    "Support Engineer",
    "Recruiter",
    "Office Administrator",
)
ROLES = (
    ("super@demo.example.com", "Super Admin", True),
    ("hr.admin@demo.example.com", "HR Admin", False),
    ("hr.staff@demo.example.com", "HR Staff", False),
    ("payroll@demo.example.com", "Payroll Officer", False),
    ("approver@demo.example.com", "Payroll Approver", False),
    ("finance@demo.example.com", "Finance", False),
    ("manager@demo.example.com", "Department Manager", False),
    ("recruiter@demo.example.com", "Recruiter", False),
    ("employee@demo.example.com", "Employee", False),
    ("auditor@demo.example.com", "Auditor", False),
)
LEAVE_STATUSES = ("pending", "approved", "rejected", "cancelled", "returned")
STAGES = ("applied", "screening", "interview", "offer", "hired", "rejected")
MONTHLY_TAX = (
    ("0", "0", "0"),
    ("20833.33", "0", "0.15"),
    ("33333.33", "1875.00", "0.20"),
    ("66666.67", "8541.67", "0.25"),
    ("166666.67", "33541.67", "0.30"),
    ("666666.67", "183541.67", "0.35"),
)
ANNUAL_TAX = (
    ("0", "0", "0"),
    ("250000", "0", "0.15"),
    ("400000", "22500", "0.20"),
    ("800000", "102500", "0.25"),
    ("2000000", "402500", "0.30"),
    ("8000000", "2202500", "0.35"),
)
HOLIDAYS = (
    (date(2026, 1, 1), "New Year's Day", "regular", "nationwide", ()),
    (date(2026, 2, 17), "Chinese New Year", "special", "nationwide", ()),
    (date(2026, 4, 2), "Maundy Thursday", "regular", "nationwide", ()),
    (date(2026, 4, 3), "Good Friday", "regular", "nationwide", ()),
    (date(2026, 4, 4), "Black Saturday", "special", "nationwide", ()),
    (date(2026, 4, 9), "Araw ng Kagitingan", "regular", "nationwide", ()),
    (date(2026, 5, 1), "Labor Day", "regular", "nationwide", ()),
    (date(2026, 6, 12), "Independence Day", "regular", "nationwide", ()),
    (date(2026, 8, 21), "Ninoy Aquino Day", "special", "nationwide", ()),
    (date(2026, 8, 31), "National Heroes Day", "regular", "nationwide", ()),
    (date(2026, 10, 16), "Cebu sample fiesta", "special", "city", ("Cebu City",)),
    (date(2026, 11, 1), "All Saints' Day", "special", "nationwide", ()),
    (date(2026, 11, 2), "All Souls' Day", "special", "nationwide", ()),
    (date(2026, 11, 30), "Bonifacio Day", "regular", "nationwide", ()),
    (date(2026, 12, 8), "Feast of the Immaculate Conception", "special", "nationwide", ()),
    (date(2026, 12, 24), "Christmas Eve", "special", "nationwide", ()),
    (date(2026, 12, 25), "Christmas Day", "regular", "nationwide", ()),
    (date(2026, 12, 30), "Rizal Day", "regular", "nationwide", ()),
    (date(2026, 12, 31), "Last Day of the Year", "special", "nationwide", ()),
)
MODULES = (
    "leave",
    "overtime",
    "attendance_correction",
    "profile_update",
    "claims",
    "payroll",
    "recruitment",
    "offboarding",
)


def _rates(basic: str, basis: str) -> tuple[Decimal, Decimal, Decimal]:
    amount = money(basic)
    if basis == "daily":
        daily = amount
        hourly = money(daily / Decimal(8))
        return daily * Decimal(22), daily, hourly
    daily = money(amount * Decimal(12) / Decimal(261))
    hourly = money(daily / Decimal(8))
    return amount, daily, hourly


def _weekdays(year: int, month: int) -> list[date]:
    found: list[date] = []
    for day in calendar.Calendar().itermonthdates(year, month):
        if day.month == month and day.weekday() < 5:
            found.append(day)
    return found


def _brackets(agency: str) -> list[ContributionBracket]:
    rows: list[ContributionBracket] = []
    if agency == "sss":
        edges = [Decimal("0"), Decimal("5250")]
        cursor = Decimal("5250")
        while cursor < Decimal("34750"):
            edges.append(cursor + Decimal("500"))
            cursor += Decimal("500")
        edges.append(Decimal("1000000"))
        for start, end in zip(edges, edges[1:], strict=False):
            sample = start if start > 0 else Decimal("4000")
            amount = sss_amount(sample)
            rows.append(
                ContributionBracket(
                    range_from=start,
                    range_to=end - Decimal("0.01"),
                    ee=amount.ee,
                    er=amount.er,
                    ec=amount.ec,
                    mpf=amount.mpf,
                    mpf_er=amount.mpf_er,
                )
            )
        return rows
    step = Decimal("100")
    limit = Decimal("100000") if agency == "philhealth" else Decimal("10000")
    start = Decimal("0")
    while start < limit:
        end = start + step
        sample = end - Decimal("0.01")
        amount = philhealth_amount(sample) if agency == "philhealth" else pagibig_amount(sample)
        rows.append(
            ContributionBracket(
                range_from=start,
                range_to=end - Decimal("0.01"),
                ee=amount.ee,
                er=amount.er,
                ec=amount.ec,
            )
        )
        start = end
    ceiling = philhealth_amount(Decimal("150000")) if agency == "philhealth" else pagibig_amount(Decimal("80000"))
    rows.append(
        ContributionBracket(
            range_from=limit,
            range_to="9999999",
            ee=ceiling.ee,
            er=ceiling.er,
            ec=ceiling.ec,
        )
    )
    return rows


async def seed() -> None:
    if await Company.find_one(Company.slug == SLUG):
        print("demo company already loaded")
        return
    company = Company(
        name="Demo Trading Co.",
        slug=SLUG,
        trade_name="Demo Trading",
        tin="000-000-000-000",
        address="Ayala Avenue, Makati",
        timezone="Asia/Manila",
    )
    await company.insert()
    cid = str(company.id)
    manila = Branch(company_id=cid, name="Manila", city="Makati", region="NCR", address="Ayala Avenue")
    cebu = Branch(company_id=cid, name="Cebu", city="Cebu City", region="Central Visayas", address="IT Park")
    await manila.insert()
    await cebu.insert()
    centers = []
    departments = []
    for name, code in DEPTS:
        center = CostCenter(company_id=cid, code=code, name=name)
        await center.insert()
        centers.append(center)
        department = Department(company_id=cid, name=name, code=code, cost_center_id=str(center.id))
        await department.insert()
        departments.append(department)
    grades = []
    for index, low in enumerate(("20000", "30000", "45000", "70000", "100000"), start=1):
        grade = SalaryGrade(
            company_id=cid,
            code=f"SG{index}",
            min_salary=low,
            mid_salary=money(Decimal(low) * Decimal("1.2")),
            max_salary=money(Decimal(low) * Decimal("1.5")),
        )
        await grade.insert()
        grades.append(grade)
    positions = []
    for index, title in enumerate(POSITIONS):
        position = Position(
            company_id=cid,
            title=title,
            department_id=str(departments[min(index // 3, 5)].id),
            salary_grade_id=str(grades[min(index // 3, 4)].id),
            is_supervisory=index in {0, 1, 5, 6, 8, 10},
        )
        await position.insert()
        positions.append(position)
    pay_group = PayGroup(company_id=cid, name="Monthly", frequency="monthly")
    await pay_group.insert()
    day_group = PayGroup(company_id=cid, name="Daily", frequency="monthly")
    await day_group.insert()
    password_hash = hash_password(PASSWORD)
    users: dict[str, User] = {}
    for email, role_name, superadmin in ROLES:
        role = Role(
            company_id=cid,
            name=role_name,
            permission_keys=sorted(ROLE_PERMISSIONS[role_name]),
        )
        await role.insert()
        user = User(
            email=email,
            password_hash=password_hash,
            company_id=cid,
            role_ids=[str(role.id)],
            is_superadmin=superadmin,
        )
        await user.insert()
        users[role_name] = user
    day_shift = WorkSchedule(
        company_id=cid, name="Day 8-5", time_in="08:00", time_out="17:00", required_hours="8"
    )
    night_shift = WorkSchedule(
        company_id=cid,
        name="Night 10-6",
        time_in="22:00",
        time_out="06:00",
        is_night_shift=True,
        required_hours="8",
    )
    await day_shift.insert()
    await night_shift.insert()
    rotating = Shift(company_id=cid, code="A", start="06:00", end="14:00")
    await rotating.insert()
    for module, values in ((name, schema().model_dump(mode="json")) for name, schema in SCHEMAS.items()):
        await SettingDoc(company_id=cid, module=module, values=values).insert()
    for when, name, kind, scope, cities in HOLIDAYS:
        await Holiday(
            company_id=cid, date=when, name=name, type=kind, scope=scope, cities=list(cities)
        ).insert()
    for frequency, rows in (("monthly", MONTHLY_TAX), ("annual", ANNUAL_TAX)):
        await TaxTable(
            company_id=cid,
            effective_from=date(2026, 1, 1),
            frequency=frequency,
            brackets=[TaxBracketRow(start=a, base_tax=b, rate=c) for a, b, c in rows],
        ).insert()
    for agency in ("sss", "philhealth", "pagibig"):
        await ContributionTable(
            company_id=cid,
            agency=agency,
            effective_from=date(2025, 1, 1),
            brackets=_brackets(agency),
        ).insert()
    flow_steps = [
        FlowStep(order=1, approver_type="specific_role", approver_value="Department Manager"),
        FlowStep(order=2, approver_type="hr_admin"),
    ]
    for module in MODULES:
        await ApprovalFlow(company_id=cid, module=module, name=module, steps=flow_steps).insert()

    employees: list[Employee] = []
    for index in range(50):
        if index < 3:
            status, basis, basic = "probationary", "monthly", "28000"
        elif index < 6:
            status, basis, basic = "contractual", "monthly", "32000"
        elif index < 9:
            status, basis, basic = "regular", "daily", "695"
        elif index < 12:
            status, basis, basic = "regular", "daily", "800"
        else:
            status, basis, basic = "regular", "monthly", str(25000 + (index % 8) * 5000)
        salary, daily, hourly = _rates(basic, basis)
        if index == 0:
            dept_index = 0
            manager_id = None
        elif index <= 5:
            dept_index = index
            manager_id = str(employees[0].id)
        else:
            dept_index = 1 + (index % 5)
            manager_id = str(employees[dept_index].id)
        chain = [] if manager_id is None else [manager_id]
        hired = date(2024, 3, 1) if status == "regular" else date(2026, 6, 1)
        employee = Employee(
            company_id=cid,
            employee_no=f"EMP-{index + 1:05d}",
            name=PersonName(first=FIRST[index], last=LAST[index]),
            gender="female" if index % 2 else "male",
            civil_status="single" if index % 3 else "married",
            contact={"email": f"emp{index + 1}@demo.example.com", "mobile": f"09{index:09d}"},
            branch_id=str(cebu.id if index % 4 == 0 else manila.id),
            department_id=str(departments[dept_index].id),
            position_id=str(positions[min(index, len(positions) - 1)].id),
            cost_center_id=str(centers[dept_index].id),
            reports_to=manager_id,
            manager_chain=chain,
            pay_group_id=str(day_group.id if basis == "daily" else pay_group.id),
            employment_type=status if status != "probationary" else "regular",
            employment_status="active",
            date_hired=hired,
            probation_end_date=date(2026, 11, 20) if status == "probationary" else None,
            contract_end_date=date(2026, 12, 31) if status == "contractual" else None,
            is_minimum_wage_earner=index in {6, 7, 8},
            current_compensation=CompensationSnapshot(
                basic_salary=salary if basis == "monthly" else daily,
                pay_basis=basis,
                daily_rate=daily,
                hourly_rate=hourly,
            ),
        )
        if status == "probationary":
            employee.employment_status = "probationary"
        await employee.insert()
        employees.append(employee)
        await CompensationHistory(
            company_id=cid,
            employee_id=str(employee.id),
            basic_salary=employee.current_compensation.basic_salary,
            pay_basis=basis,
            daily_rate=daily,
            hourly_rate=hourly,
            effective_date=hired,
            reason="hire",
        ).insert()
        await EmployeeSensitive(
            company_id=cid,
            employee_id=str(employee.id),
            tin=encrypt(f"{100000000 + index:012d}"),
            sss_no=encrypt(f"{10 + index:02d}-{1000000 + index:07d}-{index % 10}"),
            philhealth_no=encrypt(f"{12 + index:02d}-{100000000 + index:09d}-{index % 10}"),
            pagibig_no=encrypt(f"{1210 + index:012d}"),
            bank_accounts=[{"bank": "BDO", "account_no": encrypt(f"{1000000000 + index}"), "name": "payroll"}],
        ).insert()
        schedule_id = str(night_shift.id if 13 <= index <= 15 else day_shift.id)
        await EmployeeSchedule(
            company_id=cid,
            employee_id=str(employee.id),
            work_schedule_id=schedule_id,
            effective_from=hired,
        ).insert()

    users["Employee"].employee_id = str(employees[20].id)
    employees[20].user_id = str(users["Employee"].id)
    users["Department Manager"].employee_id = str(employees[1].id)
    employees[1].user_id = str(users["Department Manager"].id)
    departments[1].head_employee_id = str(employees[1].id)
    await users["Employee"].save()
    await users["Department Manager"].save()
    await employees[20].save()
    await employees[1].save()
    await departments[1].save()
    await Counter(company_id=cid, key="employee", value=50).insert()

    days: list[AttendanceDay] = []
    local_holiday = {date(2026, 10, 16)}
    for employee in employees:
        index = int(employee.employee_no.split("-")[1]) - 1
        for month in (9, 10):
            for day in _weekdays(2026, month):
                absent = index % 11 == 0 and day.day == 3
                late = 20 if index % 7 == 0 and day.weekday() == 0 else 0
                ot = 60 if index % 5 == 0 and day.weekday() == 4 else 0
                night = 480 if 13 <= index <= 15 else 0
                city_holiday = day in local_holiday and employee.branch_id == str(cebu.id)
                status = "holiday" if city_holiday else "absent" if absent else "present"
                days.append(
                    AttendanceDay(
                        company_id=cid,
                        employee_id=str(employee.id),
                        date=day,
                        hours_worked="0" if status != "present" else "8",
                        late_minutes=0 if status != "present" else late,
                        overtime_minutes=0 if status != "present" else ot,
                        night_diff_minutes=0 if status != "present" else night,
                        holiday_type="special" if city_holiday else "none",
                        status=status,
                        is_locked=month == 9,
                    )
                )
    await AttendanceDay.insert_many(days)

    vacation = LeaveType(
        company_id=cid, code="VL", name="Vacation Leave", annual_entitlement="15", convertible_to_cash=True
    )
    sick = LeaveType(company_id=cid, code="SL", name="Sick Leave", annual_entitlement="15")
    await vacation.insert()
    await sick.insert()
    for employee in employees:
        for leave_type, entitled in ((vacation, "15"), (sick, "15")):
            await LeaveBalance(
                company_id=cid,
                employee_id=str(employee.id),
                leave_type_id=str(leave_type.id),
                year=2026,
                entitled=entitled,
            ).insert()
            await LeaveLedger(
                company_id=cid,
                employee_id=str(employee.id),
                leave_type_id=str(leave_type.id),
                year=2026,
                entry_type="entitlement",
                days=entitled,
                at=utcnow(),
            ).insert()
    for offset, status in enumerate(LEAVE_STATUSES):
        person = employees[30 + offset]
        await LeaveRequest(
            company_id=cid,
            employee_id=str(person.id),
            leave_type_id=str(vacation.id),
            start_date=date(2026, 10, 5 + offset),
            end_date=date(2026, 10, 5 + offset),
            days="1",
            reason=status,
            status=status,
        ).insert()

    tax = tuple(TaxBracket(Decimal(a), Decimal(b), Decimal(c)) for a, b, c in MONTHLY_TAX)
    periods = {}
    ytd_by_employee = {str(person.id): Ytd() for person in employees}
    for month, period_status, run_status in (
        (8, "locked", "locked"),
        (9, "approved", "approved"),
        (10, "computed", "computed"),
    ):
        start = date(2026, month, 1)
        end = date(2026, month, calendar.monthrange(2026, month)[1])
        period = PayrollPeriod(
            company_id=cid,
            pay_group_id=str(pay_group.id),
            start=start,
            end=end,
            attendance_cutoff=end,
            pay_date=end,
            status=period_status,
            period_index=1,
            periods_in_month=1,
        )
        await period.insert()
        periods[month] = period
        run = PayrollRun(
            company_id=cid,
            period_id=str(period.id),
            computed_by=str(users["Payroll Officer"].id),
            computed_at=datetime(2026, month, 28, tzinfo=UTC),
            approved_by=str(users["Payroll Approver"].id) if run_status != "computed" else None,
            approved_at=datetime(2026, month, 28, tzinfo=UTC) if run_status != "computed" else None,
            progress_done=len(employees),
            progress_total=len(employees),
            status=run_status,
        )
        await run.insert()
        slips = []
        for person in employees:
            comp = person.current_compensation
            assert comp is not None
            number = int(person.employee_no.split("-")[1]) - 1
            worked = Decimal("21") if number % 11 == 0 else Decimal("22")
            result = compute_payroll(
                PayrollInput(
                    employee_id=str(person.id),
                    pay_basis=comp.pay_basis,
                    basic_salary=comp.basic_salary if comp.pay_basis == "monthly" else Decimal("0"),
                    daily_rate=comp.daily_rate,
                    hourly_rate=comp.hourly_rate,
                    periods_per_year=12,
                    period_start=start,
                    period_end=end,
                    working_days_in_period=Decimal("22"),
                    days_employed_in_period=Decimal("22"),
                    days_worked=worked,
                    hours_worked=worked * Decimal(8),
                    absence_days=Decimal("22") - worked,
                    is_minimum_wage_earner=person.is_minimum_wage_earner,
                    sss=sss_amount(comp.basic_salary if comp.pay_basis == "monthly" else comp.daily_rate * Decimal(22)),
                    philhealth=philhealth_amount(
                        comp.basic_salary if comp.pay_basis == "monthly" else comp.daily_rate * Decimal(22)
                    ),
                    pagibig=pagibig_amount(
                        comp.basic_salary if comp.pay_basis == "monthly" else comp.daily_rate * Decimal(22)
                    ),
                    tax_brackets=tax,
                    ytd=ytd_by_employee[str(person.id)],
                )
            )
            ytd_by_employee[str(person.id)] = result.ytd
            slips.append(
                Payslip(
                    company_id=cid,
                    run_id=str(run.id),
                    period_id=str(period.id),
                    employee_id=str(person.id),
                    basic_pay=result.basic_pay,
                    gross=result.gross,
                    taxable_income=result.taxable_income,
                    non_taxable_income=result.non_taxable_income,
                    withholding_tax=result.withholding_tax,
                    total_deductions=result.total_deductions,
                    net_pay=result.net_pay,
                    has_deferrals=result.has_deferrals,
                    is_published=run_status == "locked",
                    lines=[
                        PayslipLine(
                            type=line.type,
                            code=line.code,
                            label=line.label,
                            quantity=line.quantity,
                            rate=line.rate,
                            amount=line.amount,
                            is_taxable=line.is_taxable,
                            deferred=line.deferred,
                            ref_id=line.ref_id,
                        )
                        for line in result.lines
                    ],
                    ytd={
                        "gross": format(result.ytd.gross, "f"),
                        "taxable": format(result.ytd.taxable, "f"),
                        "non_taxable": format(result.ytd.non_taxable, "f"),
                        "contributions": format(result.ytd.contributions, "f"),
                        "tax_withheld": format(result.ytd.tax_withheld, "f"),
                        "basic": format(result.ytd.basic, "f"),
                    },
                    snapshot={"employee_no": person.employee_no, "pay_basis": comp.pay_basis},
                )
            )
        await Payslip.insert_many(slips)

    borrower = employees[21]
    await Loan(
        company_id=cid,
        employee_id=str(borrower.id),
        type="sss_loan",
        reference_no="SSS-1001",
        principal="20000",
        amortization="1500",
        balance="14000",
        status="active",
    ).insert()
    await RecurringDeduction(
        company_id=cid,
        employee_id=str(borrower.id),
        type="HMO dependents",
        label="HMO dependent",
        amount="500",
        until=date(2026, 12, 31),
    ).insert()
    plan = BenefitPlan(
        company_id=cid,
        type="hmo",
        provider="Sample HMO",
        plan_name="Employee HMO",
        employer_share="1500",
        employee_share="0",
        dependent_cost="500",
    )
    await plan.insert()
    await BenefitEnrollment(
        company_id=cid,
        employee_id=str(borrower.id),
        plan_id=str(plan.id),
        covered_dependents=["Child Santos"],
        effective_from=date(2026, 1, 1),
        card_no="HMO-1001",
    ).insert()
    meal = ClaimType(company_id=cid, name="Meal", taxability="non_taxable")
    await meal.insert()
    await Claim(
        company_id=cid,
        employee_id=str(employees[22].id),
        claim_type_id=str(meal.id),
        date=date(2026, 10, 8),
        amount="450",
        description="Client lunch",
        status="pending",
    ).insert()
    await CashAdvance(
        company_id=cid,
        employee_id=str(employees[22].id),
        amount="2000",
        purpose="Field work",
        balance="2000",
    ).insert()

    opening = JobOpening(
        company_id=cid,
        title="Software Engineer",
        description="Build the internal tools.",
        location="Manila",
        employment_type="regular",
        is_public=True,
        status="open",
    )
    req = ManpowerRequisition(
        company_id=cid,
        department_id=str(departments[5].id),
        position_id=str(positions[11].id),
        headcount=1,
        budget="45000",
        target_start=date(2026, 12, 1),
        status="approved",
    )
    await req.insert()
    opening.requisition_id = str(req.id)
    await opening.insert()
    for stage in STAGES:
        await Applicant(
            company_id=cid,
            job_opening_id=str(opening.id),
            name=f"{stage.title()} Applicant",
            email=f"{stage}@applicants.example.com",
            stage=stage,
            source="careers",
            consent_given_at=utcnow(),
        ).insert()

    offense = Offense(company_id=cid, offense="Tardiness", category="attendance", sanctions_by_count=["written", "suspension"])
    await offense.insert()
    await DisciplinaryCase(
        company_id=cid,
        employee_id=str(employees[23].id),
        offense_id=str(offense.id),
        case_no="ER-2026-0001",
        status="hearing",
        details=encrypt("Sample notice details for the hearing."),
        events=[{"at": utcnow().isoformat(), "type": "nte_issued"}],
    ).insert()

    leaver = employees[24]
    category = AssetCategory(company_id=cid, name="Laptop")
    await category.insert()
    laptop = Asset(
        company_id=cid,
        tag="LT-1001",
        name="Laptop",
        category_id=str(category.id),
        cost="45000",
        status="assigned",
        purchase_date=date(2025, 1, 15),
    )
    await laptop.insert()
    await AssetAssignment(
        company_id=cid,
        asset_id=str(laptop.id),
        employee_id=str(leaver.id),
        issued_at=utcnow() - timedelta(days=40),
        condition_out="good",
    ).insert()
    await Resignation(
        company_id=cid,
        employee_id=str(leaver.id),
        filed_at=date(2026, 10, 15),
        last_working_day=date(2026, 11, 15),
        reason="Personal",
        status="clearance",
    ).insert()
    await Clearance(
        company_id=cid,
        employee_id=str(leaver.id),
        status="open",
        items=[
            ClearanceItem(department="IT", item="Return laptop LT-1001", blocking=True),
            ClearanceItem(department="Finance", item="Clear cash advance", blocking=False),
        ],
    ).insert()
    await FinalPay(
        company_id=cid,
        employee_id=str(leaver.id),
        status="draft",
        net="0",
        target_release_date=date(2026, 12, 15),
    ).insert()
    print("Seeded Demo Trading Co. Password for every user: ChangeMe123!")
