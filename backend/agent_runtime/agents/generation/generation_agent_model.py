from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationCoordinationError,
    PreparedGenerationCall,
    _validate_prepared_call,
)
from backend.agent_runtime.agents.generation.generation_coordinator import (
    _validate_generation_result,
)
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationPortError,
    GenerationPortResult,
    GenerationPortResultStatus,
)
from backend.agent_runtime.contracts import (
    ActorKind,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    ProductionRequest,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty

_FORBIDDEN_GENERATION_METADATA_AUTHORITY_KEYS = frozenset(
    {
        "approved",
        "canonical",
        "gate_decision",
        "permission_scope",
        "promoted",
        "quality_score",
        "reviewed",
        "safe",
        "trusted",
        "validated",
        "validation_state",
    }
)


class GenerationCandidateMaterializationCode(StrEnum):
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    PREPARED_LINEAGE_MISMATCH = "PREPARED_LINEAGE_MISMATCH"
    TECHNICAL_RESULT_MISMATCH = "TECHNICAL_RESULT_MISMATCH"
    RESULT_META_MISMATCH = "RESULT_META_MISMATCH"
    NO_CANDIDATE_FOR_STATUS = "NO_CANDIDATE_FOR_STATUS"


class GenerationCandidateMaterializationError(ValueError):
    code: GenerationCandidateMaterializationCode
    safe_reason: str

    def __init__(
        self,
        code: GenerationCandidateMaterializationCode,
        safe_reason: str,
    ) -> None:
        if type(code) is not GenerationCandidateMaterializationCode:
            raise TypeError("code must be a GenerationCandidateMaterializationCode")
        require_non_empty(safe_reason, "safe_reason")
        self.code = code
        self.safe_reason = safe_reason
        super().__init__(safe_reason)


@dataclass(frozen=True, slots=True)
class ProductionCandidateBuildRequest:
    canonical_request: ProductionRequest
    prepared: PreparedGenerationCall
    technical_result: GenerationPortResult
    result_meta: ContractMeta[AgentResultStatus]
    production_id: str

    def __post_init__(self) -> None:
        _validate_candidate_build_request(self)


def _validate_candidate_build_request(
    request: ProductionCandidateBuildRequest,
) -> None:
    if type(request.canonical_request) is not ProductionRequest:
        raise TypeError("canonical_request must be a ProductionRequest")
    if type(request.prepared) is not PreparedGenerationCall:
        raise TypeError("prepared must be a PreparedGenerationCall")
    if type(request.technical_result) is not GenerationPortResult:
        raise TypeError("technical_result must be a GenerationPortResult")
    if type(request.result_meta) is not ContractMeta:
        raise TypeError("result_meta must be a ContractMeta")
    if not isinstance(request.result_meta.status, AgentResultStatus):
        raise TypeError("result_meta.status must be an AgentResultStatus")
    require_non_empty(request.production_id, "production_id")

    capability = request.prepared.capability_id
    if type(capability) is not CapabilityId or capability.value not in {
        "CAP-G01",
        "CAP-G02",
    }:
        _raise_materialization(
            GenerationCandidateMaterializationCode.UNSUPPORTED_CAPABILITY,
            "candidate materialization supports only CAP-G01 and CAP-G02",
        )
    if request.prepared.canonical_request != request.canonical_request:
        _raise_materialization(
            GenerationCandidateMaterializationCode.PREPARED_LINEAGE_MISMATCH,
            "prepared canonical request does not match the build request",
        )
    try:
        _validate_prepared_call(request.prepared)
    except GenerationCoordinationError as error:
        raise GenerationCandidateMaterializationError(
            GenerationCandidateMaterializationCode.PREPARED_LINEAGE_MISMATCH,
            "prepared generation lineage is invalid",
        ) from error
    try:
        _validate_generation_result(request.prepared, request.technical_result)
    except (GenerationCoordinationError, GenerationPortError) as error:
        raise GenerationCandidateMaterializationError(
            GenerationCandidateMaterializationCode.TECHNICAL_RESULT_MISMATCH,
            "technical generation result does not match the prepared call",
        ) from error
    _validate_authority_free_generation_metadata(
        request.technical_result.execution_metadata
    )

    meta = request.result_meta
    canonical_meta = request.canonical_request.meta
    if (
        meta.run_id != canonical_meta.run_id
        or meta.step_id != canonical_meta.step_id
        or meta.correlation_id != canonical_meta.correlation_id
        or meta.actor.kind is not ActorKind.AGENT
        or meta.actor.actor_id != AgentId.AG_03.value
    ):
        _raise_materialization(
            GenerationCandidateMaterializationCode.RESULT_META_MISMATCH,
            "candidate result metadata does not match the canonical request and AG-03",
        )

    technical_status = request.technical_result.status
    if technical_status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        _raise_materialization(
            GenerationCandidateMaterializationCode.NO_CANDIDATE_FOR_STATUS,
            "technical result status does not permit candidate materialization",
        )
    expected_meta_status = (
        AgentResultStatus.SUCCEEDED
        if technical_status is GenerationPortResultStatus.SUCCEEDED
        else AgentResultStatus.PARTIAL
    )
    if meta.status is not expected_meta_status:
        _raise_materialization(
            GenerationCandidateMaterializationCode.RESULT_META_MISMATCH,
            "candidate result status does not match the technical result status",
        )


def _raise_materialization(
    code: GenerationCandidateMaterializationCode,
    safe_reason: str,
) -> None:
    raise GenerationCandidateMaterializationError(code, safe_reason)


def _validate_authority_free_generation_metadata(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if (
                isinstance(key, str)
                and key.casefold() in _FORBIDDEN_GENERATION_METADATA_AUTHORITY_KEYS
            ):
                _raise_materialization(
                    GenerationCandidateMaterializationCode.TECHNICAL_RESULT_MISMATCH,
                    "technical execution metadata contains forbidden authority vocabulary",
                )
            _validate_authority_free_generation_metadata(nested_value)
    elif isinstance(value, (list, tuple)):
        for nested_value in value:
            _validate_authority_free_generation_metadata(nested_value)
