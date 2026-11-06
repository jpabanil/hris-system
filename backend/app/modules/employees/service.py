"""Employee use cases. No FastAPI imports."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from beanie import PydanticObjectId
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import DuplicateKeyError

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.db import transaction
from app.core.encryption import decrypt, encrypt, mask
from app.core.errors import AppError
from app.core.money import money
from app.core.repository import TenantRepo, api, guard_keys
from app.modules.employees.models import (
    CompensationHistory,
    CompensationSnapshot,
    Employee,
    EmployeeDocument,
    EmployeeMovement,
    EmployeeSensitive,
    PersonName,
    ProfileUpdateRequest,
)
from app.modules.employees.policies import can_view_employee
from app.modules.employees.schemas import (
    BankAccountWrite,
    CompensationWrite,
    DocumentWrite,
    EmployeeCreate,
    EmployeeUpdate,
    MovementWrite,
    ProfileUpdateEdit,
    ProfileUpdateWrite,
    SensitiveWrite,
)
from app.shared.approvals import handles, start_request
from app.shared.audit import write_audit
from app.shared.models import ApprovalRequest
from app.shared.sequences import next_number
from app.shared.settings_store import PayrollSettings, get_settings_model

_PAY_BASIS = {"monthly", "daily", "hourly"}
_MOVEMENT_TYPES = {
    "promotion",
    "transfer",
    "salary_adjustment",
    "status_change",
    "regularization",
    "demotion",
}
_PROFILE_FIELDS = {
    "name",
    "birth_date",
    "birth_place",
    "gender",
    "civil_status",
    "nationality",
    "blood_type",
    "contact",
    "present_address",
    "permanent_address",
    "emergency_contacts",
    "dependents",
    "education",
    "work_history",
    "skills",
    "licenses",
    "photo_key",
    "signature_key",
}
_PROFILE_LISTS = {
    "emergency_contacts",
    "dependents",
    "education",
    "work_history",
    "skills",
    "licenses",
}
_SECRET_FIELDS = ("tin", "sss_no", "philhealth_no", "pagibig_no")
_EMPLOYEE_SORT = {"created_at", "employee_no", "date_hired", "employment_status"}
_SEARCH = ("employee_no", "name.first", "name.last", "name.nickname")


def _missing() -> AppError:
    return AppError("not_found", "Record not found", 404)


def _forbid() -> AppError:
    return AppError("forbidden", "You do not have access to this action", 403)


def _company(actor: Actor) -> str:
    if not actor.company_id:
        raise AppError("company_required", "Choose a company first", 400)
    return actor.company_id


def _oid(value: str) -> PydanticObjectId | None:
    try:
        return PydanticObjectId(value)
    except Exception:
        return None


def _reader_scope(actor: Actor) -> dict[str, Any] | None:
    if not (
        actor.has("employees.view") or actor.has("employees.view_team") or actor.has("self.service")
    ):
        raise _forbid()
    if actor.has("employees.view"):
        return None
    oid = _oid(actor.employee_id or "")
    if oid is None:
        return {"_id": {"$in": []}}
    if actor.has("employees.view_team"):
        return {
            "$or": [
                {"_id": oid},
                {"reports_to": actor.employee_id},
                {"manager_chain": actor.employee_id},
            ]
        }
    return {"_id": oid}


async def _for_read(actor: Actor, employee_id: str) -> Employee:
    employee = await TenantRepo(Employee, actor).get(employee_id)
    if not can_view_employee(actor, employee):
        raise _missing()
    return employee


async def _for_write(actor: Actor, employee_id: str) -> Employee:
    return await TenantRepo(Employee, actor).get(employee_id)


async def _chain_for(actor: Actor, reports_to: str | None, self_id: str | None) -> list[str]:
    if not reports_to:
        return []
    if self_id and reports_to == self_id:
        raise AppError("bad_request", "An employee cannot report to themselves", 400)
    manager = await TenantRepo(Employee, actor).get(reports_to)
    manager_id = str(manager.id)
    chain = [item for item in manager.manager_chain if item != manager_id]
    chain.append(manager_id)
    if self_id and self_id in chain:
        raise AppError("bad_request", "That reporting line would create a cycle", 400)
    return chain


def _looks_hidden(value: str) -> bool:
    return "•" in value or value.startswith("v1:")


def _seal(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return encrypt(text)


def _open_secret(stored: str, reveal: bool) -> str:
    if not stored:
        return ""
    try:
        plain = decrypt(stored) if stored.startswith("v1:") else stored
    except Exception:
        plain = ""
    return plain if reveal else mask(plain)


def _seal_account(account: BankAccountWrite | dict[str, Any], existing: str = "") -> dict[str, Any]:
    if isinstance(account, BankAccountWrite):
        raw = account.model_dump()
    else:
        raw = account
    number = str(raw.get("account_no") or "")
    if _looks_hidden(number):
        sealed = existing
    else:
        sealed = _seal(number)
    return {
        "bank_name": str(raw.get("bank_name") or ""),
        "account_name": str(raw.get("account_name") or ""),
        "account_no": sealed,
        "is_primary": bool(raw.get("is_primary")),
    }


def _present_account(account: dict[str, Any], reveal: bool) -> dict[str, Any]:
    return {
        "bank_name": account.get("bank_name") or "",
        "account_name": account.get("account_name") or "",
        "account_no": _open_secret(str(account.get("account_no") or ""), reveal),
        "is_primary": bool(account.get("is_primary")),
    }


def _merge_secret(incoming: str | None, existing: str) -> str:
    if incoming is None:
        return existing
    if incoming == "":
        return ""
    if _looks_hidden(incoming):
        return existing
    return _seal(incoming)


async def _audit(
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    session: AsyncClientSession | None = None,
) -> None:
    await write_audit(
        company_id=actor.company_id,
        actor_id=actor.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        session=session,
    )


async def list_employees(
    actor: Actor,
    page: int,
    page_size: int,
    q: str | None,
    sort: str | None,
    *,
    department_id: str | None = None,
    branch_id: str | None = None,
    position_id: str | None = None,
    employment_status: str | None = None,
) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = []
    scope = _reader_scope(actor)
    if scope:
        clauses.append(scope)
    if department_id:
        clauses.append({"department_id": department_id})
    if branch_id:
        clauses.append({"branch_id": branch_id})
    if position_id:
        clauses.append({"position_id": position_id})
    if employment_status:
        clauses.append({"employment_status": employment_status})
    extra = {"$and": clauses} if clauses else None
    return await TenantRepo(Employee, actor).list(
        page=page,
        page_size=page_size,
        search_fields=_SEARCH,
        sort_fields=_EMPLOYEE_SORT,
        q=q,
        sort=sort,
        extra=extra,
    )


async def create_employee(actor: Actor, body: EmployeeCreate) -> dict[str, Any]:
    company_id = _company(actor)
    number = (body.employee_no or "").strip()
    if not number:
        number = await next_number(company_id, "employee", "EMP-")
    chain = await _chain_for(actor, body.reports_to, None)
    data = guard_keys(body.model_dump(exclude={"sensitive", "employee_no"}))
    data["name"] = PersonName.model_validate(data["name"])
    employee = Employee(
        company_id=company_id,
        employee_no=number,
        manager_chain=chain,
        created_by=actor.user_id,
        updated_by=actor.user_id,
        **data,
    )
    try:
        async with transaction() as session:
            await employee.insert(session=session)
            if body.sensitive is not None:
                sealed = _encrypted_sensitive(body.sensitive, None)
                record = EmployeeSensitive(
                    company_id=company_id,
                    employee_id=str(employee.id),
                    **sealed,
                )
                await record.insert(session=session)
                await _audit(
                    actor,
                    "create",
                    "employee_sensitive",
                    str(record.id),
                    after=api(record),
                    session=session,
                )
            await _audit(
                actor,
                "create",
                "employees",
                str(employee.id),
                after=api(employee),
                session=session,
            )
    except DuplicateKeyError:
        raise AppError("conflict", "That employee number is already used", 409) from None
    return api(employee)


def _encrypted_sensitive(
    body: SensitiveWrite,
    existing: EmployeeSensitive | None,
) -> dict[str, Any]:
    current = existing.model_dump() if existing is not None else {}
    payload: dict[str, Any] = {}
    for field in _SECRET_FIELDS:
        incoming = getattr(body, field)
        payload[field] = _merge_secret(incoming, str(current.get(field) or ""))
    if body.bank_accounts is None:
        payload["bank_accounts"] = list(current.get("bank_accounts") or [])
    else:
        previous = list(current.get("bank_accounts") or [])
        sealed_accounts = []
        for index, account in enumerate(body.bank_accounts):
            old_number = ""
            if index < len(previous):
                old_number = str(previous[index].get("account_no") or "")
            sealed_accounts.append(_seal_account(account, old_number))
        payload["bank_accounts"] = sealed_accounts
    return payload


async def get_employee(actor: Actor, employee_id: str) -> dict[str, Any]:
    return api(await _for_read(actor, employee_id))


async def update_employee(actor: Actor, employee_id: str, body: EmployeeUpdate) -> dict[str, Any]:
    employee = await _for_write(actor, employee_id)
    if body.revision is None or body.revision != employee.revision:
        raise AppError("conflict", "This record changed. Reload and try again.", 409)
    before = api(employee)
    data = guard_keys(body.model_dump(exclude_unset=True))
    data.pop("revision", None)
    if "employee_no" in data:
        number = (data.get("employee_no") or "").strip()
        if not number:
            data.pop("employee_no", None)
        else:
            data["employee_no"] = number
    if "name" in data and data["name"] is not None:
        data["name"] = PersonName.model_validate(data["name"])
    if "reports_to" in data:
        employee.manager_chain = await _chain_for(actor, data["reports_to"], str(employee.id))
    for key, value in data.items():
        setattr(employee, key, value)
    employee.revision += 1
    employee.updated_at = utcnow()
    employee.updated_by = actor.user_id
    try:
        await employee.save()
    except DuplicateKeyError:
        raise AppError("conflict", "That employee number is already used", 409) from None
    await _audit(actor, "update", "employees", str(employee.id), before=before, after=api(employee))
    return api(employee)


async def delete_employee(actor: Actor, employee_id: str) -> None:
    await TenantRepo(Employee, actor).soft_delete(employee_id)


async def my_profile(actor: Actor) -> dict[str, Any]:
    if not actor.employee_id:
        raise _missing()
    employee = await TenantRepo(Employee, actor).get(actor.employee_id)
    if not can_view_employee(actor, employee):
        raise _missing()
    return api(employee)


def _sensitive_view(
    actor: Actor,
    employee: Employee,
    record: EmployeeSensitive | None,
) -> dict[str, Any]:
    reveal = actor.has("employees.view_sensitive")
    stored = record.model_dump() if record is not None else {}
    accounts = [_present_account(item, reveal) for item in stored.get("bank_accounts") or []]
    return {
        "id": str(record.id) if record is not None else None,
        "employee_id": str(employee.id),
        "tin": _open_secret(str(stored.get("tin") or ""), reveal),
        "sss_no": _open_secret(str(stored.get("sss_no") or ""), reveal),
        "philhealth_no": _open_secret(str(stored.get("philhealth_no") or ""), reveal),
        "pagibig_no": _open_secret(str(stored.get("pagibig_no") or ""), reveal),
        "bank_accounts": accounts,
    }


async def _load_sensitive(employee: Employee) -> EmployeeSensitive | None:
    return await EmployeeSensitive.find_one(
        {"company_id": employee.company_id, "employee_id": str(employee.id)}
    )


async def get_sensitive(actor: Actor, employee_id: str) -> dict[str, Any]:
    employee = await _for_read(actor, employee_id)
    return _sensitive_view(actor, employee, await _load_sensitive(employee))


async def save_sensitive(actor: Actor, employee_id: str, body: SensitiveWrite) -> dict[str, Any]:
    employee = await _for_write(actor, employee_id)
    company_id = employee.company_id
    existing = await _load_sensitive(employee)
    before = api(existing) if existing is not None else None
    sealed = _encrypted_sensitive(body, existing)
    if existing is None:
        existing = EmployeeSensitive(company_id=company_id, employee_id=str(employee.id), **sealed)
        await existing.insert()
        await _audit(actor, "create", "employee_sensitive", str(existing.id), after=api(existing))
    else:
        for key, value in sealed.items():
            setattr(existing, key, value)
        await existing.save()
        await _audit(
            actor,
            "update",
            "employee_sensitive",
            str(existing.id),
            before=before,
            after=api(existing),
        )
    return _sensitive_view(actor, employee, existing)


async def list_compensation(
    actor: Actor,
    employee_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    employee = await _for_read(actor, employee_id)
    return await TenantRepo(CompensationHistory, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields={"effective_date", "created_at"},
        q=None,
        sort="-effective_date",
        extra={"employee_id": str(employee.id)},
    )


async def add_compensation(
    actor: Actor,
    employee_id: str,
    body: CompensationWrite,
) -> dict[str, Any]:
    if body.pay_basis not in _PAY_BASIS:
        raise AppError("bad_request", "Pay basis must be monthly, daily, or hourly", 400)
    employee = await _for_write(actor, employee_id)
    company_id = employee.company_id
    settings = await get_settings_model(company_id, "payroll")
    if not isinstance(settings, PayrollSettings) or settings.factor_days_per_year <= 0:
        raise AppError("bad_request", "Payroll factor days per year is not configured", 400)
    factor_days = settings.factor_days_per_year
    basic = money(body.basic_salary)
    if basic < 0:
        raise AppError("bad_request", "Basic salary cannot be negative", 400)
    factor = Decimal(factor_days)
    daily_rate = money(basic * Decimal(12) / factor)
    hourly_rate = money(daily_rate / Decimal(8))
    before = api(employee)
    history = CompensationHistory(
        company_id=company_id,
        employee_id=str(employee.id),
        basic_salary=basic,
        pay_basis=body.pay_basis,
        daily_rate=daily_rate,
        hourly_rate=hourly_rate,
        factor_days_per_year=factor_days,
        effective_date=body.effective_date,
        reason=body.reason,
        approval_request_id=body.approval_request_id,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    employee.current_compensation = CompensationSnapshot(
        basic_salary=basic,
        pay_basis=body.pay_basis,
        daily_rate=daily_rate,
        hourly_rate=hourly_rate,
    )
    employee.revision += 1
    employee.updated_at = utcnow()
    employee.updated_by = actor.user_id
    async with transaction() as session:
        await history.insert(session=session)
        await employee.save(session=session)
        await _audit(
            actor,
            "create",
            "compensation_history",
            str(history.id),
            after=api(history),
            session=session,
        )
        await _audit(
            actor,
            "update",
            "employees",
            str(employee.id),
            before=before,
            after=api(employee),
            session=session,
        )
    return api(history)


async def list_movements(
    actor: Actor,
    employee_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    employee = await _for_read(actor, employee_id)
    return await TenantRepo(EmployeeMovement, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields={"effective_date", "created_at"},
        q=None,
        sort="-effective_date",
        extra={"employee_id": str(employee.id)},
    )


async def add_movement(actor: Actor, employee_id: str, body: MovementWrite) -> dict[str, Any]:
    if body.type not in _MOVEMENT_TYPES:
        raise AppError("bad_request", "Unknown movement type", 400)
    employee = await _for_write(actor, employee_id)
    row = EmployeeMovement(
        company_id=employee.company_id,
        employee_id=str(employee.id),
        type=body.type,
        from_value=guard_keys(body.from_value),
        to_value=guard_keys(body.to_value),
        effective_date=body.effective_date,
        approval_request_id=body.approval_request_id,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await row.insert()
    await _audit(actor, "create", "employee_movements", str(row.id), after=api(row))
    return api(row)


async def list_documents(
    actor: Actor,
    employee_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    employee = await _for_read(actor, employee_id)
    return await TenantRepo(EmployeeDocument, actor).list(
        page=page,
        page_size=page_size,
        search_fields=("document_type",),
        sort_fields={"created_at", "document_type", "expires_at"},
        q=None,
        sort="-created_at",
        extra={"employee_id": str(employee.id)},
    )


async def add_document(actor: Actor, employee_id: str, body: DocumentWrite) -> dict[str, Any]:
    employee = await _for_write(actor, employee_id)
    row = EmployeeDocument(
        company_id=employee.company_id,
        employee_id=str(employee.id),
        document_type=body.document_type,
        file_key=body.file_key,
        expires_at=body.expires_at,
        is_confidential=body.is_confidential,
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    await row.insert()
    await _audit(actor, "create", "employee_documents", str(row.id), after=api(row))
    return api(row)


async def delete_document(actor: Actor, employee_id: str, document_id: str) -> None:
    employee = await _for_write(actor, employee_id)
    row = await TenantRepo(EmployeeDocument, actor).get(document_id)
    if row.employee_id != str(employee.id):
        raise _missing()
    await TenantRepo(EmployeeDocument, actor).soft_delete(document_id)


async def employee_assets(
    actor: Actor,
    employee_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    employee = await _for_read(actor, employee_id)
    from app.modules.assets.service import assignments_for_employee

    return await assignments_for_employee(actor, str(employee.id), page, page_size)


def _event(kind: str, on: date, row: Any) -> dict[str, Any]:
    return {"kind": kind, "date": on.isoformat(), "id": str(row.id), "record": api(row)}


async def _leave_events(company_id: str, employee_id: str) -> list[dict[str, Any]]:
    try:
        from app.modules.leave.models import LeaveRequest
    except ImportError:
        return []
    rows = await LeaveRequest.find({"company_id": company_id, "employee_id": employee_id}).to_list()
    return [_event("leave", row.start_date, row) for row in rows]


async def employee_timeline(actor: Actor, employee_id: str) -> list[dict[str, Any]]:
    employee = await _for_read(actor, employee_id)
    company_id = employee.company_id
    eid = str(employee.id)
    events: list[dict[str, Any]] = []
    movements = await EmployeeMovement.find(
        {"company_id": company_id, "employee_id": eid}
    ).to_list()
    events.extend(_event("movement", row.effective_date, row) for row in movements)
    history = await CompensationHistory.find(
        {"company_id": company_id, "employee_id": eid}
    ).to_list()
    events.extend(_event("compensation", row.effective_date, row) for row in history)
    events.extend(await _leave_events(company_id, eid))
    events.sort(key=lambda item: (item["date"], item["kind"], item["id"]))
    return events


def _clean_changes(employee: Employee, changes: dict[str, Any]) -> dict[str, Any]:
    cleaned = guard_keys(changes)
    unknown = sorted(key for key in cleaned if key not in _PROFILE_FIELDS)
    if unknown:
        raise AppError("bad_field", "Those fields cannot be changed on a profile request", 400)
    if not cleaned:
        raise AppError("bad_request", "Changes are required", 400)
    if "name" in cleaned:
        if not isinstance(cleaned["name"], dict):
            raise AppError("bad_field", "Name must be an object", 400)
        merged = employee.name.model_dump()
        merged.update(guard_keys(cleaned["name"]))
        try:
            PersonName.model_validate(merged)
        except Exception:
            raise AppError("bad_field", "Name must include first and last", 400) from None
    if "contact" in cleaned and not isinstance(cleaned["contact"], dict):
        raise AppError("bad_field", "Contact must be an object", 400)
    for field in _PROFILE_LISTS:
        if field in cleaned and not isinstance(cleaned[field], list):
            raise AppError("bad_field", f"{field} must be a list", 400)
    if "birth_date" in cleaned and cleaned["birth_date"] not in (None, ""):
        value = cleaned["birth_date"]
        if isinstance(value, date):
            cleaned["birth_date"] = value.isoformat()
        else:
            try:
                cleaned["birth_date"] = date.fromisoformat(str(value)).isoformat()
            except ValueError:
                raise AppError("bad_field", "birth_date is not a date", 400) from None
    return cleaned


def _apply_changes(employee: Employee, changes: dict[str, Any]) -> None:
    for key, value in changes.items():
        if key not in _PROFILE_FIELDS:
            continue
        if key == "name" and isinstance(value, dict):
            merged = employee.name.model_dump()
            merged.update(guard_keys(value))
            employee.name = PersonName.model_validate(merged)
            continue
        if key == "birth_date":
            if value in (None, ""):
                employee.birth_date = None
            elif isinstance(value, date):
                employee.birth_date = value
            else:
                employee.birth_date = date.fromisoformat(str(value))
            continue
        setattr(employee, key, value)


async def _apply_profile_update(
    request: ApprovalRequest,
    session: AsyncClientSession | None,
) -> None:
    doc = await ProfileUpdateRequest.get(request.subject_id, session=session)
    if doc is None or doc.company_id != request.company_id:
        return
    doc.approval_request_id = str(request.id)
    doc.status = request.status
    doc.updated_at = utcnow()
    if request.status == "approved":
        employee = await Employee.get(doc.employee_id, session=session)
        if (
            employee is not None
            and employee.deleted_at is None
            and employee.company_id == doc.company_id
        ):
            _apply_changes(employee, doc.changes)
            actor_id = request.requester_id
            if request.actions:
                actor_id = request.actions[-1].actor_id
            employee.revision += 1
            employee.updated_at = utcnow()
            employee.updated_by = actor_id
            await employee.save(session=session)
    await doc.save(session=session)


@handles("profile_update")
async def apply_profile_update(
    request: ApprovalRequest,
    session: AsyncClientSession | None,
) -> None:
    if session is None:
        async with transaction() as owned:
            await _apply_profile_update(request, owned)
        return
    await _apply_profile_update(request, session)


async def _profile_scope(actor: Actor) -> dict[str, Any] | None:
    if actor.has("employees.view") or actor.has("employees.manage"):
        return None
    if actor.has("employees.view_team") and actor.employee_id:
        oid = _oid(actor.employee_id)
        if oid is None:
            return {"employee_id": {"$in": []}}
        people = await Employee.find(
            {
                "company_id": _company(actor),
                "deleted_at": None,
                "$or": [
                    {"_id": oid},
                    {"reports_to": actor.employee_id},
                    {"manager_chain": actor.employee_id},
                ],
            }
        ).to_list()
        return {"employee_id": {"$in": [str(person.id) for person in people]}}
    if actor.has("self.service") and actor.employee_id:
        return {"employee_id": actor.employee_id}
    raise _forbid()


async def _profile_visible(actor: Actor, doc: ProfileUpdateRequest) -> bool:
    if doc.company_id != _company(actor):
        return False
    if actor.has("employees.manage") or actor.has("employees.view"):
        return True
    if doc.created_by == actor.user_id:
        return True
    employee = await Employee.get(doc.employee_id)
    if employee is None:
        return False
    return can_view_employee(actor, employee)


async def list_profile_updates(
    actor: Actor,
    page: int,
    page_size: int,
    employee_id: str | None,
) -> dict[str, Any]:
    scope = await _profile_scope(actor)
    clauses: list[dict[str, Any]] = []
    if scope:
        clauses.append(scope)
    if employee_id:
        clauses.append({"employee_id": employee_id})
    extra = {"$and": clauses} if clauses else None
    return await TenantRepo(ProfileUpdateRequest, actor).list(
        page=page,
        page_size=page_size,
        search_fields=(),
        sort_fields={"created_at", "status"},
        q=None,
        sort="-created_at",
        extra=extra,
    )


async def create_profile_update(actor: Actor, body: ProfileUpdateWrite) -> dict[str, Any]:
    company_id = _company(actor)
    if actor.has("employees.manage"):
        target = body.employee_id or actor.employee_id
        if not target:
            raise _missing()
        employee = await _for_write(actor, target)
    else:
        if not actor.has("self.service") or not actor.employee_id:
            raise _forbid()
        if body.employee_id and body.employee_id != actor.employee_id:
            raise _missing()
        employee = await _for_read(actor, actor.employee_id)
    changes = _clean_changes(employee, body.changes)
    doc = ProfileUpdateRequest(
        company_id=company_id,
        employee_id=str(employee.id),
        changes=changes,
        status="pending",
        created_by=actor.user_id,
        updated_by=actor.user_id,
    )
    async with transaction() as session:
        await doc.insert(session=session)
        approval = await start_request(
            actor=actor,
            module="profile_update",
            subject_type="profile_update",
            subject_id=str(doc.id),
            context={"employee_id": str(employee.id)},
            session=session,
        )
        doc.approval_request_id = str(approval.id)
        doc.status = approval.status
        doc.updated_at = utcnow()
        await doc.save(session=session)
        await _audit(
            actor,
            "create",
            "profile_update_requests",
            str(doc.id),
            after=api(doc),
            session=session,
        )
    return api(doc)


async def get_profile_update(actor: Actor, request_id: str) -> dict[str, Any]:
    doc = await TenantRepo(ProfileUpdateRequest, actor).get(request_id)
    if not await _profile_visible(actor, doc):
        raise _missing()
    return api(doc)


async def update_profile_update(
    actor: Actor,
    request_id: str,
    body: ProfileUpdateEdit,
) -> dict[str, Any]:
    doc = await TenantRepo(ProfileUpdateRequest, actor).get(request_id)
    if not await _profile_visible(actor, doc):
        raise _missing()
    if doc.status != "pending":
        raise AppError("conflict", "This request is already finished", 409)
    if not actor.has("employees.manage") and doc.created_by != actor.user_id:
        raise _missing()
    employee = await _for_write(actor, doc.employee_id)
    before = api(doc)
    doc.changes = _clean_changes(employee, body.changes)
    doc.updated_at = utcnow()
    doc.updated_by = actor.user_id
    await doc.save()
    await _audit(
        actor,
        "update",
        "profile_update_requests",
        str(doc.id),
        before=before,
        after=api(doc),
    )
    return api(doc)


async def delete_profile_update(actor: Actor, request_id: str) -> None:
    doc = await TenantRepo(ProfileUpdateRequest, actor).get(request_id)
    if not await _profile_visible(actor, doc):
        raise _missing()
    if doc.status != "pending":
        raise AppError("conflict", "This request is already finished", 409)
    if not actor.has("employees.manage") and doc.created_by != actor.user_id:
        raise _missing()
    before = api(doc)
    await doc.delete()
    await _audit(actor, "delete", "profile_update_requests", str(doc.id), before=before)
