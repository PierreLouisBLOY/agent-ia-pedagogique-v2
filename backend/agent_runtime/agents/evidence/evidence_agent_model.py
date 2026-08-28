from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    FusedRetrievalCandidate,
    RetrievalCoordinationResult,
    RetrievalIdentity,
)
from backend.agent_runtime.agents.evidence.retrieval_model import RetrievalChannel
from backend.agent_runtime.contracts.common import (
    ActorKind,
    AgentId,
    ContractMeta,
    freeze_agent_safe_mapping,
)
from backend.agent_runtime.contracts.evidence import EvidenceItem, EvidenceRequest
from backend.agent_runtime.contracts.invocation import AgentResultStatus
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class EvidenceMaterializationPolicy:
    """Replaceable technical bound for verbatim evidence excerpts."""

    max_excerpt_chars: int

    def __post_init__(self) -> None:
        _require_positive_integer(self.max_excerpt_chars, "max_excerpt_chars")


class EvidenceCoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"


class EvidenceFreshnessStatus(StrEnum):
    REPORTED_CURRENT = "REPORTED_CURRENT"
    REPORTED_STALE = "REPORTED_STALE"
    UNKNOWN = "UNKNOWN"


class EvidenceMaterializationCode(StrEnum):
    CONTENT_UNAVAILABLE = "CONTENT_UNAVAILABLE"
    CONTENT_RESULT_MISMATCH = "CONTENT_RESULT_MISMATCH"
    CONTENT_VERSION_MISMATCH = "CONTENT_VERSION_MISMATCH"
    DUPLICATE_EVIDENCE_ID = "DUPLICATE_EVIDENCE_ID"
    RESULT_META_MISMATCH = "RESULT_META_MISMATCH"
    RETRIEVAL_LINEAGE_MISMATCH = "RETRIEVAL_LINEAGE_MISMATCH"


class EvidenceMaterializationError(ValueError):
    code: EvidenceMaterializationCode

    def __init__(self, code: EvidenceMaterializationCode, message: str) -> None:
        if not isinstance(code, EvidenceMaterializationCode):
            raise TypeError("code must be an EvidenceMaterializationCode")
        require_non_empty(message, "message")
        self.code = code
        super().__init__(message)


class EvidenceContentUnavailable(RuntimeError):
    candidate_id: str
    reason_code: str

    def __init__(self, candidate_id: str, reason_code: str) -> None:
        require_non_empty(candidate_id, "candidate_id")
        require_non_empty(reason_code, "reason_code")
        self.candidate_id = candidate_id
        self.reason_code = reason_code
        super().__init__(
            f"evidence content unavailable: {candidate_id} ({reason_code})"
        )


@dataclass(frozen=True, slots=True)
class EvidenceFetchRequest:
    evidence_id: str
    request: EvidenceRequest
    retrieval: RetrievalCoordinationResult
    candidate: FusedRetrievalCandidate

    def __post_init__(self) -> None:
        require_non_empty(self.evidence_id, "evidence_id")
        if type(self.request) is not EvidenceRequest:
            raise TypeError("request must be an EvidenceRequest")
        if type(self.retrieval) is not RetrievalCoordinationResult:
            raise TypeError("retrieval must be a RetrievalCoordinationResult")
        if type(self.candidate) is not FusedRetrievalCandidate:
            raise TypeError("candidate must be a FusedRetrievalCandidate")
        validate_retrieval_lineage(self.request, self.retrieval)
        _validate_candidate_membership(self.candidate, self.retrieval)


@dataclass(frozen=True, slots=True)
class MaterializedEvidence:
    item: EvidenceItem
    identity: RetrievalIdentity
    technical_rank: int
    channels: tuple[RetrievalChannel, ...]
    freshness: EvidenceFreshnessStatus
    limitations: tuple[str, ...] = ()
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.item) is not EvidenceItem:
            raise TypeError("item must be an EvidenceItem")
        if not isinstance(self.identity, RetrievalIdentity):
            raise TypeError("identity must be a RetrievalIdentity")
        _require_positive_integer(self.technical_rank, "technical_rank")
        _validate_channel_tuple(self.channels, "channels")
        if not self.channels:
            raise ValueError("channels must not be empty")
        if not isinstance(self.freshness, EvidenceFreshnessStatus):
            raise TypeError("freshness must be an EvidenceFreshnessStatus")
        _validate_string_tuple(self.limitations, "limitations")
        object.__setattr__(
            self,
            "provenance",
            freeze_agent_safe_mapping(self.provenance),
        )


@dataclass(frozen=True, slots=True)
class EvidenceCoverageAssessment:
    status: EvidenceCoverageStatus
    candidate_count: int
    materialized_count: int
    missing_candidate_ids: tuple[str, ...]
    degraded_retrieval: bool
    unavailable_channels: tuple[RetrievalChannel, ...]
    semantic_adequacy_assessed: bool
    authority_requirement_assessed: bool
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvidenceCoverageStatus):
            raise TypeError("status must be an EvidenceCoverageStatus")
        _require_non_negative_integer(self.candidate_count, "candidate_count")
        _require_non_negative_integer(self.materialized_count, "materialized_count")
        if self.materialized_count > self.candidate_count:
            raise ValueError("materialized_count must not exceed candidate_count")
        _validate_string_tuple(self.missing_candidate_ids, "missing_candidate_ids")
        if len(self.missing_candidate_ids) != self.candidate_count - self.materialized_count:
            raise ValueError("missing_candidate_ids must match the materialization gap")
        if not isinstance(self.degraded_retrieval, bool):
            raise TypeError("degraded_retrieval must be a bool")
        _validate_channel_tuple(self.unavailable_channels, "unavailable_channels")
        if self.semantic_adequacy_assessed is not False:
            raise ValueError("semantic adequacy must remain unassessed")
        if self.authority_requirement_assessed is not False:
            raise ValueError("authority requirement must remain unassessed")
        _validate_string_tuple(self.limitations, "limitations")
        expected_status = _coverage_status(
            self.candidate_count,
            self.materialized_count,
        )
        if self.status is not expected_status:
            raise ValueError("coverage status does not match materialization counts")


@dataclass(frozen=True, slots=True)
class EvidenceVersionConflict:
    canonical_base_key: tuple[str, ...]
    versions: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_string_tuple(
            self.canonical_base_key,
            "canonical_base_key",
            unique=False,
        )
        if not self.canonical_base_key:
            raise ValueError("canonical_base_key must not be empty")
        _validate_string_tuple(self.versions, "versions")
        if len(self.versions) < 2:
            raise ValueError("a version conflict requires at least two versions")
        _validate_string_tuple(self.evidence_ids, "evidence_ids")
        if len(self.evidence_ids) < 2:
            raise ValueError("a version conflict requires at least two evidence ids")


@dataclass(frozen=True, slots=True)
class EvidenceSetBuildRequest:
    request: EvidenceRequest
    result_meta: ContractMeta[AgentResultStatus]
    retrieval: RetrievalCoordinationResult
    materialized: tuple[MaterializedEvidence, ...]

    def __post_init__(self) -> None:
        if type(self.request) is not EvidenceRequest:
            raise TypeError("request must be an EvidenceRequest")
        if not isinstance(self.result_meta, ContractMeta):
            raise TypeError("result_meta must be a ContractMeta")
        if not isinstance(self.result_meta.status, AgentResultStatus) or (
            self.result_meta.status
            not in {
                AgentResultStatus.SUCCEEDED,
                AgentResultStatus.PARTIAL,
            }
        ):
            _raise_meta_mismatch("result status must be SUCCEEDED or PARTIAL")
        request_meta = self.request.meta
        if (
            self.result_meta.run_id != request_meta.run_id
            or self.result_meta.step_id != request_meta.step_id
            or self.result_meta.correlation_id != request_meta.correlation_id
        ):
            _raise_meta_mismatch("result metadata does not match evidence request")
        if (
            self.result_meta.actor.kind is not ActorKind.AGENT
            or self.result_meta.actor.actor_id != AgentId.AG_02.value
        ):
            _raise_meta_mismatch("result actor must be AG-02")
        if type(self.retrieval) is not RetrievalCoordinationResult:
            raise TypeError("retrieval must be a RetrievalCoordinationResult")
        validate_retrieval_lineage(self.request, self.retrieval)
        if not isinstance(self.materialized, tuple):
            raise TypeError("materialized must be a tuple")
        if any(type(item) is not MaterializedEvidence for item in self.materialized):
            raise TypeError("materialized must contain MaterializedEvidence values")
        evidence_ids = tuple(item.item.evidence_id for item in self.materialized)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise EvidenceMaterializationError(
                EvidenceMaterializationCode.DUPLICATE_EVIDENCE_ID,
                "materialized evidence ids must be unique",
            )
        technical_ranks = tuple(item.technical_rank for item in self.materialized)
        if len(technical_ranks) != len(set(technical_ranks)):
            _raise_meta_mismatch("materialized technical ranks must be unique")
        fused_by_identity = {
            candidate.identity: candidate
            for candidate in self.retrieval.ranked_candidates
        }
        for item in self.materialized:
            fused = fused_by_identity.get(item.identity)
            if fused is None or fused.technical_rank != item.technical_rank:
                _raise_meta_mismatch(
                    "materialized evidence does not match retrieval candidates"
                )


def validate_retrieval_lineage(
    request: EvidenceRequest,
    retrieval: RetrievalCoordinationResult,
) -> None:
    if type(request) is not EvidenceRequest:
        raise TypeError("request must be an EvidenceRequest")
    if type(retrieval) is not RetrievalCoordinationResult:
        raise TypeError("retrieval must be a RetrievalCoordinationResult")
    query = retrieval.query
    if (
        query.search_goal != request.search_goal
        or query.scope != request.scope
        or query.source_policy != request.source_policy
        or query.filters != request.filters
        or query.required_authority != request.required_authority
    ):
        _raise_lineage_mismatch("retrieval query does not match evidence request")
    if request.max_items is not None:
        if query.max_items is None or query.max_items > request.max_items:
            _raise_lineage_mismatch("retrieval query widens the requested item limit")
    elif query.max_items is None:
        _raise_lineage_mismatch("retrieval query must remain technically bounded")
    if request.max_items == 0 and (
        retrieval.ranked_candidates or retrieval.channel_results
    ):
        _raise_lineage_mismatch("zero-item evidence request requires an empty retrieval")


def _validate_candidate_membership(
    candidate: FusedRetrievalCandidate,
    retrieval: RetrievalCoordinationResult,
) -> None:
    matches = tuple(
        item
        for item in retrieval.ranked_candidates
        if item.identity == candidate.identity
        and item.technical_rank == candidate.technical_rank
    )
    if len(matches) != 1 or matches[0] != candidate:
        _raise_lineage_mismatch(
            "fetch candidate does not belong to the retrieval result"
        )


def _coverage_status(
    candidate_count: int,
    materialized_count: int,
) -> EvidenceCoverageStatus:
    if candidate_count == 0:
        return EvidenceCoverageStatus.EMPTY
    if materialized_count == candidate_count:
        return EvidenceCoverageStatus.COMPLETE
    return EvidenceCoverageStatus.PARTIAL


def _validate_channel_tuple(
    channels: tuple[RetrievalChannel, ...],
    field_name: str,
) -> None:
    if not isinstance(channels, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if any(not isinstance(channel, RetrievalChannel) for channel in channels):
        raise TypeError(f"{field_name} must contain RetrievalChannel values")
    if len(channels) != len(set(channels)):
        raise ValueError(f"{field_name} must contain unique channels")


def _validate_string_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    unique: bool = True,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for value in values:
        require_non_empty(value, f"{field_name} item")
    if unique and len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")


def _require_positive_integer(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")


def _require_non_negative_integer(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _raise_meta_mismatch(message: str) -> None:
    raise EvidenceMaterializationError(
        EvidenceMaterializationCode.RESULT_META_MISMATCH,
        message,
    )


def _raise_lineage_mismatch(message: str) -> None:
    raise EvidenceMaterializationError(
        EvidenceMaterializationCode.RETRIEVAL_LINEAGE_MISMATCH,
        message,
    )


BASELINE_EVIDENCE_MATERIALIZATION_POLICY = EvidenceMaterializationPolicy(
    max_excerpt_chars=4000,
)
