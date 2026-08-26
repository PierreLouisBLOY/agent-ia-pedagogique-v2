from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import NoReturn

from backend.agent_runtime.agents.review.review_coordination_model import (
    ResolvedReviewTarget,
)
from backend.agent_runtime.agents.review.review_model import ReviewPortResultStatus
from backend.agent_runtime.agents.review.review_security import (
    ReviewSecurityGuard,
    finding_lineage_fingerprint,
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
    ReviewSecuritySignalCode,
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
    ReviewResult,
    ReviewStatus,
)
from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef


class ReviewAssessmentErrorCode(StrEnum):
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    SOURCE_REVIEW_MISMATCH = "SOURCE_REVIEW_MISMATCH"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    REVIEW_REF_INVALID = "REVIEW_REF_INVALID"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    NON_ASSESSABLE_STATUS = "NON_ASSESSABLE_STATUS"
    SOURCE_STEP_MISMATCH = "SOURCE_STEP_MISMATCH"
    OPERATION_MISMATCH = "OPERATION_MISMATCH"
    TECHNICAL_FINDINGS_FORBIDDEN = "TECHNICAL_FINDINGS_FORBIDDEN"
    INVALID_TECHNICAL_PAYLOAD = "INVALID_TECHNICAL_PAYLOAD"
    ASSESSED_IDS_MISMATCH = "ASSESSED_IDS_MISMATCH"
    BLOCKING_IDS_MISMATCH = "BLOCKING_IDS_MISMATCH"
    CORRECTION_IDS_MISMATCH = "CORRECTION_IDS_MISMATCH"
    INVALID_ASSESSMENT = "INVALID_ASSESSMENT"
    ASSESSMENT_INCOHERENT = "ASSESSMENT_INCOHERENT"
    EVIDENCE_OUT_OF_SCOPE = "EVIDENCE_OUT_OF_SCOPE"
    AUTHORITY_METADATA_FORBIDDEN = "AUTHORITY_METADATA_FORBIDDEN"


_SAFE_ERROR_REASON: Mapping[ReviewAssessmentErrorCode, str] = {
    ReviewAssessmentErrorCode.UNSUPPORTED_CAPABILITY: (
        "findings assessment requires the dedicated review capability"
    ),
    ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH: (
        "source review does not match its canonical request"
    ),
    ReviewAssessmentErrorCode.TARGET_MISMATCH: (
        "assessment target does not match the source review lineage"
    ),
    ReviewAssessmentErrorCode.REVIEW_REF_INVALID: (
        "assessment review reference is invalid"
    ),
    ReviewAssessmentErrorCode.SNAPSHOT_MISMATCH: (
        "prepared findings snapshot does not match the source review"
    ),
    ReviewAssessmentErrorCode.NON_ASSESSABLE_STATUS: (
        "technical assessment status cannot produce a signal"
    ),
    ReviewAssessmentErrorCode.SOURCE_STEP_MISMATCH: (
        "technical assessment source step does not match the request"
    ),
    ReviewAssessmentErrorCode.OPERATION_MISMATCH: (
        "technical assessment operation does not match findings assessment"
    ),
    ReviewAssessmentErrorCode.TECHNICAL_FINDINGS_FORBIDDEN: (
        "findings assessment cannot introduce new technical findings"
    ),
    ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD: (
        "technical assessment payload does not match the closed schema"
    ),
    ReviewAssessmentErrorCode.ASSESSED_IDS_MISMATCH: (
        "assessed finding identifiers do not match the source review"
    ),
    ReviewAssessmentErrorCode.BLOCKING_IDS_MISMATCH: (
        "blocking finding identifiers do not match deterministic severity"
    ),
    ReviewAssessmentErrorCode.CORRECTION_IDS_MISMATCH: (
        "correction finding identifiers do not match deterministic requirements"
    ),
    ReviewAssessmentErrorCode.INVALID_ASSESSMENT: (
        "technical assessment value is not canonical"
    ),
    ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT: (
        "technical assessment is inconsistent with deterministic findings"
    ),
    ReviewAssessmentErrorCode.EVIDENCE_OUT_OF_SCOPE: (
        "assessment evidence is outside source review scope"
    ),
    ReviewAssessmentErrorCode.AUTHORITY_METADATA_FORBIDDEN: (
        "technical assessment metadata contains authority vocabulary"
    ),
}

_ASSESSMENT_PAYLOAD_FIELDS = frozenset(
    {
        "assessed_finding_ids",
        "blocking_finding_ids",
        "correction_finding_ids",
        "overall_assessment",
        "correction_required",
        "confidence",
    }
)


def _default_output_contract() -> dict[str, object]:
    return {
        "operation": "ASSESS_FINDINGS",
        "technical_findings": "EMPTY",
        "structured_payload_fields": tuple(sorted(_ASSESSMENT_PAYLOAD_FIELDS)),
    }


class ReviewAssessmentError(ValueError):
    """Closed CAP-V02 failure exposing only a fixed agent-safe reason."""

    code: ReviewAssessmentErrorCode
    safe_reason: str

    def __init__(self, code: ReviewAssessmentErrorCode) -> None:
        if type(code) is not ReviewAssessmentErrorCode:
            raise TypeError("code must be a ReviewAssessmentErrorCode")
        self.code = code
        self.safe_reason = _SAFE_ERROR_REASON[code]
        super().__init__(self.safe_reason)


@dataclass(frozen=True, slots=True)
class FindingsAssessmentRequest:
    capability_id: CapabilityId
    source_request: ReviewRequest
    source_result: ReviewResult
    target: ResolvedReviewTarget
    review_ref: ContractRef
    resolved_inputs: Mapping[str, object] = field(default_factory=dict)
    output_contract: Mapping[str, object] = field(default_factory=_default_output_contract)
    security_policy: ReviewSecurityPolicy = field(default_factory=ReviewSecurityPolicy)
    evidence_security_by_ref: EvidenceSecurityByRef = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.capability_id) is not CapabilityId:
            raise TypeError("capability_id must be a CapabilityId")
        if type(self.source_request) is not ReviewRequest:
            raise TypeError("source_request must be a ReviewRequest")
        if type(self.source_result) is not ReviewResult:
            raise TypeError("source_result must be a ReviewResult")
        if type(self.target) is not ResolvedReviewTarget:
            raise TypeError("target must be a ResolvedReviewTarget")
        if type(self.security_policy) is not ReviewSecurityPolicy:
            raise TypeError("security_policy must be a ReviewSecurityPolicy")
        object.__setattr__(
            self,
            "resolved_inputs",
            freeze_agent_safe_mapping(self.resolved_inputs),
        )
        object.__setattr__(
            self,
            "output_contract",
            freeze_agent_safe_mapping(self.output_contract),
        )
        object.__setattr__(
            self,
            "evidence_security_by_ref",
            freeze_evidence_security_by_ref(self.evidence_security_by_ref),
        )
        _validate_findings_assessment_request(self)


@dataclass(frozen=True, slots=True)
class ReviewAssessmentSignal:
    review_ref: ContractRef
    review_id: str
    target_production_ref: ObjectVersionRef
    assessed_finding_ids: tuple[str, ...]
    blocking_finding_ids: tuple[str, ...]
    correction_finding_ids: tuple[str, ...]
    overall_assessment: OverallAssessment
    correction_required: bool
    promotion_blocked_by_review: bool
    evidence_refs_used: tuple[ContractRef, ...]
    confidence: Mapping[str, object]
    limitations: tuple[Mapping[str, object], ...]
    warnings: tuple[Mapping[str, object], ...]
    technical_status: ReviewPortResultStatus
    target_snapshot_fingerprint: str
    finding_lineage_fingerprints: tuple[tuple[str, str], ...]
    security_signal_codes: tuple[ReviewSecuritySignalCode, ...]

    def __post_init__(self) -> None:
        _require_contract_ref(self.review_ref)
        require_non_empty(self.review_id, "review_id")
        if type(self.target_production_ref) is not ObjectVersionRef:
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        _validate_id_tuple(self.assessed_finding_ids, "assessed_finding_ids")
        _validate_id_tuple(self.blocking_finding_ids, "blocking_finding_ids")
        _validate_id_tuple(self.correction_finding_ids, "correction_finding_ids")
        if not set(self.blocking_finding_ids).issubset(self.assessed_finding_ids):
            raise ValueError("blocking findings must be assessed")
        if not set(self.correction_finding_ids).issubset(self.assessed_finding_ids):
            raise ValueError("correction findings must be assessed")
        if type(self.overall_assessment) is not OverallAssessment:
            raise TypeError("overall_assessment must be an OverallAssessment")
        if type(self.correction_required) is not bool:
            raise TypeError("correction_required must be a bool")
        if type(self.promotion_blocked_by_review) is not bool:
            raise TypeError("promotion_blocked_by_review must be a bool")
        if self.promotion_blocked_by_review != bool(self.blocking_finding_ids):
            raise ValueError("promotion blocking signal must match blocking findings")
        _validate_ref_tuple(self.evidence_refs_used, "evidence_refs_used")
        if type(self.technical_status) is not ReviewPortResultStatus:
            raise TypeError("technical_status must be a ReviewPortResultStatus")
        require_non_empty(
            self.target_snapshot_fingerprint,
            "target_snapshot_fingerprint",
        )
        if type(self.finding_lineage_fingerprints) is not tuple or any(
            type(item) is not tuple
            or len(item) != 2
            or any(type(value) is not str or not value for value in item)
            for item in self.finding_lineage_fingerprints
        ):
            raise TypeError("finding lineage fingerprints must be string pairs")
        if tuple(item[0] for item in self.finding_lineage_fingerprints) != (
            self.assessed_finding_ids
        ):
            raise ValueError("finding lineage fingerprints must match assessed findings")
        if type(self.security_signal_codes) is not tuple or any(
            type(code) is not ReviewSecuritySignalCode
            for code in self.security_signal_codes
        ):
            raise TypeError("security_signal_codes must contain review security codes")
        object.__setattr__(self, "confidence", freeze_agent_safe_mapping(self.confidence))
        object.__setattr__(self, "limitations", _freeze_mapping_tuple(self.limitations))
        object.__setattr__(self, "warnings", _freeze_mapping_tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class CorrectionHandoffSignal:
    destination_agent_id: AgentId
    review_ref: ContractRef
    review_id: str
    target_production_ref: ObjectVersionRef
    finding_ids: tuple[str, ...]
    blocking_finding_ids: tuple[str, ...]
    evidence_refs: tuple[ContractRef, ...]
    suggested_actions: tuple[Mapping[str, object], ...]
    limitations: tuple[Mapping[str, object], ...]
    warnings: tuple[Mapping[str, object], ...]
    security_signal_codes: tuple[ReviewSecuritySignalCode, ...]

    def __post_init__(self) -> None:
        if self.destination_agent_id is not AgentId.AG_01:
            raise ValueError("correction handoff destination must be AG-01")
        _require_contract_ref(self.review_ref)
        require_non_empty(self.review_id, "review_id")
        if type(self.target_production_ref) is not ObjectVersionRef:
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        _validate_id_tuple(self.finding_ids, "finding_ids")
        if not self.finding_ids:
            raise ValueError("finding_ids must not be empty")
        _validate_id_tuple(self.blocking_finding_ids, "blocking_finding_ids")
        if not set(self.blocking_finding_ids).issubset(self.finding_ids):
            raise ValueError("blocking findings must be included in handoff findings")
        _validate_ref_tuple(self.evidence_refs, "evidence_refs")
        object.__setattr__(
            self,
            "suggested_actions",
            _freeze_mapping_tuple(self.suggested_actions),
        )
        object.__setattr__(self, "limitations", _freeze_mapping_tuple(self.limitations))
        object.__setattr__(self, "warnings", _freeze_mapping_tuple(self.warnings))
        if type(self.security_signal_codes) is not tuple or any(
            type(code) is not ReviewSecuritySignalCode
            for code in self.security_signal_codes
        ):
            raise TypeError("security_signal_codes must contain review security codes")


def _validate_findings_assessment_request(request: FindingsAssessmentRequest) -> None:
    if request.capability_id.value != "CAP-V02":
        _raise_assessment(ReviewAssessmentErrorCode.UNSUPPORTED_CAPABILITY)
    _require_contract_ref(request.review_ref)
    if request.output_contract != _default_output_contract():
        _raise_assessment(ReviewAssessmentErrorCode.SNAPSHOT_MISMATCH)
    try:
        reject_activatable_review_metadata(request.resolved_inputs)
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.AUTHORITY_METADATA_FORBIDDEN)

    source_request = request.source_request
    source_result = request.source_result
    if (
        type(source_request.meta) is not ContractMeta
        or type(source_request.target_production_ref) is not ObjectVersionRef
        or type(source_request.review_dimensions) is not tuple
        or any(
            type(item) is not ReviewDimension
            for item in source_request.review_dimensions
        )
        or len(source_request.review_dimensions)
        != len(set(source_request.review_dimensions))
        or type(source_request.evidence_refs) is not tuple
    ):
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH)
    try:
        _validate_ref_tuple(source_request.evidence_refs, "source_evidence_refs")
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.EVIDENCE_OUT_OF_SCOPE)
    target_ref = source_request.target_production_ref
    if (
        type(source_result.meta) is not ContractMeta
        or type(source_result.target_production_ref) is not ObjectVersionRef
        or type(source_result.findings) is not tuple
        or type(source_result.coverage) is not tuple
        or any(type(item) is not ReviewDimension for item in source_result.coverage)
        or len(source_result.coverage) != len(set(source_result.coverage))
        or type(source_result.evidence_refs_used) is not tuple
        or not isinstance(source_result.confidence, Mapping)
        or type(source_result.limitations) is not tuple
        or type(source_result.warnings) is not tuple
        or any(
            not isinstance(item, Mapping)
            for item in source_result.limitations + source_result.warnings
        )
    ):
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH)
    try:
        require_non_empty(source_result.review_id, "review_id")
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH)
    if (
        source_result.target_production_ref != target_ref
        or request.target.target_production_ref != target_ref
    ):
        _raise_assessment(ReviewAssessmentErrorCode.TARGET_MISMATCH)
    if (
        source_result.meta.schema_version != source_request.meta.schema_version
        or source_result.meta.run_id != source_request.meta.run_id
        or source_result.meta.step_id != source_request.meta.step_id
        or source_result.meta.correlation_id != source_request.meta.correlation_id
        or source_result.meta.actor.kind is not ActorKind.AGENT
        or source_result.meta.actor.actor_id != AgentId.AG_04.value
        or source_result.meta.status not in {ReviewStatus.COMPLETED, ReviewStatus.INCOMPLETE}
        or type(source_result.overall_assessment) is not OverallAssessment
        or type(source_result.correction_required) is not bool
    ):
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH)

    if type(source_result.findings) is not tuple or any(
        type(finding) is not Finding
        or type(finding.dimension) is not ReviewDimension
        or type(finding.severity) is not FindingSeverity
        or type(finding.correction_required) is not bool
        or type(finding.description) is not str
        or not finding.description.strip()
        or type(finding.rationale) is not str
        or not finding.rationale.strip()
        or not isinstance(finding.target_locator, Mapping)
        or not isinstance(finding.confidence, Mapping)
        or not isinstance(finding.suggested_action, Mapping)
        for finding in source_result.findings
    ):
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH)
    finding_ids = tuple(finding.finding_id for finding in source_result.findings)
    _validate_id_tuple(finding_ids, "finding_ids")
    if not set(source_result.coverage).issubset(source_request.review_dimensions):
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH)
    try:
        _validate_ref_tuple(source_result.evidence_refs_used, "evidence_refs_used")
        all(
            _validated_finding_evidence(finding.evidence_refs)
            for finding in source_result.findings
        )
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.EVIDENCE_OUT_OF_SCOPE)
    if not set(source_result.evidence_refs_used).issubset(source_request.evidence_refs):
        _raise_assessment(ReviewAssessmentErrorCode.EVIDENCE_OUT_OF_SCOPE)
    if any(
        finding.dimension not in source_request.review_dimensions
        or len(finding.evidence_refs) != len(set(finding.evidence_refs))
        or not set(finding.evidence_refs).issubset(source_request.evidence_refs)
        or not set(finding.evidence_refs).issubset(source_result.evidence_refs_used)
        for finding in source_result.findings
    ):
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_REVIEW_MISMATCH)
    reject_activatable_review_metadata(source_result.confidence)
    reject_activatable_review_metadata(source_result.limitations)
    reject_activatable_review_metadata(source_result.warnings)
    for finding in source_result.findings:
        reject_review_authority(finding.target_locator)
        reject_activatable_review_metadata(finding.confidence)
        reject_activatable_review_metadata(finding.suggested_action)
        finding_lineage_fingerprint(finding)
        if request.security_policy.require_locator_validation:
            validate_finding_locator(
                request.target,
                finding.target_locator,
                policy=request.security_policy,
            )
    blocking_ids = _blocking_finding_ids(source_result)
    if blocking_ids and not source_result.correction_required:
        _raise_assessment(ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT)
    security = _assessment_request_security(request)
    require_security_output_allowed(security, request.security_policy)


def _assessment_request_security(
    request: FindingsAssessmentRequest,
) -> ReviewSecurityAssessment:
    return ReviewSecurityGuard().assess(
        target=request.target,
        policy=request.security_policy,
        review_evidence_refs=request.source_request.evidence_refs,
        required_evidence_refs=request.source_result.evidence_refs_used,
        evidence_security_by_ref=request.evidence_security_by_ref,
    )


def _blocking_finding_ids(source_result: ReviewResult) -> tuple[str, ...]:
    return tuple(
        finding.finding_id
        for finding in source_result.findings
        if finding.severity is FindingSeverity.BLOCKING
    )


def _correction_finding_ids(source_result: ReviewResult) -> tuple[str, ...]:
    return tuple(
        finding.finding_id
        for finding in source_result.findings
        if finding.correction_required or finding.severity is FindingSeverity.BLOCKING
    )


def _validate_id_tuple(values: tuple[str, ...], field_name: str) -> None:
    if type(values) is not tuple:
        raise TypeError(f"{field_name} must be a tuple")
    if any(type(value) is not str or not value.strip() for value in values):
        raise ValueError(f"{field_name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")


def _validate_ref_tuple(values: tuple[ContractRef, ...], field_name: str) -> None:
    if type(values) is not tuple:
        raise TypeError(f"{field_name} must be a tuple")
    try:
        all(_is_contract_ref(value, field_name) for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} contains an invalid reference") from error
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique references")


def _require_contract_ref(value: ContractRef) -> None:
    try:
        require_contract_ref(value, "review_ref")
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.REVIEW_REF_INVALID)


def _is_contract_ref(value: ContractRef, field_name: str) -> bool:
    require_contract_ref(value, field_name)
    return True


def _validated_finding_evidence(values: tuple[ContractRef, ...]) -> bool:
    _validate_ref_tuple(values, "finding_evidence_refs")
    return True


def _freeze_mapping_tuple(
    values: tuple[Mapping[str, object], ...],
) -> tuple[Mapping[str, object], ...]:
    if type(values) is not tuple:
        raise TypeError("structured mappings must be a tuple")
    return tuple(freeze_agent_safe_mapping(value) for value in values)


def _raise_assessment(code: ReviewAssessmentErrorCode) -> NoReturn:
    raise ReviewAssessmentError(code) from None
