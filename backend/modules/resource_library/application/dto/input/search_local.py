from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.domain.value_objects.search_text import (
    InvalidSearchTextError,
    SearchText,
)


@dataclass(frozen=True, slots=True)
class SearchLocalRequest:
    text: SearchText
    limit: int = 10

    def __post_init__(self) -> None:
        if type(self.text) is not SearchText:
            raise InvalidSearchTextError("SEARCH_REQUEST_REJECTED")
        if type(self.limit) is not int or not 1 <= self.limit <= 20:
            raise InvalidSearchTextError("SEARCH_REQUEST_REJECTED")
