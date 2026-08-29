"""Mechanical SQLite OP-11/OP-13 bindings for the existing AG-02 ports."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from backend.adapters.outbound.document_content.sqlite import (
    DocumentContentAccessAdapter,
)
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter, SearchHit
from backend.adapters.outbound.semantic import (
    SemanticBackendUnavailable,
    SemanticHit,
    SemanticSearchBackend,
)
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
    def __init__(
        self,
        search: BusinessSearchAdapter,
        semantic_backend: SemanticSearchBackend | None = None,
    ) -> None:
        self._search = search
        self._semantic_backend = semantic_backend

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
            if self._semantic_backend is None:
                raise RetrievalChannelUnavailable(
                    channel, "SEMANTIC_PROVIDER_NOT_CONFIGURED_C1"
                )
            try:
                semantic_hits = self._semantic_backend.search(
                    text=self._search.semantic_query_text(query.search_goal),
                    limit=limit,
                )
            except SemanticBackendUnavailable as error:
                raise RetrievalChannelUnavailable(
                    channel, error.reason_code
                ) from None
            return RetrievalSearchResult(
                channel,
                tuple(
                    _semantic_candidate(hit, index)
                    for index, hit in enumerate(semantic_hits, start=1)
                ),
                metrics={
                    "candidate_count": len(semantic_hits),
                    "engine": "derived-sqlite-semantic",
                },
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

    def is_admissible(
        self,
        *,
        candidate: RetrievalCandidate,
        query: RetrievalQuery,
    ) -> bool:
        if not _query_constraints_supported(query):
            return False
        if (
            candidate.source_kind != "canonical_search_chunk"
            or not isinstance(candidate.source_ref, str)
            or candidate.canonical_object_ref != candidate.source_ref
            or candidate.version_or_checksum is None
            or candidate.provenance.get("boundary") != "sqlite-op11"
            or candidate.authority.get("basis") != "canonical-registry"
            or candidate.authority.get("absolute") is not False
            or candidate.metadata.get("freshness") != "CURRENT"
        ):
            return False
        if not self._search.is_current_canonical_passage(
            entity_ref=candidate.source_ref,
            passage_ref=candidate.locator,
            version_or_checksum=candidate.version_or_checksum,
        ):
            return False
        level = query.scope.get("level")
        if isinstance(level, str) and not self._search.canonical_object_matches_level(
            candidate.source_ref, level
        ):
            return False
        topic = query.scope.get("topic")
        return not isinstance(topic, str) or self._search.canonical_object_matches_topic(
            candidate.source_ref, topic
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
            "chunk_type": hit.entity_kind,
            "object_kind": hit.registry_object_type,
        },
        authority={"basis": "canonical-registry", "absolute": False},
        metadata={"freshness": "CURRENT"},
    )


def _semantic_candidate(hit: SemanticHit, rank: int) -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id=f"semantic:{hit.passage_ref}",
        channel=RetrievalChannel.SEMANTIC,
        source_ref=hit.canonical_object_ref,
        source_kind="canonical_search_chunk",
        locator=hit.passage_ref,
        signals=RetrievalSignals(
            semantic_score=Decimal(f"{hit.score:.12f}")
        ),
        canonical_object_ref=hit.canonical_object_ref,
        version_or_checksum=hit.version_or_checksum,
        provenance={
            "boundary": "sqlite-op11",
            "retrieval_boundary": "derived-semantic-sidecar",
            "chunk_type": hit.chunk_type,
            "object_kind": hit.object_type,
            "semantic_rank": rank,
            "matched_passage_ref": hit.matched_passage_ref,
        },
        authority={"basis": "canonical-registry", "absolute": False},
        metadata={"freshness": "CURRENT"},
    )


def _query_constraints_supported(query: RetrievalQuery) -> bool:
    scope_keys = set(query.scope)
    if not scope_keys.issubset({"level", "topic"}):
        return False
    for field_name in ("level", "topic"):
        value = query.scope.get(field_name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            return False
    if set(query.source_policy) != {"kinds"}:
        return False
    kinds = query.source_policy.get("kinds")
    if not isinstance(kinds, tuple) or kinds != ("canonical",):
        return False
    if dict(query.filters) != {"active": True}:
        return False
    if query.required_authority is not None and dict(query.required_authority) != {
        "basis": "canonical-registry"
    }:
        return False
    return True
