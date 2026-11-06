"""Payroll documents must not store money or hours as float."""

from __future__ import annotations

import types
import typing
from decimal import Decimal

import pytest
from app.core.money import money
from pydantic import BaseModel


def _leaves(annotation: object) -> list[object]:
    if annotation is None:
        return []
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        return _leaves(typing.get_args(annotation)[0])
    if origin in {typing.Union, types.UnionType, list, dict, tuple, set}:
        found: list[object] = []
        for arg in typing.get_args(annotation):
            if arg is type(None):
                continue
            found.extend(_leaves(arg))
        return found
    return [annotation]


def test_money_rejects_float() -> None:
    with pytest.raises(TypeError):
        money(1.5)
    with pytest.raises(TypeError):
        money(True)
    assert money("10.005") == Decimal("10.01")
    assert money(Decimal("10.004")) == Decimal("10.00")


def test_payroll_models_have_no_float_fields() -> None:
    import app.modules.payroll.models as models

    classes = [
        obj
        for obj in vars(models).values()
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj.__module__ == models.__name__
        )
    ]
    bad: list[str] = []
    seen: set[type] = set()

    def walk(cls: type[BaseModel]) -> None:
        if cls in seen:
            return
        seen.add(cls)
        for name, field in cls.model_fields.items():
            for leaf in _leaves(field.annotation):
                if leaf is float:
                    bad.append(f"{cls.__name__}.{name}")
                elif isinstance(leaf, type) and issubclass(leaf, BaseModel):
                    walk(leaf)

    for cls in classes:
        walk(cls)
    assert bad == []
