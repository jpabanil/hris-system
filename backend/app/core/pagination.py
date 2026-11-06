"""Page pagination with a whitelist of sort fields."""

from __future__ import annotations

from fastapi import Query

from app.core.errors import AppError


def sort_pairs(sort: str | None, allowed: set[str]) -> list[tuple[str, int]]:
    if not sort:
        if "created_at" in allowed:
            return [("created_at", -1)]
        field = sorted(allowed)[0]
        return [(field, 1)]
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    if field not in allowed or field.startswith("$") or "." in field:
        raise AppError("bad_sort", "That sort field is not allowed", 400)
    return [(field, -1 if descending else 1)]


class PageQuery:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
        q: str | None = None,
        sort: str | None = None,
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.q = q
        self.sort = sort
