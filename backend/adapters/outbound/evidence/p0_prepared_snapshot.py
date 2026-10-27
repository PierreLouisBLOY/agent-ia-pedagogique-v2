"""Exact prepared snapshot through AG02 ports, without external retrieval or admission."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import cast

from backend.agent_runtime.agents.evidence.evidence_agent import EvidenceAgent
from backend.agent_runtime.agents.evidence.evidence_agent_model import (
    EvidenceFetchRequest,
    EvidenceMaterializationPolicy,
)
from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    RetrievalCoordinationPolicy,
)
from backend.agent_runtime.agents.evidence.retrieval_coordinator import RetrievalCoordinator
from backend.agent_runtime.agents.evidence.retrieval_model import (
    DocumentContentRequest,
    DocumentContentResult,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
    RetrievalSearchResult,
    RetrievalSignals,
)
from backend.agent_runtime.contracts.common import ContractMeta
from backend.agent_runtime.contracts.evidence import EvidenceItem, EvidenceRequest
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.shared_kernel.time import Instant

_REFERENCE_FIELDS = {"evidence_id", "source_ref", "locator", "checksum_or_version", "excerpt_sha256", "provenance_label"}
_CHANNELS = (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL)


class PreparedEvidenceSnapshot:
    """Read-only exact memory bridge; membership is not a source admission."""
    def __init__(self, dispatch: Mapping[str, object], now: datetime) -> None:
        data = object_data(as_plain(dispatch))
        refs = [object_data(ref, _REFERENCE_FIELDS) for ref in items(data["references"], 8)]
        evidence = object_data(data["evidence"])
        if (not refs or any(any(type(value) is not str or not value for value in ref.values()) for ref in refs)
                or set(evidence) != {ref["evidence_id"] for ref in refs}
                or len({ref["evidence_id"] for ref in refs}) != len(refs)
                or len({(ref["source_ref"], ref["locator"], ref["checksum_or_version"]) for ref in refs}) != len(refs)):
            raise ValueError("P0_PREPARED_EVIDENCE_BINDING")
        for ref in refs:
            text = evidence[str(ref["evidence_id"])]
            if (type(text) is not str or not text.strip() or len(text) > 4000
                    or hashlib.sha256(text.encode()).hexdigest() != ref["excerpt_sha256"]):
                raise ValueError("P0_PREPARED_EVIDENCE_BINDING")
        self.references = tuple(MappingProxyType(ref) for ref in refs)
        self.evidence = MappingProxyType(evidence)
        self.now = Instant(now)
        self.policy = MappingProxyType({"prepared_snapshot_sha256": fingerprint(data), "scope": "EXACT_PREPARED_REFERENCE_SET_ONLY"})

    def _check(self, query: RetrievalQuery) -> None:
        if (query.search_goal != "EXACT_PREPARED_REFERENCE_SET_ONLY" or query.scope or query.filters
                or query.required_authority is not None or dict(query.source_policy) != self.policy
                or query.max_items != len(self.references)):
            raise ValueError("P0_PREPARED_EVIDENCE_QUERY_CHANGED")

    def _candidate(self, ref: Mapping[str, object], index: int, channel: RetrievalChannel) -> RetrievalCandidate:
        return RetrievalCandidate(str(ref["evidence_id"]) + ":" + channel.value, channel, str(ref["source_ref"]),
            "LOCAL_REFERENCE", str(ref["locator"]), RetrievalSignals(structured_rank=index),
            version_or_checksum=str(ref["checksum_or_version"]),
            provenance={"basis": "APPLICATION_PREPARED_SNAPSHOT_ONLY", "excerpt_sha256": ref["excerpt_sha256"]},
            authority={"authority": "NONE"}, metadata={"freshness": "UNKNOWN"})

    def search(self, *, query: RetrievalQuery, channel: RetrievalChannel) -> RetrievalSearchResult:
        self._check(query)
        if channel not in _CHANNELS:
            raise ValueError("P0_PREPARED_EVIDENCE_QUERY_CHANGED")
        return RetrievalSearchResult(channel, tuple(self._candidate(ref, index, channel)
            for index, ref in enumerate(self.references, 1)))

    def is_admissible(self, *, candidate: RetrievalCandidate, query: RetrievalQuery) -> bool:
        self._check(query)
        return candidate.channel in _CHANNELS and any(candidate == self._candidate(ref, index, candidate.channel)
                   for index, ref in enumerate(self.references, 1))

    def fetch(self, *, request: DocumentContentRequest) -> DocumentContentResult:
        if dict(request.source_policy) != self.policy:
            raise ValueError("P0_PREPARED_EVIDENCE_QUERY_CHANGED")
        matches = [(ref, candidate) for index, ref in enumerate(self.references, 1) for channel in _CHANNELS
            if (candidate := self._candidate(ref, index, channel)).candidate_id == request.candidate_id]
        if len(matches) != 1:
            raise ValueError("P0_PREPARED_EVIDENCE_BINDING")
        ref, candidate = matches[0]
        if request.source_ref != candidate.source_ref or request.locator != candidate.locator:
            raise ValueError("P0_PREPARED_EVIDENCE_BINDING")
        return DocumentContentResult(candidate.candidate_id, candidate.source_ref, candidate.locator,
            cast(str, self.evidence[str(ref["evidence_id"])]), self.now, candidate.source_kind,
            candidate.version_or_checksum, candidate.provenance)


def prepared_evidence_items(dispatch: Mapping[str, object], now: datetime,
                            meta: ContractMeta[InvocationStatus]) -> tuple[EvidenceItem, ...]:
    snapshot = PreparedEvidenceSnapshot(dispatch, now)
    request = EvidenceRequest(meta, "EXACT_PREPARED_REFERENCE_SET_ONLY", source_policy=snapshot.policy,
                              max_items=len(snapshot.references))
    coordinator = RetrievalCoordinator(snapshot,
        RetrievalCoordinationPolicy(_CHANNELS, _CHANNELS, 8, 8, 60), snapshot)
    agent = EvidenceAgent(coordinator, snapshot, EvidenceMaterializationPolicy(4000))
    retrieval = agent.search_evidence(request=request)
    if len(retrieval.ranked_candidates) != len(snapshot.references):
        raise ValueError("P0_PREPARED_EVIDENCE_BINDING")
    by_key = {(str(ref["source_ref"]), str(ref["locator"]), str(ref["checksum_or_version"])): ref
              for ref in snapshot.references}
    result = []
    for candidate in retrieval.ranked_candidates:
        representative = candidate.representative
        ref = by_key[(str(representative.source_ref), representative.locator, str(representative.version_or_checksum))]
        materialized = agent.fetch_evidence_item(request=EvidenceFetchRequest(str(ref["evidence_id"]), request, retrieval, candidate))
        if ("CONTENT_TRUNCATED" in materialized.limitations
                or materialized.item.excerpt_or_summary != snapshot.evidence[str(ref["evidence_id"])]
                or materialized.item.checksum_or_version != ref["checksum_or_version"]):
            raise ValueError("P0_PREPARED_EVIDENCE_BINDING")
        result.append(materialized.item)
    return tuple(result)
