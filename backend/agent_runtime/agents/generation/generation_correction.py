from __future__ import annotations

from backend.agent_runtime.agents.generation.generation_correction_model import (
    CorrectionMaterializationRequest,
    _validate_correction_materialization_request,
    _validated_correction_details,
)
from backend.agent_runtime.contracts import CorrectionResult, ProductionCandidate
from backend.shared_kernel.references import ObjectVersionRef


def materialize_correction(
    *,
    request: CorrectionMaterializationRequest,
) -> tuple[ProductionCandidate, CorrectionResult]:
    if type(request) is not CorrectionMaterializationRequest:
        raise TypeError("request must be a CorrectionMaterializationRequest")
    _validate_correction_materialization_request(request)
    from backend.agent_runtime.agents.generation.generation_guard import (
        generation_guard_security_warnings,
    )

    correction = request.correction_request
    technical = request.technical_result
    guard_warnings = generation_guard_security_warnings(request.guard_assessment)
    addressed, unresolved, change_summary = _validated_correction_details(
        correction,
        technical,
    )
    parent_ref = _public_object_version_ref(correction.target_production_ref)
    new_ref = _public_object_version_ref(request.new_production_ref)
    generation_metadata = dict(technical.execution_metadata)
    generation_metadata["technical_status"] = technical.status.value
    generation_metadata["operation"] = technical.operation.value
    candidate = ProductionCandidate(
        meta=request.result_meta,
        production_id=request.production_id,
        production_kind=request.target.production_kind,
        content=technical.content,
        structured_payload=technical.structured_payload,
        lineage={
            "source_run_id": correction.meta.run_id,
            "source_step_id": correction.meta.step_id,
            "source_correlation_id": correction.meta.correlation_id.value,
            "capability_id": "CAP-G03",
            "generation_operation": "CORRECT",
            "review_ref": correction.review_ref,
            "finding_ids": correction.finding_ids,
            "correction_target": parent_ref,
        },
        evidence_refs_used=technical.evidence_refs_used,
        warnings=technical.warnings + guard_warnings,
        uncertainties=technical.uncertainties,
        generation_metadata=generation_metadata,
    )
    result = CorrectionResult(
        meta=request.result_meta,
        request=correction,
        new_production_ref=request.new_production_ref,
        parent_production_ref=correction.target_production_ref,
        addressed_findings=addressed,
        unresolved_findings=unresolved,
        change_summary=change_summary,
        lineage={
            "production_candidate_id": request.production_id,
            "capability_id": "CAP-G03",
            "generation_operation": "CORRECT",
            "review_ref": correction.review_ref,
            "parent": parent_ref,
            "new_version": new_ref,
        },
        new_warnings=technical.warnings + guard_warnings,
    )
    return candidate, result


def _public_object_version_ref(reference: ObjectVersionRef) -> dict[str, str]:
    entity_id = reference.object_ref.entity_id
    return {
        "entity_type": entity_id.entity_type,
        "entity_id": entity_id.value,
        "version": reference.version_ref.value,
    }
