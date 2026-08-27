from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.agents.generation.generation_model import (
    GenerationOperation,
    GenerationPortRequest,
)
from backend.agent_runtime.contracts import (
    LabeledContent,
    LabeledEvidenceItem,
    ProductionRequest,
)
from backend.agent_runtime.contracts.common import freeze_agent_safe_mapping
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentTrustClass,
    SecurityBoundary,
    StructuredContentSecurityAssessment,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class GenerationCoordinationErrorCode(StrEnum):
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    CAPABILITY_OPERATION_MISMATCH = "CAPABILITY_OPERATION_MISMATCH"
    TARGET_FORBIDDEN_FOR_GENERATE = "TARGET_FORBIDDEN_FOR_GENERATE"
    TARGET_REQUIRED_FOR_TRANSFORM = "TARGET_REQUIRED_FOR_TRANSFORM"
    CORRECTION_REQUEST_REQUIRED = "CORRECTION_REQUEST_REQUIRED"
    SOURCE_STEP_MISMATCH = "SOURCE_STEP_MISMATCH"
    OPERATION_MISMATCH = "OPERATION_MISMATCH"
    EVIDENCE_REF_OUT_OF_SCOPE = "EVIDENCE_REF_OUT_OF_SCOPE"
    DUPLICATE_EVIDENCE_REF_USED = "DUPLICATE_EVIDENCE_REF_USED"


class GenerationCoordinationError(ValueError):
    code: GenerationCoordinationErrorCode
    safe_reason: str

    def __init__(
        self,
        code: GenerationCoordinationErrorCode,
        safe_reason: str,
    ) -> None:
        if type(code) is not GenerationCoordinationErrorCode:
            raise TypeError("code must be a GenerationCoordinationErrorCode")
        require_non_empty(safe_reason, "safe_reason")
        self.code = code
        self.safe_reason = safe_reason
        super().__init__(safe_reason)


@dataclass(frozen=True, slots=True)
class GenerationPreparationRequest:
    capability_id: CapabilityId
    request: ProductionRequest
    resolved_inputs: Mapping[str, object] = field(default_factory=dict)
    output_contract: Mapping[str, object] = field(default_factory=dict)
    labeled_evidence: tuple[LabeledEvidenceItem, ...] = ()
    labeled_inputs: tuple[LabeledContent, ...] = ()
    input_security_assessments: tuple[StructuredContentSecurityAssessment, ...] = ()

    def __post_init__(self) -> None:
        if type(self.capability_id) is not CapabilityId:
            raise TypeError("capability_id must be a CapabilityId")
        if type(self.request) is not ProductionRequest:
            raise TypeError("request must be a ProductionRequest")
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
        _validate_labeled_evidence(self.labeled_evidence, self.request.evidence_refs)
        _validate_labeled_inputs(
            self.labeled_inputs,
            self.input_security_assessments,
        )


@dataclass(frozen=True, slots=True)
class PreparedGenerationCall:
    preparation_request: GenerationPreparationRequest
    capability_id: CapabilityId
    canonical_request: ProductionRequest
    port_request: GenerationPortRequest

    def __post_init__(self) -> None:
        _validate_prepared_call(self)


def _operation_for_capability(capability_id: CapabilityId) -> GenerationOperation:
    if type(capability_id) is not CapabilityId:
        raise TypeError("capability_id must be a CapabilityId")
    if capability_id.value == "CAP-G01":
        return GenerationOperation.GENERATE
    if capability_id.value == "CAP-G02":
        return GenerationOperation.TRANSFORM
    if capability_id.value == "CAP-G03":
        return GenerationOperation.CORRECT
    raise GenerationCoordinationError(
        GenerationCoordinationErrorCode.UNSUPPORTED_CAPABILITY,
        "capability is not supported by production request coordination",
    )


def _validate_prepared_call(prepared: PreparedGenerationCall) -> None:
    if type(prepared.preparation_request) is not GenerationPreparationRequest:
        raise TypeError("preparation_request must be a GenerationPreparationRequest")
    if type(prepared.capability_id) is not CapabilityId:
        raise TypeError("capability_id must be a CapabilityId")
    if type(prepared.canonical_request) is not ProductionRequest:
        raise TypeError("canonical_request must be a ProductionRequest")
    if type(prepared.port_request) is not GenerationPortRequest:
        raise TypeError("port_request must be a GenerationPortRequest")

    expected_operation = _operation_for_capability(prepared.capability_id)
    if expected_operation is GenerationOperation.CORRECT:
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.CORRECTION_REQUEST_REQUIRED,
            "CAP-G03 requires a CorrectionRequest",
        )
    snapshot = prepared.preparation_request
    canonical = prepared.canonical_request
    technical = prepared.port_request
    _validate_labeled_evidence(snapshot.labeled_evidence, canonical.evidence_refs)
    _validate_labeled_inputs(
        snapshot.labeled_inputs,
        snapshot.input_security_assessments,
    )
    if (
        snapshot.capability_id != prepared.capability_id
        or snapshot.request != canonical
    ):
        _raise_mismatch(
            GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH,
            "prepared generation fields do not match the preparation snapshot",
        )
    if technical.operation is not expected_operation:
        _raise_mismatch(
            GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH,
            "capability does not match the prepared generation operation",
        )
    if technical.source_step_id != canonical.meta.step_id:
        _raise_mismatch(
            GenerationCoordinationErrorCode.SOURCE_STEP_MISMATCH,
            "prepared source step does not match the canonical request",
        )
    if expected_operation is GenerationOperation.GENERATE:
        if (
            canonical.target_ref is not None
            or technical.target_ref is not None
            or technical.target_version_ref is not None
        ):
            _raise_mismatch(
                GenerationCoordinationErrorCode.TARGET_FORBIDDEN_FOR_GENERATE,
                "CAP-G01 forbids a target reference",
            )
    elif (
        canonical.target_ref is None
        or technical.target_ref is None
        or technical.target_version_ref is not None
    ):
        _raise_mismatch(
            GenerationCoordinationErrorCode.TARGET_REQUIRED_FOR_TRANSFORM,
            "CAP-G02 requires only a contract target reference",
        )

    exact_pairs = (
        (technical.production_kind, canonical.production_kind, "production_kind"),
        (technical.objective, canonical.brief, "objective"),
        (technical.output_format, canonical.output_format, "output_format"),
        (
            technical.pedagogical_context,
            canonical.pedagogical_context,
            "pedagogical_context",
        ),
        (technical.constraints, canonical.constraints, "constraints"),
        (technical.evidence_refs, canonical.evidence_refs, "evidence_refs"),
        (technical.target_ref, canonical.target_ref, "target_ref"),
        (
            technical.expected_sections,
            canonical.expected_sections,
            "expected_sections",
        ),
        (
            technical.resolved_inputs,
            snapshot.resolved_inputs,
            "resolved_inputs",
        ),
        (
            technical.output_contract,
            snapshot.output_contract,
            "output_contract",
        ),
    )
    for actual, expected, field_name in exact_pairs:
        if actual != expected:
            _raise_mismatch(
                GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH,
                f"prepared {field_name} does not match the canonical request",
            )


def _validate_labeled_evidence(
    values: tuple[LabeledEvidenceItem, ...],
    evidence_refs: tuple[object, ...],
) -> None:
    if type(values) is not tuple or any(
        type(value) is not LabeledEvidenceItem for value in values
    ):
        raise TypeError("labeled_evidence must contain LabeledEvidenceItem values")
    content_refs = tuple(value.content.content_ref for value in values)
    if len(content_refs) != len(set(content_refs)):
        raise ValueError("labeled_evidence content references must be unique")
    if not set(content_refs).issubset(evidence_refs):
        raise ValueError("labeled_evidence must remain inside canonical evidence scope")


def _validate_labeled_inputs(
    values: tuple[LabeledContent, ...],
    assessments: tuple[StructuredContentSecurityAssessment, ...],
) -> None:
    if type(values) is not tuple or any(
        type(value) is not LabeledContent for value in values
    ):
        raise TypeError("labeled_inputs must contain LabeledContent values")
    refs = tuple(value.content_ref for value in values)
    if len(refs) != len(set(refs)):
        raise ValueError("labeled_inputs content references must be unique")
    if any(
        value.label.origin
        not in {ContentOrigin.TOOL_OUTPUT, ContentOrigin.APPLICATION_OUTPUT}
        or value.label.role is not ContentRole.RESULT
        or value.label.trust_class is not ContentTrustClass.UNTRUSTED
        for value in values
    ):
        raise ValueError("labeled_inputs must preserve untrusted boundary provenance")
    if type(assessments) is not tuple or any(
        type(item) is not StructuredContentSecurityAssessment for item in assessments
    ):
        raise TypeError(
            "input_security_assessments must contain structured assessments"
        )
    if any(
        item.label.origin
        not in {ContentOrigin.TOOL_OUTPUT, ContentOrigin.APPLICATION_OUTPUT}
        or item.label.trust_class is not ContentTrustClass.UNTRUSTED
        or item.boundary
        is not (
            SecurityBoundary.TOOL
            if item.label.origin is ContentOrigin.TOOL_OUTPUT
            else SecurityBoundary.APPLICATION
        )
        for item in assessments
    ):
        raise ValueError("input assessments must preserve boundary provenance")
    assessed_refs = {
        nested.content_ref
        for assessment in assessments
        for nested in assessment.content_assessments
    }
    if assessed_refs != set(refs):
        raise ValueError("input assessments must exactly cover labeled_inputs")


def _raise_mismatch(
    code: GenerationCoordinationErrorCode,
    safe_reason: str,
) -> None:
    raise GenerationCoordinationError(code, safe_reason)
