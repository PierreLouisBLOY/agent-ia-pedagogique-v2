from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from backend.agent_runtime.agents.evidence import EvidenceSetBuildRequest
from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationRequest,
    CorrectionPreparationRequest,
    GenerationCoordinator,
    GenerationGuardPolicy,
    GenerationGuardRequest,
    GenerationOperation,
    GenerationOutputGuard,
    GenerationPortResult,
    GenerationPortResultStatus,
    GeneratorAgent,
    ResolvedCorrectionTarget,
)
from backend.agent_runtime.agents.review import (
    FindingsAssessmentRequest,
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewOperation,
    ReviewPortResult,
    ReviewPortResultStatus,
    ReviewPreparationRequest,
    ReviewResultMaterializationRequest,
    ReviewSecurityPolicy,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    FindingSeverity,
    InvocationStatus,
    OverallAssessment,
    ProductionCandidate,
    ProductionRequest,
    ProductionValidationState,
    ReviewDimension,
    ReviewRequest,
    ReviewResult,
    ReviewStatus,
    StepKind,
    WorkflowStatus,
)
from backend.agent_runtime.orchestration import (
    HumanGateAnchor,
    WorkflowKind,
    WorkflowRequirements,
)
from backend.agent_runtime.runtime import (
    PlanHistory,
    PlanRevisionCode,
    PlanRevisionEngine,
    StepRuntimeStatus,
    StepState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant
from tests.integration.test_canonical_workflow_scenarios import _compile as _compile_workflow
from tests.integration.test_evidence_materialization import (
    _agent_for as _evidence_agent_for,
)
from tests.integration.test_evidence_materialization import (
    _materialize_available,
)
from tests.integration.test_evidence_materialization import (
    _request as _evidence_request,
)
from tests.integration.test_evidence_materialization import (
    _result_meta as _evidence_result_meta,
)
from tests.integration.test_generation_candidate_materialization import (
    _build as _build_generated,
)
from tests.integration.test_generation_candidate_materialization import (
    _canonical as _generation_request,
)
from tests.integration.test_generation_candidate_materialization import (
    _execute as _execute_generation,
)
from tests.integration.test_generation_candidate_materialization import (
    _result as _generation_result,
)
from tests.integration.test_replan_revision_flow import (
    STARTED,
)
from tests.integration.test_replan_revision_flow import (
    _plan as _revision_plan,
)
from tests.integration.test_replan_revision_flow import (
    _run_state as _revision_run_state,
)
from tests.integration.test_replan_revision_flow import (
    _step as _revision_step,
)
from tests.integration.test_review_security_pipeline import _evidence_warning
from tests.support.generation_fakes import RecordingGenerationPort
from tests.support.review_fakes import RecordingReviewPort
from tests.support.review_workflow_fakes import (
    AG01Decision,
    RecordingAG01PostReview,
    RecordingApplicationValidator,
    RecordingHumanGate,
    RecordingPromotionProbe,
)

NOW = Instant(datetime(2026, 8, 26, 17, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 26, 17, 1, tzinfo=UTC))


def _version(value: str) -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "ag04-workflow")),
        VersionRef(value),
    )


def _review_request(
    target_ref: ObjectVersionRef,
    evidence_refs: tuple[str, ...],
    *,
    step_id: str,
) -> ReviewRequest:
    return ReviewRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-ag04-workflows",
            step_id,
            None,
            CorrelationId(f"corr-{step_id}"),
            NOW,
            ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            InvocationStatus.PLANNED,
        ),
        target_production_ref=target_ref,
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.RISK),
        criteria={"required": ("bounded",)},
        evidence_refs=evidence_refs,
        severity_policy={"blocking": ("unsafe",)},
        context_slice={"sections": ("content",)},
        independence_requirements={"independent": True},
    )


def _review_candidate(
    candidate: ProductionCandidate,
    target_ref: ObjectVersionRef,
    *,
    step_id: str,
    severity: FindingSeverity | None = None,
    evidence_security_by_ref: dict[str, object] | None = None,
) -> tuple[ReviewRequest, ResolvedReviewTarget, ReviewResult, ReviewerAgent]:
    request = _review_request(target_ref, candidate.evidence_refs_used, step_id=step_id)
    target = ResolvedReviewTarget(
        target_ref,
        content=candidate.content,
        structured_payload=candidate.structured_payload,
    )
    finding_id = f"finding-{step_id}"
    findings = ()
    overall = OverallAssessment.ACCEPTABLE
    correction_required = False
    if severity is not None:
        quote = (candidate.content or "Exact").split(maxsplit=1)[0]
        findings = (
            {
                "finding_id": finding_id,
                "dimension": ReviewDimension.RISK.value,
                "severity": severity.value,
                "description": "Bounded review finding.",
                "target_locator": {
                    "kind": "text_span",
                    "start": 0,
                    "end": len(quote),
                    "quote": quote,
                },
                "rationale": "Bounded rationale.",
                "correction_required": True,
                "evidence_refs": candidate.evidence_refs_used[:1],
                "confidence": {"level": "high"},
                "suggested_action": {"action": "revise"},
            },
        )
        correction_required = True
        overall = (
            OverallAssessment.UNUSABLE
            if severity is FindingSeverity.BLOCKING
            else OverallAssessment.CORRECTION_REQUIRED
        )
    technical = ReviewPortResult(
        source_step_id=step_id,
        operation=ReviewOperation.SEMANTIC_REVIEW,
        status=ReviewPortResultStatus.SUCCEEDED,
        structured_payload={
            "overall_assessment": overall.value,
            "correction_required": correction_required,
            "coverage": (
                ReviewDimension.ACCURACY.value,
                ReviewDimension.RISK.value,
            ),
            "confidence": {"level": "high"},
        },
        technical_findings=findings,
        evidence_refs_used=candidate.evidence_refs_used,
    )
    agent = ReviewerAgent(ReviewCoordinator(RecordingReviewPort(technical)))
    prepared, returned = agent.semantic_review(
        request=ReviewPreparationRequest(CapabilityId("CAP-V01"), request, target)
    )
    result = agent.build_review_result(
        request=ReviewResultMaterializationRequest(
            prepared,
            returned,
            ContractMeta(
                AGENT_CONTRACT_SCHEMA_V1_0,
                request.meta.run_id,
                request.meta.step_id,
                None,
                request.meta.correlation_id,
                LATER,
                ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
                ReviewStatus.COMPLETED,
            ),
            f"review:{step_id}",
            ReviewSecurityPolicy(),
            evidence_security_by_ref or {},
        )
    )
    return request, target, result, agent


def _assess_review(
    request: ReviewRequest,
    target: ResolvedReviewTarget,
    result: ReviewResult,
):
    finding_ids = tuple(item.finding_id for item in result.findings)
    blocking_ids = tuple(
        item.finding_id
        for item in result.findings
        if item.severity is FindingSeverity.BLOCKING
    )
    technical = ReviewPortResult(
        source_step_id=request.meta.step_id,
        operation=ReviewOperation.ASSESS_FINDINGS,
        status=ReviewPortResultStatus.SUCCEEDED,
        structured_payload={
            "assessed_finding_ids": finding_ids,
            "blocking_finding_ids": blocking_ids,
            "correction_finding_ids": finding_ids,
            "overall_assessment": result.overall_assessment.value,
            "correction_required": bool(finding_ids),
            "confidence": {"level": "high"},
        },
        evidence_refs_used=result.evidence_refs_used,
    )
    agent = ReviewerAgent(ReviewCoordinator(RecordingReviewPort(technical)))
    return agent.assess_findings(
        request=FindingsAssessmentRequest(
            CapabilityId("CAP-V02"),
            request,
            result,
            target,
            f"review-ref:{request.meta.step_id}",
        )
    )


def _generated_candidate(
    *, evidence_refs: tuple[str, ...] | None = None
) -> tuple[ProductionRequest, ProductionCandidate]:
    request = _generation_request()
    technical = _generation_result(GenerationOperation.GENERATE)
    if evidence_refs is not None:
        request = replace(request, evidence_refs=evidence_refs)
        technical = replace(technical, evidence_refs_used=evidence_refs[:1])
    agent, prepared, result, _ = _execute_generation(request, "CAP-G01", technical)
    candidate = _build_generated(
        agent,
        request,
        prepared,
        result,
        production_id="ag04-workflow",
        status=AgentResultStatus.SUCCEEDED,
    )
    return request, candidate


def _correct(
    correction,
    *,
    new_ref: ObjectVersionRef,
    content: str,
) -> tuple[ProductionCandidate, object]:
    target = ResolvedCorrectionTarget(
        correction.target_production_ref,
        "learning_activity",
        "structured-markdown",
        content=content,
    )
    technical = GenerationPortResult(
        correction.meta.step_id,
        GenerationOperation.CORRECT,
        GenerationPortResultStatus.SUCCEEDED,
        content=f"Corrected {new_ref.version_ref.value}.",
        evidence_refs_used=correction.evidence_refs[:1],
        operation_details={
            "addressed_findings": correction.finding_ids,
            "unresolved_findings": (),
            "change_summary": "Applied the bounded correction.",
        },
    )
    agent = GeneratorAgent(
        GenerationCoordinator(RecordingGenerationPort({correction.meta.step_id: technical}))
    )
    prepared, returned = agent.correct_production(
        request=CorrectionPreparationRequest(
            CapabilityId("CAP-G03"), correction, target
        )
    )
    guard = GenerationOutputGuard().assess(
        request=GenerationGuardRequest(
            prepared,
            returned,
            GenerationGuardPolicy(),
        )
    )
    return agent.build_correction(
        request=CorrectionMaterializationRequest(
            correction,
            target,
            prepared,
            returned,
            guard,
            ContractMeta(
                AGENT_CONTRACT_SCHEMA_V1_0,
                correction.meta.run_id,
                correction.meta.step_id,
                None,
                correction.meta.correlation_id,
                LATER,
                ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
                AgentResultStatus.SUCCEEDED,
            ),
            f"candidate-{new_ref.version_ref.value}",
            new_ref,
        )
    )


def test_g3_g4_wf5_real_generation_targets_exact_c08_with_optional_a01() -> None:
    for validate in (False, True):
        request, candidate = _generated_candidate()
        original = candidate
        validator = RecordingApplicationValidator()
        validation = validator.validate(candidate) if validate else None
        target_ref = _version("v1")
        review_request, target, review, _ = _review_candidate(
            candidate,
            target_ref,
            step_id=f"wf5-review-{validate}",
        )

        assert request.evidence_refs == ("evidence:alpha", "evidence:beta")
        assert review_request.target_production_ref is target_ref
        assert target.target_production_ref is target_ref
        assert candidate is original
        assert candidate.validation_state is ProductionValidationState.CANDIDATE
        assert review.target_production_ref is target_ref
        assert (validation is None) is (not validate)
        assert not hasattr(review, "promotion_decision")


def test_g5_wf6_real_evidence_generation_validation_review_preserves_lineage() -> None:
    evidence_request = _evidence_request()
    evidence_agent, _ = _evidence_agent_for((("x", "v1"), ("x", "v2")))
    retrieval, materialized = _materialize_available(evidence_agent, evidence_request)
    evidence_set = evidence_agent.build_evidence_set(
        build_request=EvidenceSetBuildRequest(
            evidence_request,
            _evidence_result_meta(AgentResultStatus.SUCCEEDED),
            retrieval,
            materialized,
        )
    )
    evidence_refs = tuple(item.evidence_id for item in evidence_set.evidence_items)
    _, candidate = _generated_candidate(evidence_refs=evidence_refs)
    validator = RecordingApplicationValidator()
    validation = validator.validate(candidate)
    security = {evidence_refs[0]: _evidence_warning(evidence_refs[0])}
    _, _, review, reviewer = _review_candidate(
        candidate,
        _version("v-evidence"),
        step_id="wf6-review",
        evidence_security_by_ref=security,
    )

    assert candidate.evidence_refs_used == evidence_refs[:1]
    assert validation.accepted is True
    assert validator.calls == [candidate]
    assert evidence_set.conflicts[0]["type"] == "VERSION_DIVERGENCE"
    assert any(
        warning["code"] == "EVIDENCE_SECURITY_WARNING_PRESENT"
        for warning in review.warnings
    )
    assert review.overall_assessment is OverallAssessment.ACCEPTABLE
    assert not hasattr(reviewer, "search")
    assert "consensus" not in repr(evidence_set.coverage).casefold()


def test_g6_wf7_ag01_builds_c11_then_ag03_corrects_and_ag04_rereviews() -> None:
    _, candidate_v1 = _generated_candidate()
    request_v1, target_v1, review_v1, _ = _review_candidate(
        candidate_v1,
        _version("v1"),
        step_id="wf7-review-v1",
        severity=FindingSeverity.BLOCKING,
    )
    signal_v1, handoff_v1 = _assess_review(request_v1, target_v1, review_v1)
    assert handoff_v1 is not None
    ag01 = RecordingAG01PostReview(AG01Decision.REQUEST_CORRECTION)
    c11_v1 = ag01.build_correction_request(
        handoff=handoff_v1,
        run_id="run-wf7-v1",
        step_id="correction-v1",
        correlation_id="corr-wf7-v1",
        created_at=NOW,
    )
    candidate_v2, correction_v2 = _correct(
        c11_v1,
        new_ref=_version("v2"),
        content=candidate_v1.content or "Original",
    )
    request_v2, target_v2, review_v2, reviewer = _review_candidate(
        candidate_v2,
        correction_v2.new_production_ref,
        step_id="wf7-review-v2",
    )
    signal_v2, handoff_v2 = _assess_review(request_v2, target_v2, review_v2)

    assert signal_v1.promotion_blocked_by_review is True
    assert c11_v1.target_production_ref == _version("v1")
    assert correction_v2.new_production_ref == _version("v2")
    assert request_v2.target_production_ref == correction_v2.new_production_ref
    assert signal_v2.promotion_blocked_by_review is False
    assert handoff_v2 is None
    assert candidate_v2.validation_state is ProductionValidationState.CANDIDATE
    assert not hasattr(reviewer, "correct_production")


def test_g7_wf7_two_cycles_are_distinct_plan_versions_and_bounded() -> None:
    from tests.integration.test_ag03_workflow_compatibility import _compile

    _, candidate_v1 = _generated_candidate()
    request_v1, target_v1, review_v1, _ = _review_candidate(
        candidate_v1,
        _version("v1"),
        step_id="wf7-cycle-review-v1",
        severity=FindingSeverity.BLOCKING,
    )
    _, handoff_v1 = _assess_review(request_v1, target_v1, review_v1)
    assert handoff_v1 is not None
    ag01 = RecordingAG01PostReview(AG01Decision.REQUEST_CORRECTION)
    c11_v1 = ag01.build_correction_request(
        handoff=handoff_v1,
        run_id="run-cycle-v1",
        step_id="correction-cycle-v1",
        correlation_id="corr-cycle-v1",
        created_at=NOW,
    )
    candidate_v2, result_v2 = _correct(
        c11_v1,
        new_ref=_version("v2"),
        content=candidate_v1.content or "Original",
    )
    request_v2, target_v2, review_v2, _ = _review_candidate(
        candidate_v2,
        result_v2.new_production_ref,
        step_id="wf7-cycle-review-v2",
        severity=FindingSeverity.BLOCKING,
    )
    _, handoff_v2 = _assess_review(request_v2, target_v2, review_v2)
    assert handoff_v2 is not None
    c11_v2 = ag01.build_correction_request(
        handoff=handoff_v2,
        run_id="run-cycle-v2",
        step_id="correction-cycle-v2",
        correlation_id="corr-cycle-v2",
        created_at=NOW,
    )
    candidate_v3, result_v3 = _correct(
        c11_v2,
        new_ref=_version("v3"),
        content=candidate_v2.content or "Corrected",
    )

    _, plan_v1 = _compile(
        WorkflowRequirements(correction_required=True, independent_review_required=True),
        plan_version=1,
    )
    _, plan_v2 = _compile(
        WorkflowRequirements(correction_required=True, independent_review_required=True),
        plan_version=2,
    )
    current = _revision_plan(1, _revision_step("same-structure"))
    state = _revision_run_state(
        current,
        {"same-structure": StepState("same-structure", StepRuntimeStatus.PENDING)},
        status=WorkflowStatus.REPLANNING,
        started_at=STARTED,
    )
    no_progress = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=state,
        replacement=replace(current, plan_version=2),
    )
    first = _revision_plan(1, _revision_step("structure-a"))
    second = replace(first, plan_version=2, steps=(_revision_step("structure-b"),))
    cycle_state = _revision_run_state(
        second,
        {"structure-b": StepState("structure-b", StepRuntimeStatus.PENDING)},
        status=WorkflowStatus.REPLANNING,
        started_at=STARTED,
    )
    cycle = PlanRevisionEngine().revise(
        history=PlanHistory((first, second)),
        run_state=cycle_state,
        replacement=replace(first, plan_version=3),
    )

    assert (plan_v1.plan_version, plan_v2.plan_version) == (1, 2)
    assert plan_v1.plan_id != plan_v2.plan_id
    assert c11_v1.meta.step_id != c11_v2.meta.step_id
    assert request_v1.meta.step_id != request_v2.meta.step_id
    assert result_v3.parent_production_ref == _version("v2")
    assert result_v3.new_production_ref == _version("v3")
    assert candidate_v3.validation_state is ProductionValidationState.CANDIDATE
    assert PlanRevisionCode.NO_STRUCTURAL_PROGRESS in {
        issue.code for issue in no_progress.issues
    }
    assert PlanRevisionCode.STRUCTURAL_CYCLE_DETECTED in {
        issue.code for issue in cycle.issues
    }


def test_g8_wf10_review_gate_is_explicit_overlay_for_wf3_and_wf5() -> None:
    _, candidate = _generated_candidate()
    _, _, acceptable, reviewer = _review_candidate(
        candidate, _version("v-gate"), step_id="wf10-review"
    )
    _, _, blocking, _ = _review_candidate(
        candidate,
        _version("v-gate-blocking"),
        step_id="wf10-review-blocking",
        severity=FindingSeverity.BLOCKING,
    )
    approve = RecordingHumanGate(True)
    reject = RecordingHumanGate(False)
    assert approve.decide(acceptable) is True
    assert reject.decide(acceptable) is False
    assert approve.decide(blocking) is True
    assert reject.decide(blocking) is False

    for requirements in (
        WorkflowRequirements(
            independent_review_required=True,
            human_gate_required=True,
        ),
        WorkflowRequirements(
            production_required=True,
            independent_review_required=True,
            human_gate_required=True,
        ),
    ):
        selection, plan = _compile_workflow(
            requirements,
            human_anchor=HumanGateAnchor.AFTER_REVIEW,
        )
        gate = next(step for step in plan.steps if step.step_id == "human-gate")
        review = next(
            step for step in plan.steps if step.capability_id == CapabilityId("CAP-V01")
        )
        assert selection.overlays == (WorkflowKind.WF_10,)
        assert gate.kind is StepKind.GATE
        assert gate.depends_on == (review.step_id,)
    assert not hasattr(reviewer, "approve")
    assert not hasattr(reviewer, "gate")
    assert not hasattr(reviewer, "promote")


def test_g9_wf11_separates_validation_runtime_gate_and_promotion_from_ag04() -> None:
    _, plan = _compile_workflow(WorkflowRequirements(promotion_required=True))
    steps = {step.capability_id.value: step for step in plan.steps if step.capability_id}
    _, candidate = _generated_candidate()
    validator = RecordingApplicationValidator()
    gate = RecordingHumanGate(False)
    promotion = RecordingPromotionProbe()
    validation = validator.validate(candidate)
    gate_result = gate.decide({"review": OverallAssessment.ACCEPTABLE.value})

    assert steps["CAP-A01"].executor.kind.value == "APPLICATION"
    assert steps["CAP-O05"].executor.kind.value == "RUNTIME"
    assert steps["CAP-A02"].executor.kind.value == "APPLICATION"
    assert steps["CAP-O05"].depends_on == (steps["CAP-A01"].step_id,)
    assert steps["CAP-A02"].depends_on == (steps["CAP-O05"].step_id,)
    assert promotion.promote(
        candidate,
        validation_accepted=validation.accepted,
        gate_accepted=gate_result,
    ) is False
    assert promotion.calls == []
    assert all(step.executor.kind.value != "AG-04" for step in plan.steps)
