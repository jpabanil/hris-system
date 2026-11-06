from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.modules.attendance.schemas import (
    ClockIn,
    ComputeDayBody,
    CorrectionWrite,
    EmployeeScheduleWrite,
    HolidayWrite,
    ImportPunch,
    OfficialBusinessWrite,
    OvertimeWrite,
    RosterEntryWrite,
    ShiftSwapWrite,
    ShiftWrite,
    WfhWrite,
    WorkScheduleWrite,
)
from app.modules.attendance.service import (
    clock_in,
    compute_day_for,
    create_correction,
    create_employee_schedule,
    create_holiday,
    create_official_business,
    create_overtime,
    create_roster,
    create_shift,
    create_swap,
    create_wfh,
    create_work_schedule,
    delete_correction,
    delete_employee_schedule,
    delete_holiday,
    delete_official_business,
    delete_overtime,
    delete_roster,
    delete_shift,
    delete_swap,
    delete_wfh,
    delete_work_schedule,
    get_correction,
    get_holiday,
    get_official_business,
    get_overtime,
    get_shift,
    get_swap,
    get_wfh,
    get_work_schedule,
    import_punches,
    list_corrections,
    list_days,
    list_employee_schedules,
    list_holidays,
    list_official_business,
    list_overtime,
    list_roster,
    list_shifts,
    list_swaps,
    list_wfh,
    list_work_schedules,
    update_correction,
    update_employee_schedule,
    update_holiday,
    update_official_business,
    update_overtime,
    update_roster,
    update_shift,
    update_swap,
    update_wfh,
    update_work_schedule,
)

router = APIRouter(tags=["attendance"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/work-schedules")
async def work_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    sort: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_work_schedules(actor, page, page_size, q, sort)


@router.post("/work-schedules", status_code=201)
async def work_schedules_create(
    body: WorkScheduleWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await create_work_schedule(actor, body)


@router.get("/work-schedules/{schedule_id}")
async def work_schedules_get(schedule_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_work_schedule(actor, schedule_id)


@router.put("/work-schedules/{schedule_id}")
async def work_schedules_update(
    schedule_id: str, body: WorkScheduleWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await update_work_schedule(actor, schedule_id, body)


@router.delete("/work-schedules/{schedule_id}", status_code=204)
async def work_schedules_delete(
    schedule_id: str, actor: Actor = Depends(require("attendance.manage"))
) -> Response:
    await delete_work_schedule(actor, schedule_id)
    return Response(status_code=204)


@router.get("/shifts")
async def shifts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    sort: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_shifts(actor, page, page_size, q, sort)


@router.post("/shifts", status_code=201)
async def shifts_create(
    body: ShiftWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await create_shift(actor, body)


@router.get("/shifts/{shift_id}")
async def shifts_get(shift_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_shift(actor, shift_id)


@router.put("/shifts/{shift_id}")
async def shifts_update(
    shift_id: str, body: ShiftWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await update_shift(actor, shift_id, body)


@router.delete("/shifts/{shift_id}", status_code=204)
async def shifts_delete(
    shift_id: str, actor: Actor = Depends(require("attendance.manage"))
) -> Response:
    await delete_shift(actor, shift_id)
    return Response(status_code=204)


@router.get("/roster-entries")
async def roster_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    employee_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_roster(actor, page, page_size, employee_id, start, end)


@router.post("/roster-entries", status_code=201)
async def roster_entries_create(
    body: RosterEntryWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await create_roster(actor, body)


@router.put("/roster-entries/{entry_id}")
async def roster_entries_update(
    entry_id: str, body: RosterEntryWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await update_roster(actor, entry_id, body)


@router.delete("/roster-entries/{entry_id}", status_code=204)
async def roster_entries_delete(
    entry_id: str, actor: Actor = Depends(require("attendance.manage"))
) -> Response:
    await delete_roster(actor, entry_id)
    return Response(status_code=204)


@router.get("/holidays")
async def holidays(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    sort: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_holidays(actor, page, page_size, q, sort)


@router.post("/holidays", status_code=201)
async def holidays_create(
    body: HolidayWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await create_holiday(actor, body)


@router.get("/holidays/{holiday_id}")
async def holidays_get(holiday_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_holiday(actor, holiday_id)


@router.put("/holidays/{holiday_id}")
async def holidays_update(
    holiday_id: str, body: HolidayWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await update_holiday(actor, holiday_id, body)


@router.delete("/holidays/{holiday_id}", status_code=204)
async def holidays_delete(
    holiday_id: str, actor: Actor = Depends(require("attendance.manage"))
) -> Response:
    await delete_holiday(actor, holiday_id)
    return Response(status_code=204)


@router.get("/employee-schedules")
async def employee_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    employee_id: str | None = None,
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_employee_schedules(actor, page, page_size, employee_id)


@router.post("/employee-schedules", status_code=201)
async def employee_schedules_create(
    body: EmployeeScheduleWrite, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await create_employee_schedule(actor, body)


@router.put("/employee-schedules/{schedule_id}")
async def employee_schedules_update(
    schedule_id: str,
    body: EmployeeScheduleWrite,
    actor: Actor = Depends(require("attendance.manage")),
) -> dict:
    return await update_employee_schedule(actor, schedule_id, body)


@router.delete("/employee-schedules/{schedule_id}", status_code=204)
async def employee_schedules_delete(
    schedule_id: str, actor: Actor = Depends(require("attendance.manage"))
) -> Response:
    await delete_employee_schedule(actor, schedule_id)
    return Response(status_code=204)


@router.post("/attendance/clock")
async def attendance_clock(
    body: ClockIn, request: Request, actor: Actor = Depends(get_actor)
) -> dict:
    return await clock_in(actor, body, request.headers.get("idempotency-key", ""), _ip(request))


@router.post("/attendance/import")
async def attendance_import(
    body: list[ImportPunch], actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await import_punches(actor, body)


@router.get("/attendance/days")
async def attendance_days(
    employee_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_days(actor, employee_id, start, end, page, page_size)


@router.post("/attendance/days/compute")
async def attendance_days_compute(
    body: ComputeDayBody, actor: Actor = Depends(require("attendance.manage"))
) -> dict:
    return await compute_day_for(actor, body.employee_id, body.date)


@router.get("/overtime-requests")
async def overtime_requests(
    employee_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_overtime(actor, employee_id, page, page_size)


@router.post("/overtime-requests", status_code=201)
async def overtime_requests_create(body: OvertimeWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_overtime(actor, body)


@router.get("/overtime-requests/{request_id}")
async def overtime_requests_get(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_overtime(actor, request_id)


@router.put("/overtime-requests/{request_id}")
async def overtime_requests_update(
    request_id: str, body: OvertimeWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await update_overtime(actor, request_id, body)


@router.delete("/overtime-requests/{request_id}", status_code=204)
async def overtime_requests_delete(request_id: str, actor: Actor = Depends(get_actor)) -> Response:
    await delete_overtime(actor, request_id)
    return Response(status_code=204)


@router.get("/attendance-corrections")
async def attendance_corrections(
    employee_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_corrections(actor, employee_id, page, page_size)


@router.post("/attendance-corrections", status_code=201)
async def attendance_corrections_create(
    body: CorrectionWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await create_correction(actor, body)


@router.get("/attendance-corrections/{request_id}")
async def attendance_corrections_get(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_correction(actor, request_id)


@router.put("/attendance-corrections/{request_id}")
async def attendance_corrections_update(
    request_id: str, body: CorrectionWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await update_correction(actor, request_id, body)


@router.delete("/attendance-corrections/{request_id}", status_code=204)
async def attendance_corrections_delete(
    request_id: str, actor: Actor = Depends(get_actor)
) -> Response:
    await delete_correction(actor, request_id)
    return Response(status_code=204)


@router.get("/official-business")
async def official_business(
    employee_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_official_business(actor, employee_id, page, page_size)


@router.post("/official-business", status_code=201)
async def official_business_create(
    body: OfficialBusinessWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await create_official_business(actor, body)


@router.get("/official-business/{request_id}")
async def official_business_get(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_official_business(actor, request_id)


@router.put("/official-business/{request_id}")
async def official_business_update(
    request_id: str, body: OfficialBusinessWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await update_official_business(actor, request_id, body)


@router.delete("/official-business/{request_id}", status_code=204)
async def official_business_delete(request_id: str, actor: Actor = Depends(get_actor)) -> Response:
    await delete_official_business(actor, request_id)
    return Response(status_code=204)


@router.get("/wfh-requests")
async def wfh_requests(
    employee_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_wfh(actor, employee_id, page, page_size)


@router.post("/wfh-requests", status_code=201)
async def wfh_requests_create(body: WfhWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_wfh(actor, body)


@router.get("/wfh-requests/{request_id}")
async def wfh_requests_get(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_wfh(actor, request_id)


@router.put("/wfh-requests/{request_id}")
async def wfh_requests_update(
    request_id: str, body: WfhWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await update_wfh(actor, request_id, body)


@router.delete("/wfh-requests/{request_id}", status_code=204)
async def wfh_requests_delete(request_id: str, actor: Actor = Depends(get_actor)) -> Response:
    await delete_wfh(actor, request_id)
    return Response(status_code=204)


@router.get("/shift-swaps")
async def shift_swaps(
    employee_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Actor = Depends(get_actor),
) -> dict:
    return await list_swaps(actor, employee_id, page, page_size)


@router.post("/shift-swaps", status_code=201)
async def shift_swaps_create(body: ShiftSwapWrite, actor: Actor = Depends(get_actor)) -> dict:
    return await create_swap(actor, body)


@router.get("/shift-swaps/{request_id}")
async def shift_swaps_get(request_id: str, actor: Actor = Depends(get_actor)) -> dict:
    return await get_swap(actor, request_id)


@router.put("/shift-swaps/{request_id}")
async def shift_swaps_update(
    request_id: str, body: ShiftSwapWrite, actor: Actor = Depends(get_actor)
) -> dict:
    return await update_swap(actor, request_id, body)


@router.delete("/shift-swaps/{request_id}", status_code=204)
async def shift_swaps_delete(request_id: str, actor: Actor = Depends(get_actor)) -> Response:
    await delete_swap(actor, request_id)
    return Response(status_code=204)
