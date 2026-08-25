from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.agents.evidence.evidence_agent_model import (
    BASELINE_EVIDENCE_MATERIALIZATION_POLICY,
    EvidenceContentUnavailable,
    EvidenceCoverageAssessment,
    EvidenceCoverageStatus,
    EvidenceFetchRequest,
    EvidenceFreshnessStatus,
    EvidenceMaterializationCode,
    EvidenceMaterializationError,
    EvidenceMaterializationPolicy,
    EvidenceSetBuildRequest,
    EvidenceVersionConflict,
    MaterializedEvidence,
)
from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    FusedRetrievalCandidate,
    RetrievalCoordinationMode,
    RetrievalCoordinationResult,
    RetrievalIdentity,
)
from backend.agent_runtime.agents.evidence.retrieval_coordinator import (
    RetrievalCoordinator,
)
from backend.agent_runtime.agents.evidence.retrieval_model import (
    DocumentContentRequest,
    DocumentContentResult,
)
from backend.agent_runtime.agents.evidence.retrieval_ports import (
    EvidenceDocumentContentPort,
)
from backend.agent_runtime.contracts.common import AgentId, ContractRef
from backend.agent_runtime.contracts.evidence import EvidenceItem, EvidenceRequest, EvidenceSet
from backend.agent_runtime.contracts.invocation import AgentResultStatus
from backend.agent_runtime.registry import BASELINE_CAPABILITY_REGISTRY
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef

_AG_02_CAPABILITY_IDS = tuple(
    descriptor.capability_id.value
    for descriptor in BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_02)
)


@dataclass(frozen=True, slots=True)
class EvidenceAgent:
    retrieval_coordinator: RetrievalCoordinator
    content_port: EvidenceDocumentContentPort
    materialization_policy: EvidenceMaterializationPolicy = (
        BASELINE_EVIDENCE_MATERIALIZATION_POLICY
    )

    def __post_init__(self) -> None:
        if not isinstance(self.retrieval_coordinator, RetrievalCoordinator):
            raise TypeError("retrieval_coordinator must be a RetrievalCoordinator")
        if not isinstance(self.content_port, EvidenceDocumentContentPort):
            raise TypeError("content_port must implement EvidenceDocumentContentPort")
        if not isinstance(self.materialization_policy, EvidenceMaterializationPolicy):
            raise TypeError("materialization_policy must be an EvidenceMaterializationPolicy")

    def search_evidence(
        self,
        *,
        request: EvidenceRequest,
    ) -> RetrievalCoordinationResult:
        if type(request) is not EvidenceRequest:
            raise TypeError("request must be an EvidenceRequest")
        return self.retrieval_coordinator.coordinate(request=request)

    def fetch_evidence_item(
        self,
        *,
        request: EvidenceFetchRequest,
    ) -> MaterializedEvidence:
        if type(request) is not EvidenceFetchRequest:
            raise TypeError("request must be an EvidenceFetchRequest")
        representative = request.candidate.representative
        content_request = DocumentContentRequest(
            candidate_id=representative.candidate_id,
            source_ref=representative.source_ref,
            locator=representative.locator,
            source_policy=request.source_policy,
        )
        try:
            content = self.content_port.fetch(request=content_request)
        except EvidenceContentUnavailable:
            raise EvidenceMaterializationError(
                EvidenceMaterializationCode.CONTENT_UNAVAILABLE,
                f"content unavailable for candidate: {representative.candidate_id}",
            ) from None
        self._validate_content_result(content, content_request)

        candidate_version = representative.version_or_checksum
        content_version = content.version_or_checksum
        if (
            candidate_version is not None
            and content_version is not None
            and candidate_version != content_version
        ):
            raise EvidenceMaterializationError(
                EvidenceMaterializationCode.CONTENT_VERSION_MISMATCH,
                f"content version mismatch for candidate: {representative.candidate_id}",
            )
        selected_version = content_version or candidate_version
        freshness = _reported_freshness(representative.metadata.get("freshness"))
        excerpt = content.content[: self.materialization_policy.max_excerpt_chars]

        limitations: list[str] = []
        if selected_version is None:
            _append_unique(limitations, "VERSION_OR_CHECKSUM_UNKNOWN")
        if freshness is EvidenceFreshnessStatus.UNKNOWN:
            _append_unique(limitations, "FRESHNESS_UNKNOWN")
        elif freshness is EvidenceFreshnessStatus.REPORTED_STALE:
            _append_unique(limitations, "SOURCE_REPORTED_STALE")
        if len(content.content) > self.materialization_policy.max_excerpt_chars:
            _append_unique(limitations, "CONTENT_TRUNCATED")
        for warning in (*representative.security_warnings, *content.security_warnings):
            _append_unique(limitations, f"SECURITY_WARNING:{warning}")

        channels = tuple(request.candidate.channel_ranks)
        relevance = {
            "technical_rank": request.candidate.technical_rank,
            "fusion_score": format(request.candidate.fusion_score, "f"),
            "channel_ranks": {
                channel.value: rank
                for channel, rank in request.candidate.channel_ranks.items()
            },
            "channels": tuple(channel.value for channel in channels),
        }
        item = EvidenceItem(
            evidence_id=request.evidence_id,
            source_ref=content.source_ref,
            source_kind=content.source_kind,
            locator=content.locator,
            retrieved_at=content.retrieved_at,
            relevance=relevance,
            authority=representative.authority,
            excerpt_or_summary=excerpt,
            checksum_or_version=selected_version,
        )
        return MaterializedEvidence(
            item=item,
            identity=request.candidate.identity,
            technical_rank=request.candidate.technical_rank,
            channels=channels,
            freshness=freshness,
            limitations=tuple(limitations),
        )

    def assess_evidence_coverage(
        self,
        *,
        retrieval: RetrievalCoordinationResult,
        materialized: tuple[MaterializedEvidence, ...],
    ) -> EvidenceCoverageAssessment:
        if type(retrieval) is not RetrievalCoordinationResult:
            raise TypeError("retrieval must be a RetrievalCoordinationResult")
        _validate_materialized_collection(retrieval, materialized)
        materialized_identities = {item.identity for item in materialized}
        missing_candidate_ids = tuple(
            candidate.representative.candidate_id
            for candidate in retrieval.ranked_candidates
            if candidate.identity not in materialized_identities
        )
        candidate_count = len(retrieval.ranked_candidates)
        materialized_count = len(materialized)
        if candidate_count == 0:
            status = EvidenceCoverageStatus.EMPTY
        elif candidate_count == materialized_count:
            status = EvidenceCoverageStatus.COMPLETE
        else:
            status = EvidenceCoverageStatus.PARTIAL

        limitations: list[str] = []
        for limitation in retrieval.limitations:
            _append_unique(limitations, limitation)
        for item in materialized:
            for limitation in item.limitations:
                _append_unique(limitations, limitation)
        if status is EvidenceCoverageStatus.PARTIAL:
            _append_unique(limitations, "MATERIALIZATION_INCOMPLETE")
        elif status is EvidenceCoverageStatus.EMPTY:
            _append_unique(limitations, "NO_ADMISSIBLE_EVIDENCE")
        _append_unique(limitations, "SEMANTIC_ADEQUACY_UNASSESSED")

        return EvidenceCoverageAssessment(
            status=status,
            candidate_count=candidate_count,
            materialized_count=materialized_count,
            missing_candidate_ids=missing_candidate_ids,
            degraded_retrieval=(
                retrieval.mode is RetrievalCoordinationMode.DEGRADED
            ),
            unavailable_channels=retrieval.unavailable_channels,
            semantic_adequacy_assessed=False,
            authority_requirement_assessed=False,
            limitations=tuple(limitations),
        )

    def build_evidence_set(
        self,
        *,
        build_request: EvidenceSetBuildRequest,
    ) -> EvidenceSet:
        if type(build_request) is not EvidenceSetBuildRequest:
            raise TypeError("build_request must be an EvidenceSetBuildRequest")
        assessment = self.assess_evidence_coverage(
            retrieval=build_request.retrieval,
            materialized=build_request.materialized,
        )
        conflicts = detect_version_conflicts(build_request.materialized)
        expected_status = (
            AgentResultStatus.PARTIAL
            if assessment.status is EvidenceCoverageStatus.PARTIAL
            else AgentResultStatus.SUCCEEDED
        )
        if build_request.result_meta.status is not expected_status:
            raise EvidenceMaterializationError(
                EvidenceMaterializationCode.RESULT_META_MISMATCH,
                "result status does not match structural evidence coverage",
            )

        ordered = tuple(
            sorted(build_request.materialized, key=lambda item: item.technical_rank)
        )
        coverage = {
            "status": assessment.status.value,
            "candidate_count": assessment.candidate_count,
            "materialized_count": assessment.materialized_count,
            "missing_candidate_ids": assessment.missing_candidate_ids,
            "degraded_retrieval": assessment.degraded_retrieval,
            "unavailable_channels": tuple(
                channel.value for channel in assessment.unavailable_channels
            ),
            "semantic_adequacy_assessed": assessment.semantic_adequacy_assessed,
            "authority_requirement_assessed": (
                assessment.authority_requirement_assessed
            ),
        }
        conflict_mappings = tuple(
            {
                "type": "VERSION_DIVERGENCE",
                "canonical_base_key": conflict.canonical_base_key,
                "versions": conflict.versions,
                "evidence_ids": conflict.evidence_ids,
            }
            for conflict in conflicts
        )
        limitation_mappings = tuple(
            {"code": limitation} for limitation in assessment.limitations
        )
        freshness_counts = {
            status.value: sum(1 for item in ordered if item.freshness is status)
            for status in EvidenceFreshnessStatus
        }
        provenance_summary = {
            "agent_id": AgentId.AG_02.value,
            "capabilities": _AG_02_CAPABILITY_IDS,
            "retrieval_mode": build_request.retrieval.mode.value,
            "retrieval_channels": tuple(
                result.channel.value for result in build_request.retrieval.channel_results
            ),
            "versioned_evidence_count": sum(
                1 for item in ordered if item.item.checksum_or_version is not None
            ),
            "unversioned_evidence_count": sum(
                1 for item in ordered if item.item.checksum_or_version is None
            ),
            "freshness_counts": freshness_counts,
        }
        retrieval_metrics = {
            "ranked_candidate_count": len(
                build_request.retrieval.ranked_candidates
            ),
            "materialized_count": len(ordered),
            "channel_result_counts": {
                result.channel.value: len(result.candidates)
                for result in build_request.retrieval.channel_results
            },
        }
        return EvidenceSet(
            meta=build_request.result_meta,
            evidence_items=tuple(item.item for item in ordered),
            coverage=coverage,
            conflicts=conflict_mappings,
            limitations=limitation_mappings,
            provenance_summary=provenance_summary,
            retrieval_metrics=retrieval_metrics,
        )

    @staticmethod
    def _validate_content_result(
        content: DocumentContentResult,
        request: DocumentContentRequest,
    ) -> None:
        if type(content) is not DocumentContentResult:
            raise EvidenceMaterializationError(
                EvidenceMaterializationCode.CONTENT_RESULT_MISMATCH,
                "content port returned an invalid result",
            )
        if (
            content.candidate_id != request.candidate_id
            or content.source_ref != request.source_ref
            or content.locator != request.locator
        ):
            raise EvidenceMaterializationError(
                EvidenceMaterializationCode.CONTENT_RESULT_MISMATCH,
                f"content result mismatch for candidate: {request.candidate_id}",
            )


def detect_version_conflicts(
    materialized: tuple[MaterializedEvidence, ...],
) -> tuple[EvidenceVersionConflict, ...]:
    if not isinstance(materialized, tuple):
        raise TypeError("materialized must be a tuple")
    if any(type(item) is not MaterializedEvidence for item in materialized):
        raise TypeError("materialized must contain MaterializedEvidence values")
    grouped: dict[tuple[str, ...], list[MaterializedEvidence]] = {}
    for item in materialized:
        canonical_ref = item.identity.canonical_object_ref
        version = item.item.checksum_or_version
        if canonical_ref is None or version is None:
            continue
        base_key = _canonical_base_key(canonical_ref)
        grouped.setdefault(base_key, []).append(item)

    conflicts: list[EvidenceVersionConflict] = []
    for base_key in sorted(grouped):
        group = grouped[base_key]
        version_values: set[str] = set()
        for item in group:
            version = item.item.checksum_or_version
            if version is not None:
                version_values.add(version)
        versions = tuple(sorted(version_values))
        if len(versions) < 2:
            continue
        ordered = sorted(
            group,
            key=lambda item: (item.technical_rank, item.item.evidence_id),
        )
        conflicts.append(
            EvidenceVersionConflict(
                canonical_base_key=base_key,
                versions=versions,
                evidence_ids=tuple(item.item.evidence_id for item in ordered),
            )
        )
    return tuple(conflicts)


def _validate_materialized_collection(
    retrieval: RetrievalCoordinationResult,
    materialized: tuple[MaterializedEvidence, ...],
) -> None:
    if not isinstance(materialized, tuple):
        raise TypeError("materialized must be a tuple")
    if any(type(item) is not MaterializedEvidence for item in materialized):
        raise TypeError("materialized must contain MaterializedEvidence values")
    evidence_ids = tuple(item.item.evidence_id for item in materialized)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise EvidenceMaterializationError(
            EvidenceMaterializationCode.DUPLICATE_EVIDENCE_ID,
            "materialized evidence ids must be unique",
        )
    technical_ranks = tuple(item.technical_rank for item in materialized)
    if len(technical_ranks) != len(set(technical_ranks)):
        raise EvidenceMaterializationError(
            EvidenceMaterializationCode.RESULT_META_MISMATCH,
            "materialized technical ranks must be unique",
        )
    fused_by_identity: dict[RetrievalIdentity, FusedRetrievalCandidate] = {
        candidate.identity: candidate for candidate in retrieval.ranked_candidates
    }
    for item in materialized:
        fused = fused_by_identity.get(item.identity)
        if fused is None or fused.technical_rank != item.technical_rank:
            raise EvidenceMaterializationError(
                EvidenceMaterializationCode.RESULT_META_MISMATCH,
                "materialized evidence does not match retrieval candidates",
            )


def _reported_freshness(value: object) -> EvidenceFreshnessStatus:
    if value == "CURRENT":
        return EvidenceFreshnessStatus.REPORTED_CURRENT
    if value == "STALE":
        return EvidenceFreshnessStatus.REPORTED_STALE
    return EvidenceFreshnessStatus.UNKNOWN


def _canonical_base_key(reference: ContractRef) -> tuple[str, ...]:
    if isinstance(reference, str):
        return ("string-ref", reference)
    if isinstance(reference, TypedEntityRef):
        return (
            "typed-entity-ref",
            reference.entity_id.entity_type,
            reference.entity_id.value,
        )
    if isinstance(reference, ObjectVersionRef):
        return (
            "typed-entity-ref",
            reference.object_ref.entity_id.entity_type,
            reference.object_ref.entity_id.value,
        )
    raise TypeError("reference must be a canonical ContractRef")


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
