from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ExactResourceEvidenceRequest:
    """Internal M03 request for one explicit resource/version pair."""

    resource_ref: ResourceRef
    resource_version_ref: str

    def __post_init__(self) -> None:
        if type(self.resource_ref) is not ResourceRef:
            raise TypeError("resource_ref must be a ResourceRef")
        require_non_empty(self.resource_version_ref, "resource_version_ref")
        if len(self.resource_version_ref) > 160:
            raise ValueError("resource_version_ref is too long")
