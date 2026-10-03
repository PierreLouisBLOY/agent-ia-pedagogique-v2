"""Existing canonical projection, F2A admission and OP-13 content, by exact ID."""
from __future__ import annotations

import sqlite3

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import SQLiteEvidenceSearchAdapter, _candidate
from backend.adapters.outbound.resource_library.canonical_notion_sqlite import (
    SQLiteCanonicalNotionCatalogAdapter,
)
from backend.adapters.outbound.search.local import minimized_excerpt
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter, SearchHit
from backend.agent_runtime.agents.evidence import RetrievalChannel, RetrievalQuery
from backend.modules.resource_library.ports.outbound.exact_notion_evidence import (
    ExactNotionEvidence,
)
from backend.modules.resource_library.ports.outbound.local_search import AdmittedLocalPassage


class SQLiteExactNotionEvidenceAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        # The existing catalog enforces query_only before any projection is read.
        catalog = SQLiteCanonicalNotionCatalogAdapter(connection)
        self._identities = {n.notion_id: n for n in catalog.list_canonical_notion_identities()}
        self._search = BusinessSearchAdapter(connection)
        self._admission = SQLiteEvidenceSearchAdapter(self._search)
        self._content = DocumentContentAccessAdapter(connection)
        self._passages = self._search.canonical_search_passages()

    def get_exact_notion_evidence(self, notion_id: str) -> ExactNotionEvidence | None:
        identity = self._identities.get(notion_id)
        if identity is None:
            return None
        query = RetrievalQuery(
            search_goal=notion_id, scope={}, source_policy={"kinds": ("canonical",)},
            filters={"active": True}, required_authority={"basis": "canonical-registry"},
            max_items=100,
        )
        passages: list[AdmittedLocalPassage] = []
        for p in self._passages:
            if p.canonical_object_ref != notion_id and notion_id not in p.semantic_rollup_refs:
                continue
            hit = SearchHit(p.canonical_object_ref, p.chunk_type, p.passage_ref,
                            p.version_or_checksum, p.text, 0.0, p.object_type)
            candidate = _candidate(hit, RetrievalChannel.STRUCTURED, len(passages) + 1)
            if not self._admission.is_admissible(candidate=candidate, query=query):
                continue
            fragment = self._content.read_passage(p.passage_ref)
            if fragment is None or (fragment.source_ref, fragment.version_or_checksum) != (
                p.canonical_object_ref, p.version_or_checksum,
            ):
                raise ValueError("R6_EXACT_NOTION_PROVENANCE_MISMATCH")
            excerpt, truncated = minimized_excerpt(fragment.text)
            passages.append(AdmittedLocalPassage(p.canonical_object_ref, p.object_type,
                p.passage_ref, p.version_or_checksum, excerpt, truncated))
        return ExactNotionEvidence(identity, tuple(passages))
