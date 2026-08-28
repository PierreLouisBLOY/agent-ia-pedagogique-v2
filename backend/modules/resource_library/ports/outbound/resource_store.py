from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    """M03-owned logical record crossing OP-03, never a SQLite row."""

    resource_ref: str
    resource_type: str
    canonical_title: str
    identity_status: str

    def __post_init__(self) -> None:
        require_non_empty(self.resource_ref, "resource_ref")
        require_non_empty(self.resource_type, "resource_type")
        require_non_empty(self.canonical_title, "canonical_title")
        require_non_empty(self.identity_status, "identity_status")


@runtime_checkable
class ResourceStorePort(Protocol):
    """Canonical OP-03 read surface needed by READ-15."""

    def load_resource(self, resource_ref: str) -> ResourceRecord | None:
        ...
