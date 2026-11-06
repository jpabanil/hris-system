"""Money helpers. Floats are rejected. Rounding is half up to the centavo."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

CENT = Decimal("0.01")
FOUR = Decimal("0.0001")


def D(value: object) -> Decimal:
    """Parse a money-safe value. Floats are refused so binary fractions cannot leak in."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("float is not allowed for money or pay hours")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("empty money value")
        return Decimal(text)
    # Decimal128 and similar expose to_decimal().
    to_decimal = getattr(value, "to_decimal", None)
    if callable(to_decimal):
        parsed = to_decimal()
        if isinstance(parsed, Decimal):
            return parsed
    raise TypeError(f"unsupported money value {type(value).__name__}")


def money(value: object) -> Decimal:
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def rate(value: object) -> Decimal:
    return D(value).quantize(FOUR, rounding=ROUND_HALF_UP)


def money_str(value: Decimal) -> str:
    return format(money(value), "f")


Money = Annotated[
    Decimal,
    BeforeValidator(lambda v: money(v)),
    PlainSerializer(money_str, return_type=str, when_used="json"),
]
Rate = Annotated[
    Decimal,
    BeforeValidator(lambda v: rate(v)),
    PlainSerializer(lambda v: format(rate(v), "f"), return_type=str, when_used="json"),
]
