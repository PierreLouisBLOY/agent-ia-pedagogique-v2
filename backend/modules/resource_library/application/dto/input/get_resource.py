from __future__ import annotations

from dataclasses import dataclass

from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class GetResourceRequest:
    """Canonical READ-15 input for the minimal resource lookup slice."""

    resource_ref: str

    def __post_init__(self) -> None:
        require_non_empty(self.resource_ref, "resource_ref")
