from __future__ import annotations

from collections.abc import Mapping

from backend.shared_kernel._safe_data import freeze_safe_mapping

_PRIVATE_AGENT_CONCEPTS = (
    frozenset({"chain", "thought"}),
    frozenset({"private", "reasoning"}),
    frozenset({"system", "prompt"}),
)


def freeze_agent_safe_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Freeze structured data after rejecting private agent reasoning keys."""
    _reject_private_agent_keys(value)
    return freeze_safe_mapping(value)


def _reject_private_agent_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("structured data keys must be strings")
            if _is_private_agent_key(key):
                raise ValueError(f"forbidden agent runtime data key: {key}")
            _reject_private_agent_keys(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_agent_keys(item)


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
