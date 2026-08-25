from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import NoReturn

from backend.agent_runtime.agents.generation.generation_agent_model import (
    GenerationCandidateMaterializationError,
    _validate_authority_free_generation_metadata,
)
from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationCoordinationError,
    GenerationCoordinationErrorCode,
)
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationOperation,
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
)
from backend.agent_runtime.contracts import (
    ActorKind,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    CorrectionRequest,
)
from backend.agent_runtime.contracts.common import freeze_agent_safe_mapping
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef


class CorrectionMaterializationCode(StrEnum):
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    TARGET_LINEAGE_MISMATCH = "TARGET_LINEAGE_MISMATCH"
    PREPARED_LINEAGE_MISMATCH = "PREPARED_LINEAGE_MISMATCH"
    TECHNICAL_RESULT_MISMATCH = "TECHNICAL_RESULT_MISMATCH"
    CORRECTION_DETAILS_MISMATCH = "CORRECTION_DETAILS_MISMATCH"
    RESULT_META_MISMATCH = "RESULT_META_MISMATCH"
    NO_CORRECTION_FOR_STATUS = "NO_CORRECTION_FOR_STATUS"


class CorrectionMaterializationError(ValueError):
    code: CorrectionMaterializationCode
    safe_reason: str

    def __init__(
        self,
        code: CorrectionMaterializationCode,
        safe_reason: str,
    ) -> None:
        if type(code) is not CorrectionMaterializationCode:
            raise TypeError("code must be a CorrectionMaterializationCode")
        require_non_empty(safe_reason, "safe_reason")
        self.code = code
        self.safe_reason = safe_reason
        super().__init__(safe_reason)


@dataclass(frozen=True, slots=True)
class ResolvedCorrectionTarget:
    target_production_ref: ObjectVersionRef
    production_kind: str
    output_format: str
    pedagogical_context: Mapping[str, object] = field(default_factory=dict)
    content: str | None = None
    structured_payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.target_production_ref) is not ObjectVersionRef:
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        require_non_empty(self.production_kind, "production_kind")
        require_non_empty(self.output_format, "output_format")
        if self.content is not None:
            require_non_empty(self.content, "content")
        context = freeze_agent_safe_mapping(self.pedagogical_context)
        payload = freeze_agent_safe_mapping(self.structured_payload)
        if self.content is None and not payload:
            raise ValueError("content or structured_payload is required")
        object.__setattr__(self, "pedagogical_context", context)
        object.__setattr__(self, "structured_payload", payload)


@dataclass(frozen=True, slots=True)
class CorrectionPreparationRequest:
    capability_id: CapabilityId
    request: CorrectionRequest
    target: ResolvedCorrectionTarget
    resolved_inputs: Mapping[str, object] = field(default_factory=dict)
    output_contract: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.capability_id) is not CapabilityId:
            raise TypeError("capability_id must be a CapabilityId")
        if self.capability_id.value != "CAP-G03":
            _raise_correction(
                CorrectionMaterializationCode.UNSUPPORTED_CAPABILITY,
                "correction preparation supports only CAP-G03",
            )
        if type(self.request) is not CorrectionRequest:
            raise TypeError("request must be a CorrectionRequest")
        if type(self.target) is not ResolvedCorrectionTarget:
            raise TypeError("target must be a ResolvedCorrectionTarget")
        if self.target.target_production_ref != self.request.target_production_ref:
            _raise_correction(
                CorrectionMaterializationCode.TARGET_LINEAGE_MISMATCH,
                "resolved correction target does not match the correction request",
            )
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
class PreparedCorrectionCall:
    preparation_request: CorrectionPreparationRequest
    capability_id: CapabilityId
    correction_request: CorrectionRequest
    target: ResolvedCorrectionTarget
    port_request: GenerationPortRequest

    def __post_init__(self) -> None:
        _validate_prepared_correction_call(self)


@dataclass(frozen=True, slots=True)
class CorrectionMaterializationRequest:
    correction_request: CorrectionRequest
    target: ResolvedCorrectionTarget
    prepared: PreparedCorrectionCall
    technical_result: GenerationPortResult
    result_meta: ContractMeta[AgentResultStatus]
    production_id: str
    new_production_ref: ObjectVersionRef

    def __post_init__(self) -> None:
        _validate_correction_materialization_request(self)


def _validate_prepared_correction_call(prepared: PreparedCorrectionCall) -> None:
    if type(prepared.preparation_request) is not CorrectionPreparationRequest:
        raise TypeError("preparation_request must be a CorrectionPreparationRequest")
    if type(prepared.capability_id) is not CapabilityId:
        raise TypeError("capability_id must be a CapabilityId")
    if prepared.capability_id.value != "CAP-G03":
        _raise_correction(
            CorrectionMaterializationCode.UNSUPPORTED_CAPABILITY,
            "prepared correction supports only CAP-G03",
        )
    if type(prepared.correction_request) is not CorrectionRequest:
        raise TypeError("correction_request must be a CorrectionRequest")
    if type(prepared.target) is not ResolvedCorrectionTarget:
        raise TypeError("target must be a ResolvedCorrectionTarget")
    if type(prepared.port_request) is not GenerationPortRequest:
        raise TypeError("port_request must be a GenerationPortRequest")
    correction = prepared.correction_request
    target = prepared.target
    technical = prepared.port_request
    snapshot = prepared.preparation_request
    if (
        snapshot.capability_id != prepared.capability_id
        or snapshot.request != correction
        or snapshot.target != target
    ):
        _raise_correction(
            CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH,
            "prepared correction fields do not match the preparation snapshot",
        )
    if target.target_production_ref != correction.target_production_ref:
        _raise_correction(
            CorrectionMaterializationCode.TARGET_LINEAGE_MISMATCH,
            "prepared target does not match the correction request",
        )
    expected_constraints: Mapping[str, object] = {
        "review_ref": correction.review_ref,
        "finding_ids": correction.finding_ids,
        "preserve_constraints": correction.preserve_constraints,
        "allowed_changes": correction.allowed_changes,
        "forbidden_changes": correction.forbidden_changes,
        "expected_delta": correction.expected_delta,
    }
    expected_input_keys = {
        "target_content",
        "target_structured_payload",
        "caller_resolved_inputs",
    }
    exact_pairs = (
        (technical.operation, GenerationOperation.CORRECT),
        (technical.source_step_id, correction.meta.step_id),
        (technical.production_kind, target.production_kind),
        (technical.objective, "apply_bounded_correction_request"),
        (technical.output_format, target.output_format),
        (technical.pedagogical_context, target.pedagogical_context),
        (technical.constraints, expected_constraints),
        (technical.evidence_refs, correction.evidence_refs),
        (technical.target_ref, None),
        (technical.target_version_ref, correction.target_production_ref),
        (technical.expected_sections, ()),
    )
    if any(actual != expected for actual, expected in exact_pairs):
        _raise_correction(
            CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH,
            "prepared correction call does not match its canonical inputs",
        )
    if set(technical.resolved_inputs) != expected_input_keys:
        _raise_correction(
            CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH,
            "prepared correction inputs do not have the exact closed shape",
        )
    if (
        technical.resolved_inputs["target_content"] != target.content
        or technical.resolved_inputs["target_structured_payload"]
        != target.structured_payload
        or technical.resolved_inputs["caller_resolved_inputs"]
        != snapshot.resolved_inputs
        or technical.output_contract != snapshot.output_contract
    ):
        _raise_correction(
            CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH,
            "prepared correction inputs do not match the preparation snapshot",
        )


def _validate_correction_technical_result(
    prepared: PreparedCorrectionCall,
    result: GenerationPortResult,
) -> None:
    if type(result) is not GenerationPortResult:
        raise GenerationPortError(
            GenerationPortErrorCode.INVALID_RESPONSE,
            "generation port returned an invalid correction result",
        )
    if result.source_step_id != prepared.port_request.source_step_id:
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.SOURCE_STEP_MISMATCH,
            "correction result source step does not match the prepared request",
        )
    if result.operation is not GenerationOperation.CORRECT:
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.OPERATION_MISMATCH,
            "correction result operation must be CORRECT",
        )
    if len(result.evidence_refs_used) != len(set(result.evidence_refs_used)):
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.DUPLICATE_EVIDENCE_REF_USED,
            "correction result contains duplicate evidence references",
        )
    if not set(result.evidence_refs_used).issubset(
        prepared.correction_request.evidence_refs
    ):
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE,
            "correction result contains an evidence reference outside the request",
        )


def _validated_correction_details(
    correction_request: CorrectionRequest,
    technical_result: GenerationPortResult,
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    details = technical_result.operation_details
    if set(details) != {
        "addressed_findings",
        "unresolved_findings",
        "change_summary",
    }:
        _raise_correction(
            CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
            "correction operation details must have the exact closed shape",
        )
    addressed = _validated_declared_findings(
        details["addressed_findings"],
        "addressed_findings",
    )
    unresolved = _validated_declared_findings(
        details["unresolved_findings"],
        "unresolved_findings",
    )
    if set(addressed).intersection(unresolved):
        _raise_correction(
            CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
            "addressed and unresolved correction findings must be disjoint",
        )
    if set(addressed).union(unresolved) != set(correction_request.finding_ids):
        _raise_correction(
            CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
            "correction findings must exactly cover the correction request",
        )
    change_summary = details["change_summary"]
    if not isinstance(change_summary, str):
        _raise_correction(
            CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
            "correction change summary must be a non-empty string",
        )
    try:
        require_non_empty(change_summary, "change_summary")
    except ValueError as error:
        raise CorrectionMaterializationError(
            CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
            "correction change summary must be a non-empty string",
        ) from error
    return addressed, unresolved, change_summary


def _validate_correction_materialization_request(
    request: CorrectionMaterializationRequest,
) -> None:
    if type(request.correction_request) is not CorrectionRequest:
        raise TypeError("correction_request must be a CorrectionRequest")
    if type(request.target) is not ResolvedCorrectionTarget:
        raise TypeError("target must be a ResolvedCorrectionTarget")
    if type(request.prepared) is not PreparedCorrectionCall:
        raise TypeError("prepared must be a PreparedCorrectionCall")
    if type(request.technical_result) is not GenerationPortResult:
        raise TypeError("technical_result must be a GenerationPortResult")
    if type(request.result_meta) is not ContractMeta:
        raise TypeError("result_meta must be a ContractMeta")
    if not isinstance(request.result_meta.status, AgentResultStatus):
        raise TypeError("result_meta.status must be an AgentResultStatus")
    require_non_empty(request.production_id, "production_id")
    if type(request.new_production_ref) is not ObjectVersionRef:
        raise TypeError("new_production_ref must be an ObjectVersionRef")
    if request.prepared.correction_request != request.correction_request:
        _raise_correction(
            CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH,
            "prepared correction request does not match materialization",
        )
    if request.prepared.target != request.target:
        _raise_correction(
            CorrectionMaterializationCode.TARGET_LINEAGE_MISMATCH,
            "prepared correction target does not match materialization",
        )
    _validate_prepared_correction_call(request.prepared)
    try:
        _validate_correction_technical_result(
            request.prepared,
            request.technical_result,
        )
    except (GenerationCoordinationError, GenerationPortError) as error:
        raise CorrectionMaterializationError(
            CorrectionMaterializationCode.TECHNICAL_RESULT_MISMATCH,
            "technical correction result does not match the prepared call",
        ) from error
    status = request.technical_result.status
    if status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        _raise_correction(
            CorrectionMaterializationCode.NO_CORRECTION_FOR_STATUS,
            "technical result status does not permit correction materialization",
        )
    try:
        _validate_authority_free_generation_metadata(
            request.technical_result.execution_metadata
        )
    except GenerationCandidateMaterializationError as error:
        raise CorrectionMaterializationError(
            CorrectionMaterializationCode.TECHNICAL_RESULT_MISMATCH,
            "technical correction metadata contains forbidden authority vocabulary",
        ) from error
    _validated_correction_details(
        request.correction_request,
        request.technical_result,
    )
    meta = request.result_meta
    canonical_meta = request.correction_request.meta
    if (
        meta.run_id != canonical_meta.run_id
        or meta.step_id != canonical_meta.step_id
        or meta.correlation_id != canonical_meta.correlation_id
        or meta.actor.kind is not ActorKind.AGENT
        or meta.actor.actor_id != AgentId.AG_03.value
    ):
        _raise_correction(
            CorrectionMaterializationCode.RESULT_META_MISMATCH,
            "correction result metadata does not match C-11 and AG-03",
        )
    expected_status = (
        AgentResultStatus.SUCCEEDED
        if status is GenerationPortResultStatus.SUCCEEDED
        else AgentResultStatus.PARTIAL
    )
    if meta.status is not expected_status:
        _raise_correction(
            CorrectionMaterializationCode.RESULT_META_MISMATCH,
            "correction result status does not match the technical result",
        )


def _validated_declared_findings(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        _raise_correction(
            CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
            f"{field_name} must be a tuple of unique non-empty identifiers",
        )
    for item in value:
        if not isinstance(item, str):
            _raise_correction(
                CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
                f"{field_name} must contain only non-empty strings",
            )
        try:
            require_non_empty(item, field_name)
        except ValueError as error:
            raise CorrectionMaterializationError(
                CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
                f"{field_name} must contain only non-empty strings",
            ) from error
    if len(value) != len(set(value)):
        _raise_correction(
            CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH,
            f"{field_name} must contain unique identifiers",
        )
    return value


def _raise_correction(
    code: CorrectionMaterializationCode,
    safe_reason: str,
) -> NoReturn:
    raise CorrectionMaterializationError(code, safe_reason)
