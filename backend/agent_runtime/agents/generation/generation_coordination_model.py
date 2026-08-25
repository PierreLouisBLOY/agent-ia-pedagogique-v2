from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.agents.generation.generation_model import (
    GenerationOperation,
    GenerationPortRequest,
)
from backend.agent_runtime.contracts import ProductionRequest
from backend.agent_runtime.contracts.common import freeze_agent_safe_mapping
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


@dataclass(frozen=True, slots=True)
class PreparedGenerationCall:
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
    canonical = prepared.canonical_request
    technical = prepared.port_request
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
        if canonical.target_ref is not None or technical.target_ref is not None:
            _raise_mismatch(
                GenerationCoordinationErrorCode.TARGET_FORBIDDEN_FOR_GENERATE,
                "CAP-G01 forbids a target reference",
            )
    elif canonical.target_ref is None or technical.target_ref is None:
        _raise_mismatch(
            GenerationCoordinationErrorCode.TARGET_REQUIRED_FOR_TRANSFORM,
            "CAP-G02 requires a target reference",
        )

    exact_pairs = (
        (technical.production_kind, canonical.production_kind, "production_kind"),
        (technical.objective, canonical.brief, "objective"),
        (technical.output_format, canonical.output_format, "output_format"),
        (technical.constraints, canonical.constraints, "constraints"),
        (technical.evidence_refs, canonical.evidence_refs, "evidence_refs"),
        (technical.target_ref, canonical.target_ref, "target_ref"),
        (
            technical.expected_sections,
            canonical.expected_sections,
            "expected_sections",
        ),
    )
    for actual, expected, field_name in exact_pairs:
        if actual != expected:
            _raise_mismatch(
                GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH,
                f"prepared {field_name} does not match the canonical request",
            )


def _raise_mismatch(
    code: GenerationCoordinationErrorCode,
    safe_reason: str,
) -> None:
    raise GenerationCoordinationError(code, safe_reason)
