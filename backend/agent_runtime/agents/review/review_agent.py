from __future__ import annotations

from backend.agent_runtime.agents.review.review_agent_model import (
    ReviewMaterializationError,
    ReviewMaterializationErrorCode,
    ReviewResultMaterializationRequest,
    _materialization_payload,
    _materialize_findings,
    _review_security_assessment,
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
from backend.agent_runtime.agents.review.review_security import (
    ReviewSecurityGuard,
    reject_activatable_review_metadata,
    require_security_output_allowed,
)
from backend.agent_runtime.agents.review.review_security_model import ReviewSecurityPolicy
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
        reject_activatable_review_metadata(request.resolved_inputs)
        reject_activatable_review_metadata(request.output_contract)
        security_policy = ReviewSecurityPolicy()
        security = ReviewSecurityGuard().assess(
            target=request.target,
            policy=security_policy,
            review_evidence_refs=request.request.evidence_refs,
        )
        require_security_output_allowed(security, security_policy)
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
        security = _review_security_assessment(request)
        require_security_output_allowed(security, request.security_policy)
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
                limitations=(
                    request.technical_result.limitations + security.limitations
                ),
                warnings=request.technical_result.warnings + security.warnings,
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
