from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CanonicalNotionIdentityRecord:
    notion_id: str
    canonical_label: str
    identity_status: str
    level_applicability: tuple[str, ...] = ()
    method_refs: tuple[str, ...] = ()


@runtime_checkable
class CanonicalNotionCatalogPort(Protocol):
    def list_canonical_notion_identities(self) -> tuple[CanonicalNotionIdentityRecord, ...]: ...
