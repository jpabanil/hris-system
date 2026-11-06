"""The authenticated user, as services see them. Services do not import FastAPI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Actor:
    user_id: str
    email: str
    company_id: str | None
    permissions: set[str] = field(default_factory=set)
    employee_id: str | None = None
    role_names: list[str] = field(default_factory=list)
    is_superadmin: bool = False
    is_impersonating: bool = False
    impersonator_id: str | None = None
    branch_access: list[str] = field(default_factory=list)

    def has(self, permission: str) -> bool:
        return self.is_superadmin or permission in self.permissions

    def require(self, permission: str) -> None:
        from app.core.errors import AppError

        if not self.has(permission):
            raise AppError("forbidden", "You do not have access to this action", 403)
