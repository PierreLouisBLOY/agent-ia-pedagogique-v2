"""Active lexical discovery through M03 Application, not direct business access."""
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from backend.adapters.outbound.evidence.p0_prepared_snapshot import PreparedEvidenceSnapshot
from backend.agent_runtime.agents.evidence import (
    DocumentContentRequest,
    DocumentContentResult,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
    RetrievalSearchResult,
    RetrievalSignals,
)
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.domain.value_objects.search_text import SearchText
from backend.modules.resource_library.ports.inbound.local_search import LocalSearchInbound
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


class ApplicationEvidenceSearch:
    """Search is a proposal only. Selection/admission for generation stays separate."""
    def __init__(self, inbound: LocalSearchInbound, correlation: CorrelationId) -> None:
        self.inbound, self.correlation = inbound, correlation
        self.rows: dict[str, tuple[RetrievalCandidate, DocumentContentResult]] = {}

    def search(self, *, query: RetrievalQuery, channel: RetrievalChannel) -> RetrievalSearchResult:
        if (channel is not RetrievalChannel.LEXICAL or query.scope or query.filters
                or query.required_authority is not None or query.source_policy):
            raise ValueError("P0_ACTIVE_SEARCH_SCOPE_UNSUPPORTED")
        limit = query.max_items or 8
        if not 1 <= limit <= 8:
            raise ValueError("P0_ACTIVE_SEARCH_LIMIT")
        outcome = self.inbound.search_local(request=SearchLocalRequest(SearchText(query.search_goal), limit),
                                            correlation_id=self.correlation)
        if (not outcome.success or outcome.data is None or outcome.side_effects
                or outcome.business_errors or outcome.application_failure is not None
                or outcome.correlation_id != self.correlation):
            raise ValueError("P0_ACTIVE_SEARCH_APPLICATION_OUTCOME")
        self.rows.clear()
        candidates = []
        for item in outcome.data.items:
            row = item.passage
            if row.excerpt_truncated:
                continue
            key = "application-passage:" + str(item.position)
            candidate = RetrievalCandidate(key, channel, row.object_ref, row.object_kind, row.passage_ref,
                RetrievalSignals(lexical_score=Decimal(1) / Decimal(item.position)), version_or_checksum=row.version_or_checksum,
                provenance={"boundary": "M03_APPLICATION", "admission": "NOT_GRANTED_BY_RETRIEVAL"},
                authority={"authority": "NONE"}, metadata={"freshness": "CURRENT"})
            content = DocumentContentResult(key, row.object_ref, row.passage_ref, row.excerpt,
                Instant(datetime.now(UTC)), row.object_kind, row.version_or_checksum, candidate.provenance)
            self.rows[key] = candidate, content
            candidates.append(candidate)
        return RetrievalSearchResult(channel, tuple(candidates))

    def is_admissible(self, *, candidate: RetrievalCandidate, query: RetrievalQuery) -> bool:
        pair = self.rows.get(candidate.candidate_id)
        return bool(pair and pair[0] == candidate and not query.source_policy)

    def fetch(self, *, request: DocumentContentRequest) -> DocumentContentResult:
        pair = self.rows.get(request.candidate_id)
        if (pair is None or request.source_policy or request.source_ref != pair[0].source_ref
                or request.locator != pair[0].locator):
            raise ValueError("P0_ACTIVE_SEARCH_MEMBERSHIP")
        return pair[1]


class CoDesignEvidenceSources:
    """Native hybrid: exact prepared structured set plus active Application search."""
    def __init__(self, prepared: PreparedEvidenceSnapshot, active: ApplicationEvidenceSearch) -> None:
        self.prepared, self.active = prepared, active
        self.structured_ids: set[str] = set()

    def _exact(self, query: RetrievalQuery) -> RetrievalQuery:
        if query.scope or query.filters or query.source_policy or query.required_authority is not None:
            raise ValueError("P0_ACTIVE_SEARCH_SCOPE_UNSUPPORTED")
        return replace(query, search_goal="EXACT_PREPARED_REFERENCE_SET_ONLY",
                       source_policy=self.prepared.policy, max_items=len(self.prepared.references))

    def search(self, *, query: RetrievalQuery, channel: RetrievalChannel) -> RetrievalSearchResult:
        if channel is RetrievalChannel.STRUCTURED:
            result = self.prepared.search(query=self._exact(query), channel=channel)
            self.structured_ids = {row.candidate_id for row in result.candidates}
            return result
        return self.active.search(query=query, channel=channel)

    def is_admissible(self, *, candidate: RetrievalCandidate, query: RetrievalQuery) -> bool:
        if candidate.channel is RetrievalChannel.STRUCTURED:
            return self.prepared.is_admissible(candidate=candidate, query=self._exact(query))
        return self.active.is_admissible(candidate=candidate, query=query)

    def fetch(self, *, request: DocumentContentRequest) -> DocumentContentResult:
        if request.candidate_id in self.structured_ids:
            if request.source_policy:
                raise ValueError("P0_ACTIVE_SEARCH_SCOPE_UNSUPPORTED")
            return self.prepared.fetch(request=replace(request, source_policy=self.prepared.policy))
        return self.active.fetch(request=request)
