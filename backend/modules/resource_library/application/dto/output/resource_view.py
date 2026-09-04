from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ResourceView:
    """Transport-neutral view returned by canonical getResource."""

    resource_ref: ResourceRef
    resource_type: str
    canonical_title: str
    availability_status: str

    def __post_init__(self) -> None:
        if type(self.resource_ref) is not ResourceRef:
            raise TypeError("resource_ref must be a ResourceRef")
        require_non_empty(self.resource_type, "resource_type")
        require_non_empty(self.canonical_title, "canonical_title")
        require_non_empty(self.availability_status, "availability_status")
