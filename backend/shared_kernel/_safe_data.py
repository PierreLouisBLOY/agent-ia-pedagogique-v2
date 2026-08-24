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
_AUTHENTICATION_COMPONENTS = frozenset(
    {
        "auth",
        "access",
        "refresh",
        "bearer",
        "oauth",
        "session",
        "credential",
        "credentials",
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
    components = _key_components(key)
    component_set = frozenset(components)

    if component_set.intersection({"password", "secret", "cookie", "sql"}):
        return True
    if {"api", "key"}.issubset(component_set):
        return True
    if components == ("token",):
        return True
    if "token" in component_set and component_set.intersection(_AUTHENTICATION_COMPONENTS):
        return True
    if {"connection", "string"}.issubset(component_set):
        return True
    if components == ("stack",) or {"stack", "trace"}.issubset(component_set):
        return True
    if {"provider", "payload"}.issubset(component_set):
        return True
    return (
        {"filesystem", "path"}.issubset(component_set)
        or {"local", "path"}.issubset(component_set)
    )


def _key_components(key: str) -> tuple[str, ...]:
    components: list[str] = []
    current: list[str] = []

    for index, character in enumerate(key):
        if not character.isalnum():
            if current:
                components.append("".join(current).casefold())
                current = []
            continue

        next_character = key[index + 1] if index + 1 < len(key) else ""
        starts_camel_word = bool(
            current
            and character.isupper()
            and (
                current[-1].islower()
                or (current[-1].isupper() and next_character.islower())
            )
        )
        if starts_camel_word:
            components.append("".join(current).casefold())
            current = []
        current.append(character)

    if current:
        components.append("".join(current).casefold())
    return tuple(components)
