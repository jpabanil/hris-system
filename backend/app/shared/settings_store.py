"""Typed company settings. Stored values override the defaults in code."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.actor import Actor
from app.core.clock import utcnow
from app.shared.audit import write_audit
from app.shared.models import SettingDoc


class PayrollSettings(BaseModel):
    contribution_timing: str = "split"
    factor_days_per_year: int = 261
    periods_guard: str = "never-negative"
    deduction_order: list[str] = Field(
        default_factory=lambda: [
            "sss",
            "philhealth",
            "pagibig",
            "tax",
            "sss_loan",
            "pagibig_loan",
            "company_loan",
            "cash_advance",
            "recurring",
            "other",
        ]
    )
    variance_threshold: Decimal = Decimal("0.20")
    thirteenth_month_nontax_ceiling: Decimal = Decimal("90000")
    payslip_password_pattern: str = "{employee_no}{birth_mmdd}"
    monthly_includes_unworked_holiday: bool = True
    ot_multipliers: dict[str, str] = Field(
        default_factory=lambda: {
            "regular_ot": "1.25",
            "rest_day": "1.30",
            "rest_day_ot": "1.69",
            "special_non_working": "1.30",
            "special_non_working_ot": "1.69",
            "regular_holiday": "2.00",
            "regular_holiday_ot": "2.60",
            "regular_holiday_rest": "2.60",
            "double_regular": "3.00",
            "night_diff": "0.10",
        }
    )


class AttendanceSettings(BaseModel):
    grace_minutes: int = 5
    late_counts_from_schedule_if_beyond_grace: bool = False
    night_start: str = "22:00"
    night_end: str = "06:00"
    ot_rounding_minutes: int = 0
    ot_requires_approval: bool = True
    daily_ot_cap_minutes: int | None = None
    selfie_required: bool = False
    geofence_required: bool = False
    allowed_sources: list[str] = Field(
        default_factory=lambda: ["web", "pwa", "biometric_import", "manual"]
    )


class LeaveSettings(BaseModel):
    min_notice_days_default: int = 3
    accrual_day: int = 1


class GeneralSettings(BaseModel):
    probation_days: int = 180
    resignation_notice_days: int = 30
    final_pay_release_days: int = 30
    portal_access_days_after_separation: int = 365
    approval_escalation_hours: int = 48
    dpo_name: str = ""
    dpo_email: str = ""


class OffboardingSettings(BaseModel):
    nte_response_days: int = 5


SCHEMAS: dict[str, type[BaseModel]] = {
    "payroll": PayrollSettings,
    "attendance": AttendanceSettings,
    "leave": LeaveSettings,
    "general": GeneralSettings,
    "offboarding": OffboardingSettings,
}


async def get_settings_model(company_id: str, module: str) -> BaseModel:
    schema = SCHEMAS[module]
    stored = await SettingDoc.find_one({"company_id": company_id, "module": module})
    if stored is None:
        return schema()
    return schema.model_validate(stored.values)


async def save_settings(actor: Actor, module: str, values: dict[str, Any]) -> BaseModel:
    if not actor.company_id:
        from app.core.errors import AppError

        raise AppError("company_required", "Choose a company first", 400)
    schema = SCHEMAS[module]
    parsed = schema.model_validate(values)
    existing = await SettingDoc.find_one({"company_id": actor.company_id, "module": module})
    before = existing.values if existing else None
    if existing is None:
        existing = SettingDoc(
            company_id=actor.company_id,
            module=module,
            values=parsed.model_dump(mode="json"),
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        await existing.insert()
    else:
        existing.values = parsed.model_dump(mode="json")
        existing.updated_at = utcnow()
        existing.updated_by = actor.user_id
        await existing.save()
    await write_audit(
        company_id=actor.company_id,
        actor_id=actor.user_id,
        action="update",
        entity_type="settings",
        entity_id=module,
        before={"values": before} if before else None,
        after={"values": existing.values},
    )
    return parsed
