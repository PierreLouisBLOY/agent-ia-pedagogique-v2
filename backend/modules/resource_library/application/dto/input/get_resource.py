from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.domain.value_objects import ResourceRef


@dataclass(frozen=True, slots=True)
class GetResourceRequest:
    """Canonical READ-15 input for the minimal resource lookup slice."""

    resource_ref: ResourceRef

    def __post_init__(self) -> None:
        if type(self.resource_ref) is not ResourceRef:
            raise TypeError("resource_ref must be a ResourceRef")
