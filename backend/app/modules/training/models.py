from __future__ import annotations

from datetime import date as Date

from beanie import Document
from pymongo import IndexModel

from app.core.models import AuditMixin, MoneyField, TenantMixin


class Training(AuditMixin, TenantMixin, Document):
    title: str
    provider: str = ""
    type: str = "internal"
    date: Date | None = None
    hours: str = "0"
    cost: MoneyField = "0"

    class Settings:
        name = "trainings"
        indexes = [IndexModel([("company_id", 1), ("date", -1)])]


class TrainingAttendee(AuditMixin, TenantMixin, Document):
    training_id: str
    employee_id: str
    status: str = "enrolled"
    certificate_key: str | None = None

    class Settings:
        name = "training_attendees"
        indexes = [
            IndexModel(
                [("company_id", 1), ("training_id", 1), ("employee_id", 1)],
                unique=True,
            )
        ]


class TrainingBond(AuditMixin, TenantMixin, Document):
    employee_id: str
    training_id: str
    amount: MoneyField
    bond_until: Date

    class Settings:
        name = "training_bonds"
        indexes = [IndexModel([("company_id", 1), ("employee_id", 1)])]
