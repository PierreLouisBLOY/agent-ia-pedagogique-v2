from __future__ import annotations

from backend.agent_runtime.agents.review.review_agent_model import (
    ReviewMaterializationError,
    ReviewMaterializationErrorCode,
    ReviewResultMaterializationRequest,
    _materialization_payload,
    _materialize_findings,
    _validate_materialization_request,
)
from backend.agent_runtime.agents.review.review_assessment import (
    execute_findings_assessment,
)
from backend.agent_runtime.agents.review.review_assessment_model import (
    CorrectionHandoffSignal,
    FindingsAssessmentRequest,
    ReviewAssessmentSignal,
)
from backend.agent_runtime.agents.review.review_coordination_model import (
    PreparedReviewCall,
    ReviewPreparationRequest,
)
from backend.agent_runtime.agents.review.review_coordinator import ReviewCoordinator
from backend.agent_runtime.agents.review.review_model import ReviewPortResult
from backend.agent_runtime.contracts import ReviewResult


class ReviewerAgent:
    __slots__ = ("_coordinator",)

    def __init__(self, coordinator: ReviewCoordinator) -> None:
        if not isinstance(coordinator, ReviewCoordinator):
            raise TypeError("coordinator must be a ReviewCoordinator")
        self._coordinator = coordinator

    def semantic_review(
        self,
        *,
        request: ReviewPreparationRequest,
    ) -> tuple[PreparedReviewCall, ReviewPortResult]:
        if type(request) is not ReviewPreparationRequest:
            raise TypeError("request must be a ReviewPreparationRequest")
        if request.capability_id.value != "CAP-V01":
            raise ReviewMaterializationError(ReviewMaterializationErrorCode.UNSUPPORTED_CAPABILITY)
        prepared = self._coordinator.prepare(request=request)
        technical_result = self._coordinator.execute(prepared=prepared)
        return prepared, technical_result

    def build_review_result(
        self,
        *,
        request: ReviewResultMaterializationRequest,
    ) -> ReviewResult:
        if type(request) is not ReviewResultMaterializationRequest:
            raise TypeError("request must be a ReviewResultMaterializationRequest")
        _validate_materialization_request(request)
        findings = _materialize_findings(request)
        assessment, correction_required, coverage, confidence = _materialization_payload(
            request, findings
        )
        try:
            return ReviewResult(
                meta=request.result_meta,
                review_id=request.review_id,
                target_production_ref=(request.prepared.canonical_request.target_production_ref),
                findings=findings,
                overall_assessment=assessment,
                correction_required=correction_required,
                coverage=coverage,
                evidence_refs_used=request.technical_result.evidence_refs_used,
                confidence=confidence,
                limitations=request.technical_result.limitations,
                warnings=request.technical_result.warnings,
            )
        except (TypeError, ValueError) as error:
            raise ReviewMaterializationError(
                ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH
            ) from error

    def assess_findings(
        self,
        *,
        request: FindingsAssessmentRequest,
    ) -> tuple[ReviewAssessmentSignal, CorrectionHandoffSignal | None]:
        return execute_findings_assessment(
            coordinator=self._coordinator,
            request=request,
        )
