from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.modules.resource_library.application.dto.output.resource_view import ResourceView
from backend.modules.resource_library.ports.outbound.local_search import AdmittedLocalPassage


class SearchOpenStatus(StrEnum):
    OPENABLE = "OPENABLE"
    NOT_RESOURCE = "NOT_RESOURCE"
    INVALID_RESOURCE_REF = "INVALID_RESOURCE_REF"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class LocalSearchItem:
    position: int
    passage: AdmittedLocalPassage
    read15: ResourceView | None
    open_status: SearchOpenStatus

    def __post_init__(self) -> None:
        if type(self.position) is not int or not 1 <= self.position <= 20:
            raise ValueError("INVALID_SEARCH_POSITION")
        if type(self.passage) is not AdmittedLocalPassage:
            raise ValueError("INVALID_SEARCH_PASSAGE")
        if type(self.open_status) is not SearchOpenStatus:
            raise ValueError("INVALID_OPEN_STATUS")
        if self.open_status is SearchOpenStatus.OPENABLE:
            if (type(self.read15) is not ResourceView
                    or self.read15.resource_ref.value != self.passage.object_ref
                    or self.passage.object_kind != "RESOURCE"):
                raise ValueError("INVALID_SEARCH_RESOURCE_LINK")
        elif self.read15 is not None:
            raise ValueError("INVALID_SEARCH_RESOURCE_LINK")


@dataclass(frozen=True, slots=True)
class LocalSearchView:
    items: tuple[LocalSearchItem, ...]
    window_full: bool
    more_admitted_in_window: bool

    def __post_init__(self) -> None:
        if type(self.items) is not tuple or len(self.items) > 20 or any(
            type(item) is not LocalSearchItem or item.position != index
            for index, item in enumerate(self.items, 1)
        ):
            raise ValueError("INVALID_SEARCH_VIEW")
        if type(self.window_full) is not bool or type(self.more_admitted_in_window) is not bool:
            raise ValueError("INVALID_SEARCH_VIEW")
