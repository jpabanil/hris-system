"""Mongo connection, Decimal128 codec, and multi-document transactions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from decimal import Decimal

from beanie import Document, init_beanie
from bson import Decimal128
from bson.codec_options import CodecOptions, TypeCodec, TypeRegistry
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.config import get_settings

_client: AsyncMongoClient | None = None


class _DecimalCodec(TypeCodec):
    python_type = Decimal
    bson_type = Decimal128

    def transform_python(self, value: Decimal) -> Decimal128:
        return Decimal128(str(value))

    def transform_bson(self, value: Decimal128) -> Decimal:
        return value.to_decimal()


def get_client() -> AsyncMongoClient:
    if _client is None:
        raise RuntimeError("database is not initialized")
    return _client


async def init_db(models: list[type[Document]], *, database: str | None = None) -> None:
    global _client
    settings = get_settings()
    _client = AsyncMongoClient(settings.mongo_uri)
    options = CodecOptions(tz_aware=True, tzinfo=UTC, type_registry=TypeRegistry([_DecimalCodec()]))
    db = _client.get_database(database or settings.mongo_db, codec_options=options)
    await init_beanie(database=db, document_models=models)


async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


@asynccontextmanager
async def transaction() -> AsyncIterator[AsyncClientSession]:
    client = get_client()
    async with client.start_session() as session:
        async with await session.start_transaction():
            yield session


def collect_documents() -> list[type[Document]]:
    """Import every module models.py and return its Beanie documents."""
    import importlib
    import pkgutil

    import app.modules
    import app.shared.models as shared_models

    found: list[type[Document]] = []
    seen: set[str] = set()

    def take(module: object) -> None:
        for obj in vars(module).values():
            if not isinstance(obj, type) or not issubclass(obj, Document):
                continue
            if obj is Document or obj.__module__ != module.__name__:
                continue
            # Beanie only fills collection settings during init_beanie.
            meta = getattr(obj, "Settings", None)
            name = getattr(meta, "name", None) or obj.__name__
            if name not in seen:
                seen.add(name)
                found.append(obj)

    take(shared_models)
    for info in pkgutil.walk_packages(app.modules.__path__, "app.modules."):
        if info.name.endswith(".models"):
            take(importlib.import_module(info.name))
    return found


def import_services() -> None:
    import importlib
    import pkgutil

    import app.modules

    for info in pkgutil.walk_packages(app.modules.__path__, "app.modules."):
        if info.name.endswith(".service") or info.name.endswith(".tasks"):
            importlib.import_module(info.name)
