from __future__ import annotations

from backend.agent_runtime.agents.review.review_coordination_model import (
    PreparedReviewCall,
    ReviewCoordinationError,
    ReviewCoordinationErrorCode,
    ReviewPreparationRequest,
    _coverage_context_for,
    _operation_for_capability,
    _validate_prepared_review_call,
)
from backend.agent_runtime.agents.review.review_model import (
    ReviewPortError,
    ReviewPortErrorCode,
    ReviewPortRequest,
    ReviewPortResult,
)
from backend.agent_runtime.agents.review.review_ports import ReviewPort


class ReviewCoordinator:
    __slots__ = ("_port",)

    def __init__(self, port: ReviewPort) -> None:
        if not isinstance(port, ReviewPort):
            raise TypeError("port must implement ReviewPort")
        self._port = port

    def prepare(self, *, request: ReviewPreparationRequest) -> PreparedReviewCall:
        if type(request) is not ReviewPreparationRequest:
            raise TypeError("request must be a ReviewPreparationRequest")
        canonical = request.request
        target = request.target
        operation = _operation_for_capability(request.capability_id)
        if target.target_production_ref != canonical.target_production_ref:
            raise ReviewCoordinationError(ReviewCoordinationErrorCode.TARGET_REF_MISMATCH)
        if len(canonical.evidence_refs) != len(set(canonical.evidence_refs)):
            raise ReviewCoordinationError(ReviewCoordinationErrorCode.PREPARATION_MISMATCH)
        port_request = ReviewPortRequest(
            source_step_id=canonical.meta.step_id,
            operation=operation,
            capability_id=request.capability_id,
            target_production_ref=canonical.target_production_ref,
            target_content=target.content,
            target_payload=target.structured_payload,
            review_dimensions=canonical.review_dimensions,
            criteria=canonical.criteria,
            evidence_refs=canonical.evidence_refs,
            coverage_context=_coverage_context_for(canonical),
            resolved_inputs=request.resolved_inputs,
            output_contract=request.output_contract,
            review_budget=canonical.review_budget,
        )
        return PreparedReviewCall(
            preparation_request=request,
            capability_id=request.capability_id,
            canonical_request=canonical,
            target=target,
            port_request=port_request,
        )

    def execute(self, *, prepared: PreparedReviewCall) -> ReviewPortResult:
        if type(prepared) is not PreparedReviewCall:
            raise TypeError("prepared must be a PreparedReviewCall")
        _validate_prepared_review_call(prepared)
        result = self._port.review(request=prepared.port_request)
        _validate_review_result(prepared, result)
        return result


def _validate_review_result(
    prepared: PreparedReviewCall,
    result: ReviewPortResult,
) -> None:
    if type(result) is not ReviewPortResult:
        raise ReviewPortError(ReviewPortErrorCode.INVALID_RESPONSE)
    if result.source_step_id != prepared.port_request.source_step_id:
        raise ReviewCoordinationError(ReviewCoordinationErrorCode.SOURCE_STEP_MISMATCH)
    if result.operation is not prepared.port_request.operation:
        raise ReviewCoordinationError(ReviewCoordinationErrorCode.OPERATION_MISMATCH)
    if len(result.evidence_refs_used) != len(set(result.evidence_refs_used)):
        raise ReviewCoordinationError(ReviewCoordinationErrorCode.DUPLICATE_EVIDENCE_REF_USED)
    if not set(result.evidence_refs_used).issubset(prepared.canonical_request.evidence_refs):
        raise ReviewCoordinationError(ReviewCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE)
