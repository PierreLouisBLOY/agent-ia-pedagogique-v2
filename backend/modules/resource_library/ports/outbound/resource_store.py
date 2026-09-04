from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.modules.resource_library.domain.value_objects import (
    ResourceRef,
    ResourceSemanticState,
)
from backend.modules.resource_library.domain.value_objects.persistence_vocabulary import (
    ResourceType,
)
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    """M03-owned logical record crossing OP-03, never a SQLite row."""

    resource_ref: ResourceRef
    resource_type: ResourceType
    canonical_title: str
    semantic_state: ResourceSemanticState

    def __post_init__(self) -> None:
        if type(self.resource_ref) is not ResourceRef:
            raise TypeError("resource_ref must be a ResourceRef")
        if not isinstance(self.resource_type, ResourceType):
            raise TypeError("resource_type must be a ResourceType")
        require_non_empty(self.canonical_title, "canonical_title")
        if not isinstance(self.semantic_state, ResourceSemanticState):
            raise TypeError("semantic_state must be a ResourceSemanticState")


@runtime_checkable
class ResourceStorePort(Protocol):
    """Canonical OP-03 read surface needed by READ-15."""

    def load_resource(self, resource_ref: ResourceRef) -> ResourceRecord | None:
        ...
