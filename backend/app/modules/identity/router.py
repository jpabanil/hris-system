from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from app.core.actor import Actor
from app.core.deps import get_actor, require
from app.core.permissions import PERMISSIONS
from app.modules.identity.models import User
from app.modules.identity.service import (
    begin_2fa,
    enable_2fa,
    forgot_password,
    impersonate,
    login,
    logout,
    public_me,
    refresh,
    reset_password,
    verify_2fa,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class MfaBody(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=8)


class EmailBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str
    password: str = Field(min_length=10)


class CodeBody(BaseModel):
    code: str


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login")
async def login_route(body: LoginBody, request: Request, response: Response) -> dict:
    return await login(
        response, body.email, body.password, _ip(request), request.headers.get("user-agent")
    )


@router.post("/logout")
async def logout_route(request: Request, response: Response) -> dict:
    await logout(response, request.cookies.get("hris_refresh"))
    return {"ok": True}


@router.post("/refresh")
async def refresh_route(request: Request, response: Response) -> dict:
    await refresh(response, request.cookies.get("hris_refresh"))
    return {"ok": True}


@router.get("/me")
async def me_route(actor: Actor = Depends(get_actor)) -> dict:
    return await public_me(actor)


@router.post("/2fa/verify")
async def mfa_route(body: MfaBody, response: Response) -> dict:
    return await verify_2fa(response, body.mfa_token, body.code)


@router.post("/2fa/setup")
async def mfa_setup(actor: Actor = Depends(get_actor)) -> dict:
    user = await User.get(actor.user_id)
    return await begin_2fa(user)


@router.post("/2fa/enable")
async def mfa_enable(body: CodeBody, actor: Actor = Depends(get_actor)) -> dict:
    user = await User.get(actor.user_id)
    await enable_2fa(user, body.code)
    return {"ok": True}


@router.post("/password/forgot")
async def forgot_route(body: EmailBody) -> dict:
    return await forgot_password(body.email)


@router.post("/password/reset")
async def reset_route(body: ResetBody) -> dict:
    await reset_password(body.token, body.password)
    return {"ok": True}


@router.post("/impersonate/{user_id}")
async def impersonate_route(
    user_id: str, response: Response, actor: Actor = Depends(get_actor)
) -> dict:
    return await impersonate(response, actor, user_id)


@router.get("/permissions")
async def permissions_route(actor: Actor = Depends(require("users.manage"))) -> dict:
    return {"items": [{"key": key, "label": label} for key, label in sorted(PERMISSIONS.items())]}
