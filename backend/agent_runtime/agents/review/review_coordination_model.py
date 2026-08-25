from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.agents.review.review_model import (
    ReviewOperation,
    ReviewPortRequest,
)
from backend.agent_runtime.contracts import ReviewRequest
from backend.agent_runtime.contracts.common import freeze_agent_safe_mapping
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.references import ObjectVersionRef


class ReviewCoordinationErrorCode(StrEnum):
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    CAPABILITY_OPERATION_MISMATCH = "CAPABILITY_OPERATION_MISMATCH"
    TARGET_REF_MISMATCH = "TARGET_REF_MISMATCH"
    SOURCE_STEP_MISMATCH = "SOURCE_STEP_MISMATCH"
    OPERATION_MISMATCH = "OPERATION_MISMATCH"
    EVIDENCE_REF_OUT_OF_SCOPE = "EVIDENCE_REF_OUT_OF_SCOPE"
    DUPLICATE_EVIDENCE_REF_USED = "DUPLICATE_EVIDENCE_REF_USED"
    PREPARATION_MISMATCH = "PREPARATION_MISMATCH"


_SAFE_ERROR_REASON: Mapping[ReviewCoordinationErrorCode, str] = {
    ReviewCoordinationErrorCode.UNSUPPORTED_CAPABILITY: (
        "capability is not supported by review coordination"
    ),
    ReviewCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH: (
        "capability does not match the prepared review operation"
    ),
    ReviewCoordinationErrorCode.TARGET_REF_MISMATCH: (
        "review target does not match the canonical request"
    ),
    ReviewCoordinationErrorCode.SOURCE_STEP_MISMATCH: (
        "source step does not match the prepared review request"
    ),
    ReviewCoordinationErrorCode.OPERATION_MISMATCH: (
        "result operation does not match the prepared review request"
    ),
    ReviewCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE: (
        "result evidence is outside the canonical review scope"
    ),
    ReviewCoordinationErrorCode.DUPLICATE_EVIDENCE_REF_USED: (
        "result contains duplicate evidence references"
    ),
    ReviewCoordinationErrorCode.PREPARATION_MISMATCH: (
        "prepared review fields do not match the preparation snapshot"
    ),
}


class ReviewCoordinationError(ValueError):
    """Closed coordination failure exposing only a fixed agent-safe reason."""

    code: ReviewCoordinationErrorCode
    safe_reason: str

    def __init__(self, code: ReviewCoordinationErrorCode) -> None:
        if type(code) is not ReviewCoordinationErrorCode:
            raise TypeError("code must be a ReviewCoordinationErrorCode")
        self.code = code
        self.safe_reason = _SAFE_ERROR_REASON[code]
        super().__init__(self.safe_reason)


@dataclass(frozen=True, slots=True)
class ResolvedReviewTarget:
    """Caller-resolved target data bound to one exact production version."""

    target_production_ref: ObjectVersionRef
    content: str | None = None
    structured_payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.target_production_ref) is not ObjectVersionRef:
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        if self.content is not None:
            if type(self.content) is not str:
                raise TypeError("content must be a str or None")
            if not self.content.strip():
                raise ValueError("content must not be empty")
        structured_payload = freeze_agent_safe_mapping(self.structured_payload)
        if self.content is None and not structured_payload:
            raise ValueError("content or structured_payload is required")
        object.__setattr__(self, "structured_payload", structured_payload)


@dataclass(frozen=True, slots=True)
class ReviewPreparationRequest:
    capability_id: CapabilityId
    request: ReviewRequest
    target: ResolvedReviewTarget
    resolved_inputs: Mapping[str, object] = field(default_factory=dict)
    output_contract: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.capability_id) is not CapabilityId:
            raise TypeError("capability_id must be a CapabilityId")
        if type(self.request) is not ReviewRequest:
            raise TypeError("request must be a ReviewRequest")
        if type(self.target) is not ResolvedReviewTarget:
            raise TypeError("target must be a ResolvedReviewTarget")
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


@dataclass(frozen=True, slots=True)
class PreparedReviewCall:
    preparation_request: ReviewPreparationRequest
    capability_id: CapabilityId
    canonical_request: ReviewRequest
    target: ResolvedReviewTarget
    port_request: ReviewPortRequest

    def __post_init__(self) -> None:
        _validate_prepared_review_call(self)


def _operation_for_capability(capability_id: CapabilityId) -> ReviewOperation:
    if type(capability_id) is not CapabilityId:
        raise TypeError("capability_id must be a CapabilityId")
    if capability_id.value == "CAP-V01":
        return ReviewOperation.SEMANTIC_REVIEW
    if capability_id.value == "CAP-V02":
        return ReviewOperation.ASSESS_FINDINGS
    raise ReviewCoordinationError(ReviewCoordinationErrorCode.UNSUPPORTED_CAPABILITY)


def _coverage_context_for(request: ReviewRequest) -> Mapping[str, object]:
    return {
        "severity_policy": request.severity_policy,
        "context_slice": request.context_slice,
        "independence_requirements": request.independence_requirements,
    }


def _validate_prepared_review_call(prepared: PreparedReviewCall) -> None:
    if type(prepared.preparation_request) is not ReviewPreparationRequest:
        raise TypeError("preparation_request must be a ReviewPreparationRequest")
    if type(prepared.capability_id) is not CapabilityId:
        raise TypeError("capability_id must be a CapabilityId")
    if type(prepared.canonical_request) is not ReviewRequest:
        raise TypeError("canonical_request must be a ReviewRequest")
    if type(prepared.target) is not ResolvedReviewTarget:
        raise TypeError("target must be a ResolvedReviewTarget")
    if type(prepared.port_request) is not ReviewPortRequest:
        raise TypeError("port_request must be a ReviewPortRequest")

    snapshot = prepared.preparation_request
    canonical = prepared.canonical_request
    target = prepared.target
    technical = prepared.port_request
    expected_operation = _operation_for_capability(prepared.capability_id)

    if snapshot.capability_id != prepared.capability_id:
        _raise_coordination(ReviewCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH)
    if snapshot.request != canonical or snapshot.target != target:
        _raise_coordination(ReviewCoordinationErrorCode.PREPARATION_MISMATCH)
    if target.target_production_ref != canonical.target_production_ref:
        _raise_coordination(ReviewCoordinationErrorCode.TARGET_REF_MISMATCH)
    if technical.capability_id != prepared.capability_id:
        _raise_coordination(ReviewCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH)
    if technical.operation is not expected_operation:
        _raise_coordination(ReviewCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH)
    if technical.source_step_id != canonical.meta.step_id:
        _raise_coordination(ReviewCoordinationErrorCode.SOURCE_STEP_MISMATCH)
    if technical.target_production_ref != canonical.target_production_ref:
        _raise_coordination(ReviewCoordinationErrorCode.TARGET_REF_MISMATCH)

    exact_pairs = (
        (technical.target_content, target.content),
        (technical.target_payload, target.structured_payload),
        (technical.review_dimensions, canonical.review_dimensions),
        (technical.criteria, canonical.criteria),
        (technical.evidence_refs, canonical.evidence_refs),
        (technical.coverage_context, _coverage_context_for(canonical)),
        (technical.resolved_inputs, snapshot.resolved_inputs),
        (technical.output_contract, snapshot.output_contract),
        (technical.review_budget, canonical.review_budget),
    )
    if any(actual != expected for actual, expected in exact_pairs):
        _raise_coordination(ReviewCoordinationErrorCode.PREPARATION_MISMATCH)


def _raise_coordination(code: ReviewCoordinationErrorCode) -> None:
    raise ReviewCoordinationError(code)
