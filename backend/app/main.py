"""FastAPI application factory."""

from __future__ import annotations

import importlib
import logging
import pkgutil
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.db import close_db, collect_documents, get_client, import_services, init_db
from app.core.errors import error_body, register_error_handlers

logger = logging.getLogger("hris")

_CSRF_EXEMPT = {
    "/api/v1/auth/login",
    "/api/v1/auth/2fa/verify",
    "/api/v1/auth/password/forgot",
    "/api/v1/auth/password/reset",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            path = request.url.path
            public = path.startswith("/api/v1/public/")
            if path.startswith("/api/") and path not in _CSRF_EXEMPT and not public:
                cookie = request.cookies.get("hris_csrf") or ""
                header = request.headers.get("x-csrf-token") or ""
                if not cookie or not header or not secrets.compare_digest(cookie, header):
                    return JSONResponse(
                        status_code=403,
                        content=error_body("csrf", "CSRF token missing"),
                    )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response


def _include_routers(application: FastAPI) -> None:
    import app.modules
    from app.modules.identity.router import router as identity_router
    from app.shared.router import router as shared_router

    application.include_router(identity_router, prefix="/api/v1")
    application.include_router(shared_router, prefix="/api/v1")
    for info in pkgutil.walk_packages(app.modules.__path__, "app.modules."):
        if not info.name.endswith(".router") or info.name.endswith("identity.router"):
            continue
        module = importlib.import_module(info.name)
        found = getattr(module, "router", None)
        if found is not None:
            application.include_router(found, prefix="/api/v1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import_services()
    await init_db(collect_documents())
    yield
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="HRIS", version="0.1.0", lifespan=lifespan)
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    _include_routers(app)

    @app.get("/health")
    async def health() -> dict:
        mongo = "ok"
        try:
            await get_client().admin.command("ping")
        except Exception:
            mongo = "down"
        redis_state = "down"
        try:
            from redis.asyncio import Redis

            client = Redis.from_url(settings.redis_url)
            await client.ping()
            redis_state = "ok"
            await client.aclose()
        except Exception:
            redis_state = "down"
        return {"ok": mongo == "ok", "mongo": mongo, "redis": redis_state, "storage": "local"}

    return app


app = create_app()
