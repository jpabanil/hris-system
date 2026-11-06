"""Atomic document numbers. The counter row is incremented with find_one_and_update."""

from __future__ import annotations

from pymongo import ReturnDocument

from app.shared.models import Counter


async def next_number(company_id: str, key: str, prefix: str) -> str:
    collection = Counter.get_pymongo_collection()
    row = await collection.find_one_and_update(
        {"company_id": company_id, "key": key},
        {"$inc": {"value": 1}, "$setOnInsert": {"company_id": company_id, "key": key}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    value = int(row["value"])
    return f"{prefix}{value:05d}"
