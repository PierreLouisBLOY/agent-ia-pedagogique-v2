"""Exact canonical identifier lookup; no lexical ranking or implicit alias resolution."""
from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.ports.outbound.exact_notion_evidence import (
    ExactNotionEvidence,
    ExactNotionEvidencePort,
)
from backend.modules.resource_library.ports.outbound.local_search import require_logical_identifier


@dataclass(frozen=True, slots=True)
class GetExactNotionEvidenceQuery:
    evidence: ExactNotionEvidencePort

    def execute(self, notion_id: str) -> ExactNotionEvidence | None:
        require_logical_identifier(notion_id, 256)
        result = self.evidence.get_exact_notion_evidence(notion_id)
        if result is not None and (
            result.identity.notion_id != notion_id
            or result.identity.identity_status != "CANONICAL"
            or len({p.passage_ref for p in result.passages}) != len(result.passages)
        ):
            raise ValueError("R6_EXACT_NOTION_IDENTITY_MISMATCH")
        return result
