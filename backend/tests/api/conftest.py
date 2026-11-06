"""API tests use the local HRIS replica set. Each run gets its own database."""

from __future__ import annotations

import httpx
import pytest
from app.core.config import get_settings
from app.core.db import close_db, collect_documents, get_client, init_db
from app.main import app

get_settings.cache_clear()


@pytest.fixture
async def client():
    await init_db(collect_documents())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await get_client().drop_database(get_settings().mongo_db)
    await close_db()


def csrf(http: httpx.AsyncClient) -> dict[str, str]:
    token = http.cookies.get("hris_csrf")
    assert token, "login did not set the CSRF cookie"
    return {"x-csrf-token": token}
