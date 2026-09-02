from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.modules.resource_library.domain.value_objects.persistence_vocabulary import (
    ResourceIdentityStatus,
    ResourceType,
)
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    """M03-owned logical record crossing OP-03, never a SQLite row."""

    resource_ref: str
    resource_type: ResourceType
    canonical_title: str
    identity_status: ResourceIdentityStatus

    def __post_init__(self) -> None:
        require_non_empty(self.resource_ref, "resource_ref")
        if not isinstance(self.resource_type, ResourceType):
            raise TypeError("resource_type must be a ResourceType")
        require_non_empty(self.canonical_title, "canonical_title")
        if not isinstance(self.identity_status, ResourceIdentityStatus):
            raise TypeError("identity_status must be a ResourceIdentityStatus")


@runtime_checkable
class ResourceStorePort(Protocol):
    """Canonical OP-03 read surface needed by READ-15."""

    def load_resource(self, resource_ref: str) -> ResourceRecord | None:
        ...
