"""Internal helpers for immutable, transport-neutral structured data."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType


def freeze_safe_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return an immutable copy containing only neutral data values."""
    frozen: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("structured data keys must be strings")
        frozen[key] = _freeze_safe_value(item)
    return MappingProxyType(frozen)


def _freeze_safe_value(value: object) -> object:
    if isinstance(value, BaseException):
        raise TypeError("raw exceptions are not safe contract data")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return freeze_safe_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_safe_value(item) for item in value)
    raise TypeError(f"unsupported structured data value: {type(value).__name__}")
