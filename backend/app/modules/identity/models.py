from __future__ import annotations

from datetime import datetime

from beanie import Document, Indexed
from pymongo import IndexModel

from app.core.models import AuditMixin


class Role(AuditMixin, Document):
    company_id: str | None = None
    name: str
    permission_keys: list[str] = []

    class Settings:
        name = "roles"
        indexes = [IndexModel([("company_id", 1), ("name", 1)], unique=True)]


class User(AuditMixin, Document):
    email: Indexed(str, unique=True)
    password_hash: str
    is_active: bool = True
    last_login_at: datetime | None = None
    totp_secret: str | None = None
    totp_enabled: bool = False
    locale: str = "en"
    failed_login_count: int = 0
    locked_until: datetime | None = None
    role_ids: list[str] = []
    branch_access: list[str] = []
    employee_id: str | None = None
    company_id: str | None = None
    must_change_password: bool = False
    is_superadmin: bool = False

    class Settings:
        name = "users"


class RefreshToken(Document):
    user_id: str
    family_id: str
    token_hash: Indexed(str, unique=True)
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by: str | None = None
    created_at: datetime

    class Settings:
        name = "refresh_tokens"
        indexes = [IndexModel([("expires_at", 1)], expireAfterSeconds=0)]


class LoginHistory(Document):
    user_id: str | None = None
    email: str
    success: bool
    ip: str | None = None
    user_agent: str | None = None
    at: datetime

    class Settings:
        name = "login_history"
        indexes = [IndexModel([("user_id", 1), ("at", -1)])]


class PasswordReset(Document):
    user_id: str
    token_hash: Indexed(str, unique=True)
    expires_at: datetime
    used_at: datetime | None = None

    class Settings:
        name = "password_resets"
        indexes = [IndexModel([("expires_at", 1)], expireAfterSeconds=0)]
