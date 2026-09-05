"""M03-owned bounded lexical intention; no transport or storage syntax."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


class InvalidSearchTextError(ValueError):
    """A public search intention is not supported."""


@dataclass(frozen=True, slots=True)
class SearchText:
    value: str
    tokens: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        if type(self.value) is not str or not 1 <= len(self.value) <= 256:
            raise InvalidSearchTextError("SEARCH_REQUEST_REJECTED")
        if any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in self.value):
            raise InvalidSearchTextError("SEARCH_REQUEST_REJECTED")
        normalized = unicodedata.normalize("NFC", self.value)
        normalized = " ".join("".join(
            " " if unicodedata.category(c).startswith("Z") else c for c in normalized
        ).split(" "))
        normalized = " ".join(part for part in normalized.split(" ") if part)
        if not 1 <= len(normalized) <= 256:
            raise InvalidSearchTextError("SEARCH_REQUEST_REJECTED")
        tokens: list[str] = []
        current = ""
        for char in normalized:
            category = unicodedata.category(char)[0]
            if category in {"L", "N"} or category == "M" and current:
                current += char
            elif current:
                tokens.append(current)
                current = ""
        if current:
            tokens.append(current)
        if not 1 <= len(tokens) <= 12 or any(len(token) > 64 for token in tokens):
            raise InvalidSearchTextError("SEARCH_REQUEST_REJECTED")
        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "tokens", tuple(tokens))
