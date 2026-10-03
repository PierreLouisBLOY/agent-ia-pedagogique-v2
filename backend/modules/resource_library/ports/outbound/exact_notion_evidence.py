"""Read-only exact identity and explicitly linked admitted passages, owned by M03."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.modules.resource_library.ports.outbound.canonical_notion_catalog import (
    CanonicalNotionIdentityRecord,
)
from backend.modules.resource_library.ports.outbound.local_search import AdmittedLocalPassage


@dataclass(frozen=True, slots=True)
class ExactNotionEvidence:
    identity: CanonicalNotionIdentityRecord
    passages: tuple[AdmittedLocalPassage, ...]


class ExactNotionEvidencePort(Protocol):
    def get_exact_notion_evidence(self, notion_id: str) -> ExactNotionEvidence | None: ...
