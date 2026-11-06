"""Tenant-scoped reads and writes. Collection access stays behind this module."""

from __future__ import annotations

from typing import Any

from beanie import Document
from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession

from app.core.actor import Actor
from app.core.clock import utcnow
from app.core.errors import AppError
from app.core.pagination import sort_pairs

_BLOCKED = {
    "id",
    "_id",
    "company_id",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "deleted_at",
    "revision",
}


def api(doc: Document) -> dict[str, Any]:
    data = doc.model_dump(mode="json")
    data["id"] = str(doc.id)
    return data


def guard_keys(payload: dict[str, Any]) -> dict[str, Any]:
    for key in payload:
        if key.startswith("$") or key.startswith("."):
            raise AppError("bad_field", "Illegal field name", 400)
    return {key: value for key, value in payload.items() if key not in _BLOCKED}


class TenantRepo:
    def __init__(self, model: type[Document], actor: Actor) -> None:
        self.model = model
        self.actor = actor

    def scoped(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.actor.company_id:
            raise AppError("company_required", "Choose a company first", 400)
        query: dict[str, Any] = {"company_id": self.actor.company_id}
        if "deleted_at" in self.model.model_fields:
            query["deleted_at"] = None
        if extra:
            query.update(extra)
        return query

    async def get(self, doc_id: str, session: AsyncClientSession | None = None) -> Document:
        doc = await self.model.get(doc_id, session=session)
        if doc is None or not self._visible(doc):
            raise AppError("not_found", "Record not found", 404)
        return doc

    def _visible(self, doc: Document) -> bool:
        company_id = getattr(doc, "company_id", None)
        if company_id is None:
            return self.actor.is_superadmin
        if company_id != self.actor.company_id:
            return False
        deleted = getattr(doc, "deleted_at", None)
        return deleted is None

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        search_fields: tuple[str, ...],
        sort_fields: set[str],
        q: str | None,
        sort: str | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = self.scoped(extra)
        if q and search_fields:
            query["$or"] = [{field: {"$regex": q, "$options": "i"}} for field in search_fields]
        total = await self.model.find(query).count()
        cursor = self.model.find(query).sort(sort_pairs(sort, sort_fields))
        items = await cursor.skip((page - 1) * page_size).limit(page_size).to_list()
        return {
            "items": [api(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def create(
        self, payload: BaseModel, session: AsyncClientSession | None = None
    ) -> Document:
        data = guard_keys(payload.model_dump())
        data["company_id"] = self.actor.company_id
        data["created_by"] = self.actor.user_id
        data["updated_by"] = self.actor.user_id
        doc = self.model(**data)
        await doc.insert(session=session)
        await self._audit("create", doc, None, session)
        return doc

    async def update(
        self,
        doc_id: str,
        payload: BaseModel,
        session: AsyncClientSession | None = None,
    ) -> Document:
        doc = await self.get(doc_id, session=session)
        before = api(doc)
        data = guard_keys(payload.model_dump(exclude_unset=True))
        revision = getattr(payload, "revision", None)
        if "revision" in self.model.model_fields:
            if revision is None or revision != doc.revision:  # type: ignore[attr-defined]
                raise AppError("conflict", "This record changed. Reload and try again.", 409)
            data["revision"] = revision + 1
        for key, value in data.items():
            setattr(doc, key, value)
        doc.updated_at = utcnow()  # type: ignore[attr-defined]
        doc.updated_by = self.actor.user_id  # type: ignore[attr-defined]
        await doc.save(session=session)
        await self._audit("update", doc, before, session)
        return doc

    async def soft_delete(self, doc_id: str) -> None:
        doc = await self.get(doc_id)
        if "deleted_at" not in self.model.model_fields:
            raise AppError("bad_request", "This record cannot be deleted", 400)
        before = api(doc)
        doc.deleted_at = utcnow()  # type: ignore[attr-defined]
        doc.updated_at = utcnow()  # type: ignore[attr-defined]
        doc.updated_by = self.actor.user_id  # type: ignore[attr-defined]
        await doc.save()
        await self._audit("delete", doc, before, None)

    async def _audit(
        self,
        action: str,
        doc: Document,
        before: dict[str, Any] | None,
        session: AsyncClientSession | None,
    ) -> None:
        from app.shared.audit import write_audit

        await write_audit(
            company_id=self.actor.company_id,
            actor_id=self.actor.user_id,
            action=action,
            entity_type=self.model.get_collection_name(),
            entity_id=str(doc.id),
            before=before,
            after=api(doc),
            session=session,
        )
