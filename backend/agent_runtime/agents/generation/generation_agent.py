from __future__ import annotations

from backend.agent_runtime.agents.generation.generation_agent_model import (
    GenerationCandidateMaterializationCode,
    GenerationCandidateMaterializationError,
    ProductionCandidateBuildRequest,
    _validate_candidate_build_request,
)
from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationPreparationRequest,
    PreparedGenerationCall,
)
from backend.agent_runtime.agents.generation.generation_coordinator import (
    GenerationCoordinator,
)
from backend.agent_runtime.agents.generation.generation_correction import (
    materialize_correction,
)
from backend.agent_runtime.agents.generation.generation_correction_model import (
    CorrectionMaterializationCode,
    CorrectionMaterializationError,
    CorrectionMaterializationRequest,
    CorrectionPreparationRequest,
    PreparedCorrectionCall,
)
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationPortResult,
)
from backend.agent_runtime.contracts import CorrectionResult, ProductionCandidate


class GeneratorAgent:
    __slots__ = ("_coordinator",)

    def __init__(self, coordinator: GenerationCoordinator) -> None:
        if not isinstance(coordinator, GenerationCoordinator):
            raise TypeError("coordinator must be a GenerationCoordinator")
        self._coordinator = coordinator

    def generate_production(
        self,
        *,
        request: GenerationPreparationRequest,
    ) -> tuple[PreparedGenerationCall, GenerationPortResult]:
        self._require_capability(request, "CAP-G01")
        prepared = self._coordinator.prepare(request=request)
        result = self._coordinator.execute(prepared=prepared)
        return prepared, result

    def transform_production(
        self,
        *,
        request: GenerationPreparationRequest,
    ) -> tuple[PreparedGenerationCall, GenerationPortResult]:
        self._require_capability(request, "CAP-G02")
        prepared = self._coordinator.prepare(request=request)
        result = self._coordinator.execute(prepared=prepared)
        return prepared, result

    def build_candidate(
        self,
        *,
        request: ProductionCandidateBuildRequest,
    ) -> ProductionCandidate:
        if type(request) is not ProductionCandidateBuildRequest:
            raise TypeError("request must be a ProductionCandidateBuildRequest")
        _validate_candidate_build_request(request)
        canonical = request.canonical_request
        technical = request.technical_result
        lineage: dict[str, object] = {
            "source_run_id": canonical.meta.run_id,
            "source_step_id": canonical.meta.step_id,
            "source_correlation_id": canonical.meta.correlation_id.value,
            "source_request_schema_version": str(canonical.meta.schema_version),
            "capability_id": request.prepared.capability_id.value,
            "generation_operation": technical.operation.value,
        }
        if request.prepared.capability_id.value == "CAP-G02":
            lineage["target_ref"] = canonical.target_ref
        generation_metadata = dict(technical.execution_metadata)
        generation_metadata["technical_status"] = technical.status.value
        generation_metadata["operation"] = technical.operation.value
        return ProductionCandidate(
            meta=request.result_meta,
            production_id=request.production_id,
            production_kind=canonical.production_kind,
            content=technical.content,
            structured_payload=technical.structured_payload,
            lineage=lineage,
            evidence_refs_used=technical.evidence_refs_used,
            warnings=technical.warnings,
            uncertainties=technical.uncertainties,
            generation_metadata=generation_metadata,
        )

    def correct_production(
        self,
        *,
        request: CorrectionPreparationRequest,
    ) -> tuple[PreparedCorrectionCall, GenerationPortResult]:
        if type(request) is not CorrectionPreparationRequest:
            raise TypeError("request must be a CorrectionPreparationRequest")
        if request.capability_id.value != "CAP-G03":
            raise CorrectionMaterializationError(
                CorrectionMaterializationCode.UNSUPPORTED_CAPABILITY,
                "operation requires CAP-G03",
            )
        prepared = self._coordinator.prepare_correction(request=request)
        result = self._coordinator.execute_correction(prepared=prepared)
        return prepared, result

    def build_correction(
        self,
        *,
        request: CorrectionMaterializationRequest,
    ) -> tuple[ProductionCandidate, CorrectionResult]:
        return materialize_correction(request=request)

    @staticmethod
    def _require_capability(
        request: GenerationPreparationRequest,
        expected_capability: str,
    ) -> None:
        if type(request) is not GenerationPreparationRequest:
            raise TypeError("request must be a GenerationPreparationRequest")
        if request.capability_id.value != expected_capability:
            raise GenerationCandidateMaterializationError(
                GenerationCandidateMaterializationCode.UNSUPPORTED_CAPABILITY,
                f"operation requires {expected_capability}",
            )
