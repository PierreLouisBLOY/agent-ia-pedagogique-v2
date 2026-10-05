from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import NoReturn, cast

from backend.agent_runtime.agents.review.review_coordination_model import (
    PreparedReviewCall,
    ResolvedReviewTarget,
    ReviewCoordinationError,
    _validate_prepared_review_call,
)
from backend.agent_runtime.agents.review.review_metadata_successor import (
    ReviewDiagnosticSurface,
    reject_review_diagnostics,
)
from backend.agent_runtime.agents.review.review_model import (
    ReviewOperation,
    ReviewPortResult,
    ReviewPortResultStatus,
)
from backend.agent_runtime.agents.review.review_security import (
    ReviewSecurityGuard,
    freeze_evidence_security_by_ref,
    reject_activatable_review_metadata,
    reject_review_authority,
    require_security_output_allowed,
    validate_finding_locator,
)
from backend.agent_runtime.agents.review.review_security_model import (
    EvidenceSecurityByRef,
    ReviewSecurityAssessment,
    ReviewSecurityPolicy,
)
from backend.agent_runtime.contracts import (
    ActorKind,
    AgentId,
    ContractMeta,
    Finding,
    FindingSeverity,
    OverallAssessment,
    ReviewDimension,
    ReviewRequest,
    ReviewStatus,
)
from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class ReviewMaterializationErrorCode(StrEnum):
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    NON_MATERIALIZABLE_STATUS = "NON_MATERIALIZABLE_STATUS"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    SOURCE_STEP_MISMATCH = "SOURCE_STEP_MISMATCH"
    OPERATION_MISMATCH = "OPERATION_MISMATCH"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    INVALID_TECHNICAL_FINDING = "INVALID_TECHNICAL_FINDING"
    DUPLICATE_FINDING_ID = "DUPLICATE_FINDING_ID"
    FINDING_DIMENSION_OUT_OF_SCOPE = "FINDING_DIMENSION_OUT_OF_SCOPE"
    FINDING_EVIDENCE_OUT_OF_SCOPE = "FINDING_EVIDENCE_OUT_OF_SCOPE"
    FINDING_EVIDENCE_NOT_USED = "FINDING_EVIDENCE_NOT_USED"
    INVALID_OVERALL_ASSESSMENT = "INVALID_OVERALL_ASSESSMENT"
    COVERAGE_OUT_OF_SCOPE = "COVERAGE_OUT_OF_SCOPE"
    MATERIALIZATION_MISMATCH = "MATERIALIZATION_MISMATCH"


_SAFE_ERROR_REASON: Mapping[ReviewMaterializationErrorCode, str] = {
    ReviewMaterializationErrorCode.UNSUPPORTED_CAPABILITY: (
        "review materialization supports only semantic review"
    ),
    ReviewMaterializationErrorCode.NON_MATERIALIZABLE_STATUS: (
        "technical review status cannot be materialized"
    ),
    ReviewMaterializationErrorCode.STATUS_MISMATCH: (
        "canonical review status does not match the technical status"
    ),
    ReviewMaterializationErrorCode.SOURCE_STEP_MISMATCH: (
        "technical review source step does not match the prepared call"
    ),
    ReviewMaterializationErrorCode.OPERATION_MISMATCH: (
        "technical review operation does not match semantic review"
    ),
    ReviewMaterializationErrorCode.TARGET_MISMATCH: (
        "prepared review target does not match the canonical request"
    ),
    ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING: (
        "technical finding does not match the closed materialization schema"
    ),
    ReviewMaterializationErrorCode.DUPLICATE_FINDING_ID: (
        "technical findings contain duplicate identifiers"
    ),
    ReviewMaterializationErrorCode.FINDING_DIMENSION_OUT_OF_SCOPE: (
        "technical finding dimension is outside the requested review scope"
    ),
    ReviewMaterializationErrorCode.FINDING_EVIDENCE_OUT_OF_SCOPE: (
        "technical finding evidence is outside the requested review scope"
    ),
    ReviewMaterializationErrorCode.FINDING_EVIDENCE_NOT_USED: (
        "technical finding evidence is absent from the result evidence set"
    ),
    ReviewMaterializationErrorCode.INVALID_OVERALL_ASSESSMENT: (
        "technical overall assessment is not canonical"
    ),
    ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE: (
        "technical coverage is outside the requested review scope"
    ),
    ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH: (
        "review materialization inputs are structurally inconsistent"
    ),
}

_TECHNICAL_FINDING_FIELDS = frozenset(
    {
        "finding_id",
        "dimension",
        "severity",
        "description",
        "target_locator",
        "rationale",
        "correction_required",
        "evidence_refs",
        "confidence",
        "suggested_action",
    }
)
_STRUCTURED_PAYLOAD_FIELDS = frozenset(
    {
        "overall_assessment",
        "correction_required",
        "coverage",
        "confidence",
    }
)
_DIMENSIONS_BY_VALUE = {item.value: item for item in ReviewDimension}
_SEVERITIES_BY_VALUE = {item.value: item for item in FindingSeverity}
_ASSESSMENTS_BY_VALUE = {item.value: item for item in OverallAssessment}


class ReviewMaterializationError(ValueError):
    """Closed materialization failure exposing only a fixed safe reason."""

    code: ReviewMaterializationErrorCode
    safe_reason: str

    def __init__(self, code: ReviewMaterializationErrorCode) -> None:
        if type(code) is not ReviewMaterializationErrorCode:
            raise TypeError("code must be a ReviewMaterializationErrorCode")
        self.code = code
        self.safe_reason = _SAFE_ERROR_REASON[code]
        super().__init__(self.safe_reason)


@dataclass(frozen=True, slots=True)
class ReviewResultMaterializationRequest:
    prepared: PreparedReviewCall
    technical_result: ReviewPortResult
    result_meta: ContractMeta[ReviewStatus]
    review_id: str
    security_policy: ReviewSecurityPolicy = field(default_factory=ReviewSecurityPolicy)
    evidence_security_by_ref: EvidenceSecurityByRef = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.security_policy) is not ReviewSecurityPolicy:
            raise TypeError("security_policy must be a ReviewSecurityPolicy")
        object.__setattr__(
            self,
            "evidence_security_by_ref",
            freeze_evidence_security_by_ref(self.evidence_security_by_ref),
        )
        _validate_materialization_request(self)


def _validate_materialization_request(
    request: ReviewResultMaterializationRequest,
) -> None:
    if type(request.prepared) is not PreparedReviewCall:
        raise TypeError("prepared must be a PreparedReviewCall")
    if type(request.technical_result) is not ReviewPortResult:
        raise TypeError("technical_result must be a ReviewPortResult")
    if type(request.result_meta) is not ContractMeta:
        raise TypeError("result_meta must be a ContractMeta")
    if type(request.result_meta.status) is not ReviewStatus:
        raise TypeError("result_meta.status must be a ReviewStatus")
    try:
        require_non_empty(request.review_id, "review_id")
    except (TypeError, ValueError):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)

    prepared = request.prepared
    technical = request.technical_result
    canonical = prepared.canonical_request

    _revalidate_technical_result_shape(technical)
    reject_activatable_review_metadata(technical.structured_payload)
    reject_review_authority(technical.technical_findings)
    reject_review_diagnostics(technical.limitations, version=request.security_policy.metadata_policy_version,
                             surface=ReviewDiagnosticSurface.LIMITATIONS)
    reject_activatable_review_metadata(technical.warnings)
    reject_review_diagnostics(technical.uncertainties, version=request.security_policy.metadata_policy_version,
                             surface=ReviewDiagnosticSurface.UNCERTAINTIES)
    reject_activatable_review_metadata(technical.execution_metadata)

    if type(prepared.capability_id) is not CapabilityId:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if type(canonical) is not ReviewRequest or type(prepared.target) is not ResolvedReviewTarget:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if prepared.capability_id.value != "CAP-V01":
        _raise_materialization(ReviewMaterializationErrorCode.UNSUPPORTED_CAPABILITY)
    if prepared.target.target_production_ref != canonical.target_production_ref:
        _raise_materialization(ReviewMaterializationErrorCode.TARGET_MISMATCH)
    try:
        _validate_prepared_review_call(prepared)
    except (ReviewCoordinationError, TypeError):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if prepared.port_request.operation is not ReviewOperation.SEMANTIC_REVIEW:
        _raise_materialization(ReviewMaterializationErrorCode.OPERATION_MISMATCH)
    if prepared.target.target_production_ref != canonical.target_production_ref:
        _raise_materialization(ReviewMaterializationErrorCode.TARGET_MISMATCH)
    if technical.source_step_id != prepared.port_request.source_step_id:
        _raise_materialization(ReviewMaterializationErrorCode.SOURCE_STEP_MISMATCH)
    if technical.operation is not ReviewOperation.SEMANTIC_REVIEW:
        _raise_materialization(ReviewMaterializationErrorCode.OPERATION_MISMATCH)
    if type(technical.evidence_refs_used) is not tuple:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    try:
        all(
            _is_contract_ref(value, "evidence_ref_used")
            for value in technical.evidence_refs_used
        )
    except (TypeError, ValueError):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if len(technical.evidence_refs_used) != len(set(technical.evidence_refs_used)):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if not set(technical.evidence_refs_used).issubset(canonical.evidence_refs):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)

    expected_status = _review_status_for(technical.status)
    if request.result_meta.status is not expected_status:
        _raise_materialization(ReviewMaterializationErrorCode.STATUS_MISMATCH)
    _validate_result_meta(request.result_meta, canonical.meta)

    findings = _materialize_findings(request)
    _materialization_payload(request, findings)
    security = _review_security_assessment(request)
    require_security_output_allowed(security, request.security_policy)


def _review_status_for(status: ReviewPortResultStatus) -> ReviewStatus:
    if status is ReviewPortResultStatus.SUCCEEDED:
        return ReviewStatus.COMPLETED
    if status is ReviewPortResultStatus.PARTIAL:
        return ReviewStatus.INCOMPLETE
    if status in {ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED}:
        _raise_materialization(ReviewMaterializationErrorCode.NON_MATERIALIZABLE_STATUS)
    _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)


def _validate_result_meta(
    result_meta: ContractMeta[ReviewStatus],
    canonical_meta: ContractMeta[object],
) -> None:
    if (
        result_meta.schema_version != canonical_meta.schema_version
        or result_meta.run_id != canonical_meta.run_id
        or result_meta.step_id != canonical_meta.step_id
        or result_meta.correlation_id != canonical_meta.correlation_id
        or result_meta.actor.kind is not ActorKind.AGENT
        or result_meta.actor.actor_id != AgentId.AG_04.value
    ):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)


def _materialize_findings(
    request: ReviewResultMaterializationRequest,
) -> tuple[Finding, ...]:
    if type(request.technical_result.technical_findings) is not tuple:
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    findings = tuple(
        _materialize_finding(raw, request) for raw in request.technical_result.technical_findings
    )
    finding_ids = tuple(item.finding_id for item in findings)
    if len(finding_ids) != len(set(finding_ids)):
        _raise_materialization(ReviewMaterializationErrorCode.DUPLICATE_FINDING_ID)
    return findings


def _materialize_finding(
    raw: Mapping[str, object],
    request: ReviewResultMaterializationRequest,
) -> Finding:
    if not isinstance(raw, Mapping) or set(raw) != _TECHNICAL_FINDING_FIELDS:
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)

    finding_id = _required_text(raw["finding_id"])
    description = _required_text(raw["description"])
    rationale = _required_text(raw["rationale"])
    dimension = _closed_enum_value(raw["dimension"], _DIMENSIONS_BY_VALUE)
    if dimension is None:
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    canonical = request.prepared.canonical_request
    if dimension not in canonical.review_dimensions:
        _raise_materialization(ReviewMaterializationErrorCode.FINDING_DIMENSION_OUT_OF_SCOPE)
    severity = _closed_enum_value(raw["severity"], _SEVERITIES_BY_VALUE)
    if severity is None:
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    correction_required = raw["correction_required"]
    if type(correction_required) is not bool:
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    evidence_refs = _evidence_refs(raw["evidence_refs"])
    if not set(evidence_refs).issubset(canonical.evidence_refs):
        _raise_materialization(ReviewMaterializationErrorCode.FINDING_EVIDENCE_OUT_OF_SCOPE)
    if not set(evidence_refs).issubset(request.technical_result.evidence_refs_used):
        _raise_materialization(ReviewMaterializationErrorCode.FINDING_EVIDENCE_NOT_USED)
    target_locator = _agent_safe_mapping(raw["target_locator"])
    if request.security_policy.require_locator_validation:
        validate_finding_locator(
            request.prepared.target,
            target_locator,
            policy=request.security_policy,
        )
    confidence = _agent_safe_mapping(raw["confidence"])
    suggested_action = _agent_safe_mapping(raw["suggested_action"])
    reject_activatable_review_metadata(confidence)
    reject_activatable_review_metadata(suggested_action)
    return Finding(
        finding_id=finding_id,
        dimension=dimension,
        severity=severity,
        description=description,
        target_locator=target_locator,
        rationale=rationale,
        correction_required=correction_required,
        evidence_refs=evidence_refs,
        confidence=confidence,
        suggested_action=suggested_action,
    )


def _materialization_payload(
    request: ReviewResultMaterializationRequest,
    findings: tuple[Finding, ...],
) -> tuple[OverallAssessment, bool, tuple[ReviewDimension, ...], Mapping[str, object]]:
    payload = request.technical_result.structured_payload
    if set(payload) != _STRUCTURED_PAYLOAD_FIELDS:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    assessment = _closed_enum_value(payload["overall_assessment"], _ASSESSMENTS_BY_VALUE)
    if assessment is None:
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_OVERALL_ASSESSMENT)
    correction_required = payload["correction_required"]
    if type(correction_required) is not bool:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    coverage = _coverage(payload["coverage"], request)
    if any(finding.dimension not in coverage for finding in findings):
        _raise_materialization(ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE)
    confidence = _agent_safe_mapping(payload["confidence"])
    _validate_c10_coherence(
        request.result_meta.status,
        findings,
        assessment,
        correction_required,
        coverage,
    )
    return assessment, correction_required, coverage, confidence


def _coverage(
    raw: object,
    request: ReviewResultMaterializationRequest,
) -> tuple[ReviewDimension, ...]:
    if type(raw) is not tuple:
        _raise_materialization(ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE)
    raw_values = cast(tuple[object, ...], raw)
    coverage: tuple[ReviewDimension, ...] = tuple(
        value
        for item in raw_values
        if (value := _closed_enum_value(item, _DIMENSIONS_BY_VALUE)) is not None
    )
    if len(coverage) != len(raw_values) or len(coverage) != len(set(coverage)):
        _raise_materialization(ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE)
    if request.result_meta.status is ReviewStatus.COMPLETED and not coverage:
        _raise_materialization(ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE)
    if not set(coverage).issubset(request.prepared.canonical_request.review_dimensions):
        _raise_materialization(ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE)
    return coverage


def _validate_c10_coherence(
    status: ReviewStatus,
    findings: tuple[Finding, ...],
    assessment: OverallAssessment,
    correction_required: bool,
    coverage: tuple[ReviewDimension, ...],
) -> None:
    finding_requires_correction = any(item.correction_required for item in findings)
    if finding_requires_correction and not correction_required:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if assessment is OverallAssessment.CORRECTION_REQUIRED and not correction_required:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if assessment is OverallAssessment.ACCEPTABLE and (
        correction_required or finding_requires_correction
    ):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if status is ReviewStatus.INCOMPLETE and assessment is OverallAssessment.ACCEPTABLE:
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)
    if status is ReviewStatus.COMPLETED and not coverage:
        _raise_materialization(ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE)


def _required_text(raw: object) -> str:
    if type(raw) is not str or not raw.strip():
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    return raw


def _closed_enum_value[T: StrEnum](
    raw: object,
    values: Mapping[str, T],
) -> T | None:
    if type(raw) is not str:
        return None
    return values.get(raw)


def _evidence_refs(raw: object) -> tuple[ContractRef, ...]:
    if type(raw) is not tuple:
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    values = cast(tuple[ContractRef, ...], raw)
    try:
        all(_is_contract_ref(value, "evidence_ref") for value in values)
    except (TypeError, ValueError):
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    if len(values) != len(set(values)):
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    return values


def _is_contract_ref(value: ContractRef, field_name: str) -> bool:
    require_contract_ref(value, field_name)
    return True


def _agent_safe_mapping(raw: object) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    try:
        frozen = freeze_agent_safe_mapping(cast(Mapping[str, object], raw))
    except (TypeError, ValueError):
        _raise_materialization(ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING)
    reject_review_authority(frozen)
    return frozen


def _revalidate_technical_result_shape(technical: ReviewPortResult) -> None:
    try:
        freeze_agent_safe_mapping(technical.structured_payload)
        freeze_agent_safe_mapping(technical.execution_metadata)
        structured_sequences = (
            technical.technical_findings,
            technical.limitations,
            technical.warnings,
            technical.uncertainties,
        )
        if any(
            type(values) is not tuple
            or any(not isinstance(value, Mapping) for value in values)
            for values in structured_sequences
        ):
            raise TypeError("technical sequences must contain mappings")
        tuple(
            freeze_agent_safe_mapping(value)
            for values in structured_sequences
            for value in values
        )
    except (TypeError, ValueError):
        _raise_materialization(ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH)


def _review_security_assessment(
    request: ReviewResultMaterializationRequest,
) -> ReviewSecurityAssessment:
    return ReviewSecurityGuard().assess(
        target=request.prepared.target,
        policy=request.security_policy,
        review_evidence_refs=request.prepared.canonical_request.evidence_refs,
        required_evidence_refs=request.technical_result.evidence_refs_used,
        evidence_security_by_ref=request.evidence_security_by_ref,
    )


def _raise_materialization(code: ReviewMaterializationErrorCode) -> NoReturn:
    raise ReviewMaterializationError(code) from None
