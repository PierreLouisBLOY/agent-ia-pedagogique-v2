from __future__ import annotations

from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationCoordinationError,
    GenerationCoordinationErrorCode,
    GenerationPreparationRequest,
    PreparedGenerationCall,
    _operation_for_capability,
    _validate_prepared_call,
)
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationOperation,
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
    GenerationPortResult,
)
from backend.agent_runtime.agents.generation.generation_ports import GenerationPort


class GenerationCoordinator:
    __slots__ = ("_port",)

    def __init__(self, port: GenerationPort) -> None:
        if not isinstance(port, GenerationPort):
            raise TypeError("port must implement GenerationPort")
        self._port = port

    def prepare(
        self,
        *,
        request: GenerationPreparationRequest,
    ) -> PreparedGenerationCall:
        if type(request) is not GenerationPreparationRequest:
            raise TypeError("request must be a GenerationPreparationRequest")
        canonical = request.request
        operation = _operation_for_capability(request.capability_id)
        if operation is GenerationOperation.CORRECT:
            raise GenerationCoordinationError(
                GenerationCoordinationErrorCode.CORRECTION_REQUEST_REQUIRED,
                "CAP-G03 requires a CorrectionRequest",
            )
        if operation is GenerationOperation.GENERATE and canonical.target_ref is not None:
            raise GenerationCoordinationError(
                GenerationCoordinationErrorCode.TARGET_FORBIDDEN_FOR_GENERATE,
                "CAP-G01 forbids a target reference",
            )
        if operation is GenerationOperation.TRANSFORM and canonical.target_ref is None:
            raise GenerationCoordinationError(
                GenerationCoordinationErrorCode.TARGET_REQUIRED_FOR_TRANSFORM,
                "CAP-G02 requires a target reference",
            )
        port_request = GenerationPortRequest(
            operation=operation,
            source_step_id=canonical.meta.step_id,
            production_kind=canonical.production_kind,
            objective=canonical.brief,
            output_format=canonical.output_format,
            pedagogical_context=canonical.pedagogical_context,
            resolved_inputs=request.resolved_inputs,
            constraints=canonical.constraints,
            evidence_refs=canonical.evidence_refs,
            target_ref=canonical.target_ref,
            expected_sections=canonical.expected_sections,
            output_contract=request.output_contract,
        )
        return PreparedGenerationCall(
            capability_id=request.capability_id,
            canonical_request=canonical,
            port_request=port_request,
        )

    def execute(
        self,
        *,
        prepared: PreparedGenerationCall,
    ) -> GenerationPortResult:
        if type(prepared) is not PreparedGenerationCall:
            raise TypeError("prepared must be a PreparedGenerationCall")
        _validate_prepared_call(prepared)
        result = self._port.generate(request=prepared.port_request)
        _validate_generation_result(prepared, result)
        return result


def _validate_generation_result(
    prepared: PreparedGenerationCall,
    result: GenerationPortResult,
) -> None:
    if type(result) is not GenerationPortResult:
        raise GenerationPortError(
            GenerationPortErrorCode.INVALID_RESPONSE,
            "generation port returned an invalid technical result",
        )
    if result.source_step_id != prepared.port_request.source_step_id:
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.SOURCE_STEP_MISMATCH,
            "result source step does not match the prepared request",
        )
    if result.operation is not prepared.port_request.operation:
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.OPERATION_MISMATCH,
            "result operation does not match the prepared request",
        )
    if len(result.evidence_refs_used) != len(set(result.evidence_refs_used)):
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.DUPLICATE_EVIDENCE_REF_USED,
            "result contains duplicate evidence references",
        )
    if not set(result.evidence_refs_used).issubset(
        prepared.canonical_request.evidence_refs
    ):
        raise GenerationCoordinationError(
            GenerationCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE,
            "result contains an evidence reference outside the canonical request",
        )
