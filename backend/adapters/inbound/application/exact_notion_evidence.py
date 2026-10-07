"""Application entry for a bounded diagnostic campaign, without storage authority."""
from __future__ import annotations

from backend.modules.resource_library.application.queries.get_exact_notion_evidence import (
    GetExactNotionEvidenceQuery,
)


class ExactNotionEvidenceInbound:
    def __init__(self, query: GetExactNotionEvidenceQuery) -> None:
        self._query = query

    def inspect(self, notion_id: str) -> dict[str, object]:
        result = self._query.execute(notion_id)
        if result is None:
            return {"notion_id": notion_id, "status": "NOT_CANONICAL_OR_ABSENT", "items": []}
        return {
            "notion_id": notion_id, "status": "CANONICAL",
            "retrieval_path": "EXACT_ID_AND_EXPLICIT_LINKS",
            "items": [{
                "object_ref": p.object_ref, "object_kind": p.object_kind,
                "passage_ref": p.passage_ref, "version_or_checksum": p.version_or_checksum,
                "excerpt": p.excerpt, "excerpt_truncated": p.excerpt_truncated,
                **({"source_status": p.source_status.as_dict()} if p.source_status is not None else {}),
                "provenance": {"source_kind": "canonical_search_chunk", "freshness": "CURRENT",
                    "admission_policy": "F2A", "authority_absolute": False,
                    "content_trust": "UNTRUSTED_CONTENT", "channel": "EXACT_ID"},
            } for p in result.passages],
        }
