from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from backend.shared_kernel._safe_data import freeze_safe_mapping
from backend.shared_kernel._value_safety import (
    DEFAULT_STRUCTURED_DATA_LIMITS,
    StructuredDataLimits,
    require_safe_structured_value,
)

AGENT_SAFE_DATA_LIMITS: Final = DEFAULT_STRUCTURED_DATA_LIMITS
ERROR_SAFE_DATA_LIMITS: Final = StructuredDataLimits(
    max_depth=8,
    max_mapping_keys=64,
    max_sequence_items=64,
    max_string_length=2_048,
    max_total_nodes=1_024,
)
SECURITY_EVENT_DATA_LIMITS: Final = StructuredDataLimits(
    max_depth=8,
    max_mapping_keys=32,
    max_sequence_items=64,
    max_string_length=512,
    max_total_nodes=512,
)

_PRIVATE_AGENT_CONCEPTS = (
    frozenset({"chain", "thought"}),
    frozenset({"private", "reasoning"}),
    frozenset({"system", "prompt"}),
)


def freeze_agent_safe_mapping(
    value: Mapping[str, object],
    *,
    limits: StructuredDataLimits = AGENT_SAFE_DATA_LIMITS,
) -> Mapping[str, object]:
    """Freeze structured data after rejecting private agent reasoning keys."""
    require_safe_structured_value(value, limits=limits, root_location="metadata")
    _reject_private_agent_keys(value)
    return freeze_safe_mapping(value)


def require_agent_safe_value(
    value: object,
    *,
    root_location: str,
    limits: StructuredDataLimits = AGENT_SAFE_DATA_LIMITS,
) -> None:
    require_safe_structured_value(
        value,
        limits=limits,
        root_location=root_location,
    )


def require_agent_safe_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    limits = StructuredDataLimits(
        max_depth=1,
        max_mapping_keys=1,
        max_sequence_items=1,
        max_string_length=max_length,
        max_total_nodes=1,
    )
    require_safe_structured_value(
        value,
        limits=limits,
        root_location=field_name,
    )


def require_agent_safe_ref(
    value: object,
    *,
    field_name: str,
    max_string_length: int = 256,
) -> None:
    if type(value) is str:
        require_agent_safe_text(
            value,
            field_name=field_name,
            max_length=max_string_length,
        )


def _reject_private_agent_keys(value: object) -> None:
    pending = [value]
    while pending:
        item_value = pending.pop()
        if isinstance(item_value, Mapping):
            for key, item in item_value.items():
                if not isinstance(key, str):
                    raise TypeError("structured data keys must be strings")
                if _is_private_agent_key(key):
                    raise ValueError(f"forbidden agent runtime data key: {key}")
                pending.append(item)
        elif isinstance(item_value, (list, tuple)):
            pending.extend(item_value)


def _is_private_agent_key(key: str) -> bool:
    components = frozenset(_key_components(key))
    return any(concept.issubset(components) for concept in _PRIVATE_AGENT_CONCEPTS)


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
