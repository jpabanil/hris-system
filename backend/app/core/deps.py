"""FastAPI dependencies. Services never import this module."""

from __future__ import annotations

from fastapi import Depends, Request

from app.core.actor import Actor
from app.core.errors import AppError
from app.core.security import decode_token
from app.modules.identity.models import User
from app.modules.identity.service import ACCESS, to_actor


async def get_actor(request: Request) -> Actor:
    token = request.cookies.get(ACCESS)
    if not token:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
    if not token:
        raise AppError("unauthorized", "Sign in required", 401)
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AppError("unauthorized", "Sign in required", 401)
    user = await User.get(payload.get("sub"))
    if user is None or not user.is_active:
        raise AppError("unauthorized", "Sign in required", 401)
    company_override = request.headers.get("x-company-id")
    actor = await to_actor(
        user,
        impersonator_id=payload.get("impersonator_id"),
        company_override=company_override,
    )
    request.state.actor = actor
    return actor


def require(*permissions: str):
    async def checker(actor: Actor = Depends(get_actor)) -> Actor:
        for permission in permissions:
            actor.require(permission)
        return actor

    return checker
