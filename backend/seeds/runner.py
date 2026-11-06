"""Load the demo company. The full dataset is filled in by `seed`."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.db import close_db, collect_documents, get_client, init_db


async def run(*, fresh: bool) -> None:
    settings = get_settings()
    await init_db(collect_documents())
    if fresh:
        await get_client().drop_database(settings.mongo_db)
        await init_db(collect_documents())
    from seeds.demo import seed

    await seed()
    await close_db()
