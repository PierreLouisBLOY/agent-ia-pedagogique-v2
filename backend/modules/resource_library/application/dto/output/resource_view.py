from __future__ import annotations

from dataclasses import dataclass

from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ResourceView:
    """Transport-neutral view returned by canonical getResource."""

    resource_ref: str
    resource_type: str
    canonical_title: str
    identity_status: str

    def __post_init__(self) -> None:
        require_non_empty(self.resource_ref, "resource_ref")
        require_non_empty(self.resource_type, "resource_type")
        require_non_empty(self.canonical_title, "canonical_title")
        require_non_empty(self.identity_status, "identity_status")
