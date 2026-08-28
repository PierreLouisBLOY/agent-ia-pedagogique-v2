"""Mechanical SQLite OP-11/OP-13 bindings for the existing AG-02 ports."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from backend.adapters.outbound.document_content.sqlite import (
    DocumentContentAccessAdapter,
)
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter, SearchHit
from backend.agent_runtime.agents.evidence import (
    DocumentContentRequest,
    DocumentContentResult,
    EvidenceContentUnavailable,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalQuery,
    RetrievalSearchResult,
    RetrievalSignals,
)
from backend.shared_kernel.time import Instant


class EvidenceClockPort(Protocol):
    def now(self) -> Instant: ...


class SQLiteEvidenceSearchAdapter:
    def __init__(self, search: BusinessSearchAdapter) -> None:
        self._search = search

    def search(
        self, *, query: RetrievalQuery, channel: RetrievalChannel
    ) -> RetrievalSearchResult:
        limit = query.max_items if query.max_items is not None else 10
        if channel is RetrievalChannel.STRUCTURED:
            hits = self._search.structured_search(query.search_goal, limit=limit)
        elif channel is RetrievalChannel.LEXICAL:
            hits = self._search.search(query.search_goal, limit=limit)
        elif channel is RetrievalChannel.RELATIONAL:
            raise RetrievalChannelUnavailable(channel, "RELATIONAL_NOT_CONFIGURED_C1")
        elif channel is RetrievalChannel.SEMANTIC:
            raise RetrievalChannelUnavailable(
                channel, "SEMANTIC_PROVIDER_NOT_CONFIGURED_C1"
            )
        else:
            raise RetrievalChannelUnavailable(channel, "CHANNEL_NOT_SEARCHABLE")
        return RetrievalSearchResult(
            channel,
            tuple(
                _candidate(hit, channel, index)
                for index, hit in enumerate(hits, start=1)
            ),
            metrics={"candidate_count": len(hits), "engine": "sqlite"},
        )

    def close(self) -> None:
        self._search.close()


class SQLiteEvidenceDocumentContentAdapter:
    def __init__(
        self, content: DocumentContentAccessAdapter, clock: EvidenceClockPort
    ) -> None:
        self._content = content
        self._clock = clock

    def fetch(self, *, request: DocumentContentRequest) -> DocumentContentResult:
        fragment = self._content.read_passage(request.locator)
        if fragment is None or fragment.source_ref != request.source_ref:
            raise EvidenceContentUnavailable(request.candidate_id, "PASSAGE_NOT_FOUND")
        return DocumentContentResult(
            candidate_id=request.candidate_id,
            source_ref=request.source_ref,
            locator=request.locator,
            content=fragment.text,
            retrieved_at=self._clock.now(),
            source_kind="canonical_search_chunk",
            version_or_checksum=fragment.version_or_checksum,
            provenance={
                "boundary": "sqlite-op13",
                "evidence_ref": fragment.evidence_ref,
            },
            metadata={"freshness": "CURRENT", "trust": "UNTRUSTED_CONTENT"},
        )

    def close(self) -> None:
        self._content.close()


def _candidate(
    hit: SearchHit, channel: RetrievalChannel, structured_rank: int
) -> RetrievalCandidate:
    signals = (
        RetrievalSignals(structured_rank=structured_rank)
        if channel is RetrievalChannel.STRUCTURED
        else RetrievalSignals(lexical_score=Decimal(str(hit.rank)))
    )
    return RetrievalCandidate(
        candidate_id=f"{channel.value.lower()}:{hit.passage_ref}",
        channel=channel,
        source_ref=hit.entity_ref,
        source_kind="canonical_search_chunk",
        locator=hit.passage_ref,
        signals=signals,
        canonical_object_ref=hit.entity_ref,
        version_or_checksum=hit.version_or_checksum,
        provenance={
            "boundary": "sqlite-op11",
            "object_kind": hit.entity_kind,
        },
        authority={"basis": "canonical-registry", "absolute": False},
        metadata={"freshness": "CURRENT"},
    )
