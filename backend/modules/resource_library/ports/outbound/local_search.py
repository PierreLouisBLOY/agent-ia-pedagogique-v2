"""Transport-neutral admitted passage window owned by M03."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.modules.resource_library.domain.value_objects.search_text import SearchText


def require_logical_identifier(value: str, maximum: int) -> None:
    if type(value) is not str or not 1 <= len(value) <= maximum or any(
        unicodedata.category(c)[0] not in {"L", "N"} and c not in "._:-" for c in value
    ):
        raise ValueError("INVALID_SEARCH_PROJECTION")


@dataclass(frozen=True, slots=True)
class AdmittedLocalPassage:
    object_ref: str
    object_kind: str
    passage_ref: str
    version_or_checksum: str
    excerpt: str
    excerpt_truncated: bool

    def __post_init__(self) -> None:
        for value, maximum in (
            (self.object_ref, 256), (self.object_kind, 64),
            (self.passage_ref, 256), (self.version_or_checksum, 128),
        ):
            require_logical_identifier(value, maximum)
        if type(self.excerpt) is not str or len(self.excerpt) > 320 or any(
            unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in self.excerpt
        ):
            raise ValueError("INVALID_SEARCH_PROJECTION")
        if type(self.excerpt_truncated) is not bool:
            raise ValueError("INVALID_SEARCH_PROJECTION")


@dataclass(frozen=True, slots=True)
class LocalSearchWindow:
    passages: tuple[AdmittedLocalPassage, ...]
    window_full: bool
    more_admitted_in_window: bool

    def __post_init__(self) -> None:
        if type(self.passages) is not tuple or len(self.passages) > 20:
            raise ValueError("INVALID_SEARCH_WINDOW")
        if any(type(p) is not AdmittedLocalPassage for p in self.passages):
            raise ValueError("INVALID_SEARCH_WINDOW")
        if len({p.passage_ref for p in self.passages}) != len(self.passages):
            raise ValueError("DUPLICATE_SEARCH_PASSAGE")
        if type(self.window_full) is not bool or type(self.more_admitted_in_window) is not bool:
            raise ValueError("INVALID_SEARCH_WINDOW")


@runtime_checkable
class LocalSearchPort(Protocol):
    def admitted_window(
        self, *, text: SearchText, result_limit: int, candidate_limit: int = 100,
    ) -> LocalSearchWindow: ...
