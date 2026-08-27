from __future__ import annotations

from collections.abc import Collection, Mapping


def normalize_structural_key(key: str) -> str:
    if type(key) is not str:
        raise TypeError("structured data keys must be strings")
    components: list[str] = []
    current: list[str] = []
    for index, character in enumerate(key):
        if not character.isalnum():
            if current:
                components.append("".join(current).casefold())
                current = []
            continue
        next_character = key[index + 1] if index + 1 < len(key) else ""
        if current and character.isupper() and (
            current[-1].islower()
            or (current[-1].isupper() and next_character.islower())
        ):
            components.append("".join(current).casefold())
            current = []
        current.append(character)
    if current:
        components.append("".join(current).casefold())
    return "_".join(components)


def structural_key_locations(
    value: object,
    *,
    forbidden_keys: Collection[str],
    root_location: str,
) -> tuple[str, ...]:
    normalized_forbidden = frozenset(
        normalize_structural_key(key) for key in forbidden_keys
    )
    compact_forbidden = frozenset(
        key.replace("_", "") for key in normalized_forbidden
    )
    matches: list[str] = []
    _collect_locations(
        value,
        (normalize_structural_key(root_location),),
        normalized_forbidden,
        compact_forbidden,
        matches,
    )
    return tuple(dict.fromkeys(matches))


def contains_structural_keys(
    value: object,
    *,
    forbidden_keys: Collection[str],
) -> bool:
    return bool(
        structural_key_locations(
            value,
            forbidden_keys=forbidden_keys,
            root_location="metadata",
        )
    )


def _collect_locations(
    value: object,
    path: tuple[str, ...],
    forbidden_keys: frozenset[str],
    compact_forbidden: frozenset[str],
    matches: list[str],
) -> None:
    if isinstance(value, Mapping):
        for index, (key, nested) in enumerate(value.items()):
            normalized = normalize_structural_key(key)
            segment = normalized if _is_safe_segment(normalized) else f"field_{index}"
            nested_path = (*path, segment)
            if (
                normalized in forbidden_keys
                or normalized.replace("_", "") in compact_forbidden
            ):
                matches.append(".".join(nested_path))
            _collect_locations(
                nested,
                nested_path,
                forbidden_keys,
                compact_forbidden,
                matches,
            )
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _collect_locations(
                nested,
                (*path, str(index)),
                forbidden_keys,
                compact_forbidden,
                matches,
            )


def _is_safe_segment(value: str) -> bool:
    return bool(value) and len(value) <= 64 and all(
        character.isascii() and (character.isalnum() or character == "_")
        for character in value
    )
