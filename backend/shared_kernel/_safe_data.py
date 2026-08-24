"""Internal helpers for immutable, transport-neutral structured data."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef

_SAFE_REFERENCE_TYPES = (
    TypedEntityId,
    TypedEntityRef,
    VersionRef,
    ObjectVersionRef,
    CorrelationId,
)
_FORBIDDEN_KEY_NAMES = frozenset(
    {
        "password",
        "secret",
        "secretconfig",
        "token",
        "authtoken",
        "accesstoken",
        "refreshtoken",
        "bearertoken",
        "apikey",
        "cookie",
        "sql",
        "rawsql",
        "sqlquery",
        "rawsqlquery",
        "connectionstring",
        "stack",
        "stacktrace",
        "providerpayload",
        "filesystempath",
        "localpath",
    }
)


def freeze_safe_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return an immutable copy containing only neutral data values."""
    if not isinstance(value, Mapping):
        raise TypeError("structured data must be a mapping")

    frozen: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("structured data keys must be strings")
        if _is_forbidden_key(key):
            raise ValueError(f"forbidden structured data key: {key}")
        frozen[key] = _freeze_safe_value(item)
    return MappingProxyType(frozen)


def _freeze_safe_value(value: object) -> object:
    if isinstance(value, BaseException):
        raise TypeError("raw exceptions are not safe contract data")
    if isinstance(value, _SAFE_REFERENCE_TYPES):
        return value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return freeze_safe_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_safe_value(item) for item in value)
    raise TypeError(f"unsupported structured data value: {type(value).__name__}")


def _is_forbidden_key(key: str) -> bool:
    normalized = "".join(character for character in key.casefold() if character.isalnum())
    return normalized in _FORBIDDEN_KEY_NAMES
