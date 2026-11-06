"""Login, refresh rotation, 2FA, and impersonation."""

from __future__ import annotations

import secrets
from datetime import timedelta

import pyotp
from fastapi import Response

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.errors import AppError
from app.core.permissions import PERMISSIONS
from app.core.repository import api
from app.core.security import (
    decode_token,
    encode_token,
    hash_password,
    hash_token,
    new_csrf,
    new_refresh,
    verify_password,
)
from app.modules.identity.models import LoginHistory, PasswordReset, RefreshToken, Role, User
from app.shared.audit import write_audit
from app.shared.notify import send_email

ACCESS = "hris_access"
REFRESH = "hris_refresh"
CSRF = "hris_csrf"


def _cookie(response: Response, name: str, value: str, *, max_age: int, http_only: bool) -> None:
    settings = get_settings()
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=http_only,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _clear(response: Response) -> None:
    for name in (ACCESS, REFRESH, CSRF):
        response.delete_cookie(name, path="/")


async def permissions_for(user: User) -> tuple[set[str], list[str]]:
    if user.is_superadmin:
        return set(PERMISSIONS), ["Super Admin"]
    if not user.role_ids:
        return set(), []
    from beanie import PydanticObjectId

    ids: list[PydanticObjectId] = []
    for raw in user.role_ids:
        try:
            ids.append(PydanticObjectId(raw))
        except Exception:
            continue
    roles = await Role.find({"_id": {"$in": ids}}).to_list() if ids else []
    names = [role.name for role in roles]
    keys: set[str] = set()
    for role in roles:
        keys.update(role.permission_keys)
    return keys, names


async def to_actor(
    user: User, *, impersonator_id: str | None = None, company_override: str | None = None
) -> Actor:
    keys, names = await permissions_for(user)
    company_id = user.company_id
    if user.is_superadmin and company_override:
        company_id = company_override
    return Actor(
        user_id=str(user.id),
        email=user.email,
        company_id=company_id,
        permissions=keys,
        employee_id=user.employee_id,
        role_names=names,
        is_superadmin=user.is_superadmin,
        is_impersonating=impersonator_id is not None,
        impersonator_id=impersonator_id,
        branch_access=list(user.branch_access),
    )


async def public_me(actor: Actor) -> dict:
    user = await User.get(actor.user_id)
    if user is None:
        raise AppError("unauthorized", "Session is not valid", 401)
    return {
        "id": str(user.id),
        "email": user.email,
        "company_id": actor.company_id,
        "employee_id": user.employee_id,
        "permissions": sorted(actor.permissions if not actor.is_superadmin else actor.permissions),
        "roles": actor.role_names,
        "is_superadmin": user.is_superadmin,
        "is_impersonating": actor.is_impersonating,
        "impersonator_id": actor.impersonator_id,
        "locale": user.locale,
        "must_change_password": user.must_change_password,
        "totp_enabled": user.totp_enabled,
    }


async def _history(
    email: str, success: bool, user_id: str | None, ip: str | None, agent: str | None
) -> None:
    await LoginHistory(
        user_id=user_id,
        email=email,
        success=success,
        ip=ip,
        user_agent=agent,
        at=utcnow(),
    ).insert()


async def issue_session(
    response: Response, user: User, *, impersonator_id: str | None = None
) -> str:
    settings = get_settings()
    csrf = new_csrf()
    access = encode_token(
        {
            "sub": str(user.id),
            "type": "access",
            "impersonator_id": impersonator_id,
            "csrf": csrf,
        },
        minutes=settings.access_token_minutes,
    )
    refresh = new_refresh()
    family = secrets.token_hex(8)
    await RefreshToken(
        user_id=str(user.id),
        family_id=family,
        token_hash=hash_token(refresh),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        created_at=utcnow(),
    ).insert()
    _cookie(response, ACCESS, access, max_age=settings.access_token_minutes * 60, http_only=True)
    _cookie(response, REFRESH, refresh, max_age=settings.refresh_token_days * 86400, http_only=True)
    _cookie(response, CSRF, csrf, max_age=settings.refresh_token_days * 86400, http_only=False)
    return csrf


async def login(
    response: Response, email: str, password: str, ip: str | None, agent: str | None
) -> dict:
    settings = get_settings()
    user = await User.find_one(User.email == email.lower().strip())
    if user and user.locked_until and user.locked_until > utcnow():
        await _history(email, False, str(user.id), ip, agent)
        raise AppError("locked", "Account is locked. Try again later.", 423)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.lockout_attempts:
                user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
            await user.save()
            await _history(email, False, str(user.id), ip, agent)
        else:
            await _history(email, False, None, ip, agent)
        raise AppError("unauthorized", "Email or password is incorrect", 401)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    await user.save()
    await _history(email, True, str(user.id), ip, agent)
    if user.totp_enabled:
        token = encode_token(
            {"sub": str(user.id), "type": "mfa"}, minutes=settings.mfa_token_minutes
        )
        return {"mfa_required": True, "mfa_token": token}
    await issue_session(response, user)
    actor = await to_actor(user)
    return {"mfa_required": False, "user": await public_me(actor)}


async def verify_2fa(response: Response, mfa_token: str, code: str) -> dict:
    payload = decode_token(mfa_token)
    if payload.get("type") != "mfa":
        raise AppError("unauthorized", "Session is not valid", 401)
    user = await User.get(payload["sub"])
    if user is None or not user.totp_secret:
        raise AppError("unauthorized", "Session is not valid", 401)
    secret = decrypt(user.totp_secret)
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise AppError("unauthorized", "That code is not valid", 401)
    await issue_session(response, user)
    actor = await to_actor(user)
    return {"user": await public_me(actor)}


async def begin_2fa(user: User) -> dict:
    secret = pyotp.random_base32()
    user.totp_secret = encrypt(secret)
    user.totp_enabled = False
    await user.save()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="HRIS")
    return {"secret": secret, "otpauth_url": uri}


async def enable_2fa(user: User, code: str) -> None:
    if not user.totp_secret:
        raise AppError("bad_request", "Start 2FA setup first", 400)
    if not pyotp.TOTP(decrypt(user.totp_secret)).verify(code, valid_window=1):
        raise AppError("unauthorized", "That code is not valid", 401)
    user.totp_enabled = True
    await user.save()


async def refresh(response: Response, raw_token: str | None) -> None:
    if not raw_token:
        raise AppError("unauthorized", "Refresh token missing", 401)
    settings = get_settings()
    stored = await RefreshToken.find_one(RefreshToken.token_hash == hash_token(raw_token))
    if stored is None or stored.expires_at < utcnow():
        raise AppError("unauthorized", "Refresh token is not valid", 401)
    if stored.revoked_at is not None:
        await RefreshToken.find({"family_id": stored.family_id}).update(
            {"$set": {"revoked_at": utcnow()}}
        )
        raise AppError("unauthorized", "Refresh token was already used", 401)
    user = await User.get(stored.user_id)
    if user is None or not user.is_active:
        raise AppError("unauthorized", "Session is not valid", 401)
    stored.revoked_at = utcnow()
    replacement = new_refresh()
    stored.replaced_by = hash_token(replacement)
    await stored.save()
    await RefreshToken(
        user_id=str(user.id),
        family_id=stored.family_id,
        token_hash=hash_token(replacement),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        created_at=utcnow(),
    ).insert()
    csrf = new_csrf()
    access = encode_token(
        {"sub": str(user.id), "type": "access", "csrf": csrf},
        minutes=settings.access_token_minutes,
    )
    _cookie(response, ACCESS, access, max_age=settings.access_token_minutes * 60, http_only=True)
    _cookie(
        response,
        REFRESH,
        replacement,
        max_age=settings.refresh_token_days * 86400,
        http_only=True,
    )
    _cookie(response, CSRF, csrf, max_age=settings.refresh_token_days * 86400, http_only=False)


async def logout(response: Response, raw_token: str | None) -> None:
    if raw_token:
        stored = await RefreshToken.find_one(RefreshToken.token_hash == hash_token(raw_token))
        if stored is not None:
            stored.revoked_at = utcnow()
            await stored.save()
    _clear(response)


async def forgot_password(email: str) -> dict:
    user = await User.find_one(User.email == email.lower().strip())
    token = secrets.token_urlsafe(24)
    if user is not None:
        await PasswordReset(
            user_id=str(user.id),
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(hours=2),
        ).insert()
        await send_email(user.email, "Reset your HRIS password", f"Reset token: {token}")
    body: dict = {"ok": True}
    if get_settings().env != "production" and user is not None:
        body["reset_token"] = token
    return body


async def reset_password(token: str, password: str) -> None:
    if len(password) < 10:
        raise AppError("validation_error", "Password must be at least 10 characters", 422)
    stored = await PasswordReset.find_one(PasswordReset.token_hash == hash_token(token))
    if stored is None or stored.used_at is not None or stored.expires_at < utcnow():
        raise AppError("bad_token", "Reset token is not valid", 400)
    user = await User.get(stored.user_id)
    if user is None:
        raise AppError("bad_token", "Reset token is not valid", 400)
    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    await user.save()
    stored.used_at = utcnow()
    await stored.save()


async def impersonate(response: Response, actor: Actor, user_id: str) -> dict:
    if not actor.is_superadmin or actor.is_impersonating:
        raise AppError("forbidden", "Only a super admin can impersonate", 403)
    user = await User.get(user_id)
    if user is None or user.is_superadmin:
        raise AppError("not_found", "User not found", 404)
    await issue_session(response, user, impersonator_id=actor.user_id)
    await write_audit(
        company_id=user.company_id,
        actor_id=actor.user_id,
        action="impersonate",
        entity_type="users",
        entity_id=str(user.id),
        after={"email": user.email},
    )
    target = await to_actor(user, impersonator_id=actor.user_id)
    return await public_me(target)


def block_payroll_if_impersonating(actor: Actor) -> None:
    if actor.is_impersonating:
        raise AppError("forbidden", "Payroll actions are blocked while impersonating", 403)


def role_api(role: Role) -> dict:
    data = api(role)
    data["permission_keys"] = list(role.permission_keys)
    return data
