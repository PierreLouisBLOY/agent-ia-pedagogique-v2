"""Test-only owner bindings for canonical assessment, correction and QCM paths."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.agent_runtime.agents.evidence import (
    DocumentContentResult,
    EvidenceAgent,
    EvidenceCoverageStatus,
    EvidenceFetchRequest,
    EvidenceSetBuildRequest,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalCoordinator,
    RetrievalSearchResult,
    RetrievalSignals,
)
from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationRequest,
    CorrectionPreparationRequest,
    GenerationCoordinator,
    GenerationGuardAssessment,
    GenerationGuardPolicy,
    GenerationGuardRequest,
    GenerationOperation,
    GenerationOutputGuard,
    GenerationPortResult,
    GenerationPortResultStatus,
    GenerationPreparationRequest,
    GeneratorAgent,
    ProductionCandidateBuildRequest,
    ResolvedCorrectionTarget,
)
from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewOperation,
    ReviewPortResult,
    ReviewPortResultStatus,
    ReviewPreparationRequest,
    ReviewResultMaterializationRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    CorrectionRequest,
    CorrectionResult,
    EvidenceRequest,
    EvidenceSet,
    FailurePolicy,
    GateDecisionValue,
    GateRequest,
    GateStatus,
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
    StepSpec,
)
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateEngine,
    GateResolution,
    GateResolutionDisposition,
)
from backend.agent_runtime.orchestration import (
    CompletionDisposition,
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
    WorkflowCompletionDecision,
    WorkflowKind,
    WorkflowRequirements,
    WorkflowResponsibility,
    WorkflowSelectionDecision,
    WorkflowSelector,
)
from backend.agent_runtime.runtime import Plan, initialize_run_state
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant
from tests.e2e.core.fixtures import SyntheticPedagogicalFixture, SyntheticSourceEntry
from tests.support.evidence_retrieval_fakes import (
    RecordingDocumentContentPort,
    RecordingEvidenceSearchPort,
)
from tests.support.gate_fakes import RecordingGateDecisionSource, make_gate_decision
from tests.support.generation_fakes import RecordingGenerationPort
from tests.support.orchestration_fakes import (
    FakePreLaunchGuard,
    FakeWorkflowCompletionEvaluator,
    RecordingStepRunner,
    run_until_decisive,
)
from tests.support.review_fakes import RecordingReviewPort
from tests.support.use_case_routing_fakes import NOW as ROUTING_NOW
from tests.support.use_case_routing_fakes import make_request, make_router

E_NOW = Instant(datetime(2026, 8, 28, 15, 0, tzinfo=UTC))
E_LATER = Instant(datetime(2026, 8, 28, 15, 1, tzinfo=UTC))
E_GATE_NOW = Instant(datetime(2026, 8, 28, 15, 2, tzinfo=UTC))

R = WorkflowResponsibility

_CAPABILITY: Mapping[R, str | None] = {
    R.DIRECT_APPLICATION: "CAP-R02",
    R.EVIDENCE: "CAP-E01",
    R.GENERATE_TRANSFORM: "CAP-G01",
    R.REVIEW: "CAP-V01",
    R.DETERMINISTIC_VALIDATION: "CAP-A01",
    R.CORRECTION: "CAP-G03",
    R.EVIDENCE_JOIN: None,
    R.VARIANT_GENERATION: "CAP-G01",
    R.VARIANT_JOIN: None,
    R.VARIANT_SELECTION: None,
    R.GATE: None,
    R.PROMOTION: "CAP-A02",
}

_REQUIRED: Mapping[WorkflowKind, tuple[R, ...]] = {
    WorkflowKind.WF_0: (R.DIRECT_APPLICATION,),
    WorkflowKind.WF_1: (R.EVIDENCE,),
    WorkflowKind.WF_3: (R.REVIEW,),
    WorkflowKind.WF_6: (
        R.EVIDENCE,
        R.GENERATE_TRANSFORM,
        R.DETERMINISTIC_VALIDATION,
        R.REVIEW,
    ),
    WorkflowKind.WF_7: (R.CORRECTION,),
    WorkflowKind.WF_8: (R.EVIDENCE, R.EVIDENCE_JOIN),
    WorkflowKind.WF_9: (R.VARIANT_GENERATION, R.VARIANT_JOIN, R.VARIANT_SELECTION),
    WorkflowKind.WF_11: (R.DETERMINISTIC_VALIDATION, R.GATE, R.PROMOTION),
}

_EXECUTABLE = frozenset(
    {
        R.DIRECT_APPLICATION,
        R.EVIDENCE,
        R.GENERATE_TRANSFORM,
        R.REVIEW,
        R.DETERMINISTIC_VALIDATION,
        R.CORRECTION,
        R.VARIANT_GENERATION,
        R.PROMOTION,
    }
)


@dataclass(frozen=True, slots=True)
class CompiledScenarioPlan:
    selection: WorkflowSelectionDecision
    plan: Plan
    scheduler_events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedCandidateWitness:
    request: ProductionRequest
    candidate: ProductionCandidate
    guard: GenerationGuardAssessment
    port_call_count: int


@dataclass(frozen=True, slots=True)
class EvidenceBranchWitness:
    request: EvidenceRequest
    evidence_set: EvidenceSet
    search_call_count: int
    content_call_count: int
    raw_text: str


@dataclass(frozen=True, slots=True)
class ApplicationRouteWitness:
    use_case_id: str
    capability_id: str
    call_count: int
    success: bool
    idempotency_key: str | None


@dataclass(frozen=True, slots=True)
class ReviewWitness:
    result: ReviewResult
    port_call_count: int


@dataclass(frozen=True, slots=True)
class GatePromotionWitness:
    resolution: GateResolution
    promotion: ApplicationRouteWitness | None
    events: tuple[str, ...]


class OpaqueDeterministicSelector:
    """Selects one joined reference without semantic or quality scoring."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def select(self, candidate_refs: tuple[str, ...]) -> int:
        if not candidate_refs:
            raise ValueError("candidate_refs must not be empty")
        self.calls.append(candidate_refs)
        return 0


class RecordingRenderEffectPort:
    """Nominal E render probe; SCN-08 never invokes it."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def render(self, production_ref: str) -> None:
        self.calls.append(production_ref)


@dataclass(frozen=True, slots=True)
class Scn06Witness:
    compiled: CompiledScenarioPlan
    evidence: tuple[EvidenceBranchWitness, ...]
    generation: GeneratedCandidateWitness
    validation: ApplicationRouteWitness
    review: ReviewWitness
    events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Scn07Witness:
    compiled: CompiledScenarioPlan
    evidence: EvidenceBranchWitness
    correction_request: CorrectionRequest
    candidate: ProductionCandidate
    correction_result: CorrectionResult
    correction_guard: GenerationGuardAssessment
    correction_port_call_count: int
    rereview: ReviewWitness
    final_read: ApplicationRouteWitness
    events: tuple[str, ...]
    correction_count: int


@dataclass(frozen=True, slots=True)
class Scn08Witness:
    compiled: CompiledScenarioPlan
    variants: tuple[GeneratedCandidateWitness, ...]
    selected_index: int
    selection_policy: str
    selection_call_count: int
    review: ReviewWitness
    validation: ApplicationRouteWitness
    gate_promotion: GatePromotionWitness
    render_effect_count: int
    events: tuple[str, ...]


def compile_e_plan(case_code: str, *, plan_version: int = 1) -> CompiledScenarioPlan:
    if case_code == "SCN-06":
        requirements = WorkflowRequirements(
            external_evidence_required=True,
            parallel_evidence_branches=2,
            parallel_evidence_independent=True,
            production_required=True,
            deterministic_validation_required=True,
            independent_review_required=True,
        )
        branches = 2
    elif case_code == "SCN-07":
        requirements = WorkflowRequirements(
            external_evidence_required=True,
            correction_required=True,
            independent_review_required=True,
            deterministic_validation_required=True,
        )
        branches = 1
    elif case_code == "SCN-08":
        requirements = WorkflowRequirements(
            production_required=True,
            variant_count=2,
            variants_explicitly_useful=True,
            independent_review_required=True,
            promotion_required=True,
        )
        branches = 2
    else:
        raise ValueError("unsupported E scenario")
    selection = WorkflowSelector().select(requirements)
    plan = PlanCompiler().compile(
        PlanCompilationRequest(
            selection=selection,
            plan_id=f"plan-{case_code.casefold()}",
            run_id=f"run-{case_code.casefold()}",
            plan_version=plan_version,
            objective=f"Execute canonical {case_code}",
            success_criteria={"hard_assertions": True},
            stop_conditions={"failure": "stop"},
            bindings=_bindings_for(selection, branches=branches),
            gate_refs=("gate-ref-e",),
        )
    )
    runner = RecordingStepRunner()
    completion = FakeWorkflowCompletionEvaluator(
        WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "E_COMPLETE")
    )
    run_until_decisive(
        plan=plan,
        run_state=initialize_run_state(plan, CorrelationId(f"corr-{case_code.casefold()}")),
        now=E_NOW,
        guard=FakePreLaunchGuard(),
        runner=runner,
        completion_evaluator=completion,
    )
    return CompiledScenarioPlan(
        selection,
        plan,
        tuple(step_id for step_id, _ in runner.calls),
    )


def execute_scn06(fixture: SyntheticPedagogicalFixture) -> Scn06Witness:
    compiled = compile_e_plan("SCN-06")
    evidence_steps = tuple(
        step for step in compiled.plan.steps if step.capability_id == CapabilityId("CAP-E01")
    )
    branches = tuple(
        _execute_evidence_branch("SCN-06", step.step_id, source, index)
        for index, (step, source) in enumerate(zip(evidence_steps, fixture.sources, strict=True))
    )
    evidence_refs = tuple(
        item.evidence_id for branch in branches for item in branch.evidence_set.evidence_items
    )
    generation_step = _step_for(compiled.plan, "CAP-G01")
    generation = _generate_candidate(
        "SCN-06",
        generation_step.step_id,
        "assessment",
        ("instructions", "questions", "marking-scheme"),
        evidence_refs,
        "assessment-candidate:scn-06",
    )
    validation = _route_application(
        "application.run_deterministic_validation",
        "CAP-A01",
        {"production_ref": generation.candidate.production_id},
    )
    review = _review_candidate(
        "SCN-06",
        generation.candidate,
        _candidate_version(generation.candidate, "candidate-v1"),
    )
    events = tuple(_event_for_step(compiled.plan, step_id) for step_id in compiled.scheduler_events)
    return Scn06Witness(compiled, branches, generation, validation, review, events)


def execute_scn07(fixture: SyntheticPedagogicalFixture) -> Scn07Witness:
    compiled = compile_e_plan("SCN-07")
    evidence_step = _step_for(compiled.plan, "CAP-E01")
    evidence = _execute_evidence_branch("SCN-07", evidence_step.step_id, fixture.sources[0], 0)
    events = ["EVIDENCE_AVAILABLE", "PRIOR_REVIEW_FINDING_AVAILABLE"]
    evidence_refs = tuple(item.evidence_id for item in evidence.evidence_set.evidence_items)
    correction_step = _step_for(compiled.plan, "CAP-G03")
    parent_ref = _version("scn-07-reviewed-production", "v1")
    correction_request = CorrectionRequest(
        meta=_invocation_meta("SCN-07", correction_step.step_id, AgentId.AG_03),
        target_production_ref=parent_ref,
        review_ref="review:scn-07:prior",
        finding_ids=("finding:scn-07:major",),
        evidence_refs=evidence_refs,
        preserve_constraints={"constraint": "preserve-fixture-intent"},
        allowed_changes={"finding_ids": ("finding:scn-07:major",)},
        forbidden_changes={"object_identity": True},
        expected_delta={"version": "v2"},
    )
    technical = GenerationPortResult(
        source_step_id=correction_step.step_id,
        operation=GenerationOperation.CORRECT,
        status=GenerationPortResultStatus.SUCCEEDED,
        content="Synthetic corrected production v2.",
        structured_payload={"sections": {"context": "Synthetic context.", "correction-link": "Synthetic link.", "summary": "Synthetic summary."}},
        evidence_refs_used=evidence_refs,
        operation_details={
            "addressed_findings": ("finding:scn-07:major",),
            "unresolved_findings": (),
            "change_summary": "Applied the bounded major-finding correction.",
        },
        execution_metadata={"port_mode": "deterministic_test"},
    )
    port = RecordingGenerationPort({correction_step.step_id: technical})
    generator = GeneratorAgent(GenerationCoordinator(port))
    target = ResolvedCorrectionTarget(
        parent_ref,
        "reviewed_production",
        "structured",
        {"level": "bts-cg-2"},
        content=fixture.sources[0].text,
        structured_payload={"sections": ("context", "correction-link", "summary")},
    )
    prepared, result = generator.correct_production(
        request=CorrectionPreparationRequest(
            CapabilityId("CAP-G03"),
            correction_request,
            target,
            resolved_inputs={"prior_review": "available"},
            output_contract={"type": "corrected_candidate"},
        )
    )
    guard = GenerationOutputGuard().assess(
        request=GenerationGuardRequest(prepared, result, GenerationGuardPolicy())
    )
    candidate, correction_result = generator.build_correction(
        request=CorrectionMaterializationRequest(
            correction_request,
            target,
            prepared,
            result,
            guard,
            _agent_result_meta(correction_request.meta, AgentId.AG_03),
            "scn-07-reviewed-production",
            _version("scn-07-reviewed-production", "v2"),
        )
    )
    events.append("CORRECTION")
    rereview = _review_candidate(
        "SCN-07",
        candidate,
        correction_result.new_production_ref,
    )
    events.append("RE_REVIEW")
    final_read = _route_application(
        "application.read_production",
        "CAP-R02",
        {
            "production_ref": correction_result.new_production_ref.object_ref.entity_id.value,
            "version_ref": correction_result.new_production_ref.version_ref.value,
        },
    )
    events.extend(("FINAL_APPLICATION_READ", "STOP"))
    return Scn07Witness(
        compiled,
        evidence,
        correction_request,
        candidate,
        correction_result,
        guard,
        len(port.calls),
        rereview,
        final_read,
        tuple(events),
        correction_count=len(port.calls),
    )


def execute_scn08(fixture: SyntheticPedagogicalFixture) -> Scn08Witness:
    del fixture
    compiled = compile_e_plan("SCN-08")
    variant_steps = tuple(
        step
        for step in compiled.plan.steps
        if step.executor.kind.value == AgentId.AG_03.value
        and step.capability_id == CapabilityId("CAP-G01")
    )
    variants = tuple(
        _generate_candidate(
            "SCN-08",
            step.step_id,
            "qcm_variant",
            ("question", "options", "answer-key", "feedback"),
            (),
            f"qcm-candidate:scn-08:{index}",
        )
        for index, step in enumerate(variant_steps)
    )
    selector = OpaqueDeterministicSelector()
    selected_index = selector.select(
        tuple(variant.candidate.production_id for variant in variants)
    )
    selected = variants[selected_index].candidate
    review = _review_candidate(
        "SCN-08",
        selected,
        _candidate_version(selected, "candidate-v1"),
    )
    validation = _route_application(
        "application.run_deterministic_validation",
        "CAP-A01",
        {"production_ref": selected.production_id},
    )
    gate_promotion = execute_gate_promotion(
        GateDecisionValue.APPROVED,
        selected.production_id,
    )
    render_port = RecordingRenderEffectPort()
    events = tuple(_event_for_step(compiled.plan, step_id) for step_id in compiled.scheduler_events)
    return Scn08Witness(
        compiled,
        variants,
        selected_index,
        "opaque_deterministic_first_joined_ref",
        len(selector.calls),
        review,
        validation,
        gate_promotion,
        render_effect_count=len(render_port.calls),
        events=events,
    )


def execute_gate_promotion(
    decision_value: GateDecisionValue,
    production_ref: str = "qcm-candidate:scn-08:0",
) -> GatePromotionWitness:
    request = GateRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-scn-08",
            "scn-08-promotion-gate",
            "scn-08-validation",
            CorrelationId("corr-scn-08"),
            E_LATER,
            ActorRef(ActorKind.AGENT, AgentId.AG_01.value),
            GateStatus.PENDING,
        ),
        gate_id="gate-scn-08-promotion",
        gate_type="human_qcm_promotion_approval",
        reason="Validated QCM candidate requires external approval",
        options=({"id": "approve"}, {"id": "reject"}),
        required_actor=ActorRef(ActorKind.USER, "user-scn-08"),
        context_summary={"candidate_ref": production_ref},
        expires_at=None,
    )
    selected_option: dict[str, object] = {
        "id": "approve" if decision_value is GateDecisionValue.APPROVED else "reject"
    }
    decision = make_gate_decision(
        request,
        value=decision_value,
        decided_at=E_GATE_NOW,
        selected_option=selected_option,
        decision_ref=f"gate-decision:scn-08:{decision_value.value}",
    )
    source = RecordingGateDecisionSource(decision)
    resolution = GateEngine(BASELINE_GATE_AUTHORITY_POLICY, source).evaluate(
        request=request,
        now=E_GATE_NOW,
    )
    events = ["VALIDATION", f"GATE_{resolution.disposition.value}"]
    promotion: ApplicationRouteWitness | None = None
    if resolution.disposition is GateResolutionDisposition.APPROVED:
        promotion = _route_application(
            "application.request_promotion",
            "CAP-A02",
            {"production_ref": production_ref},
            idempotency_key="promotion:scn-08:0",
            matrix_gate_satisfied=True,
        )
        events.append("PROMOTION_REQUEST")
    return GatePromotionWitness(resolution, promotion, tuple(events))


def second_correction_plan() -> tuple[Plan, Plan]:
    first = compile_e_plan("SCN-07", plan_version=1).plan
    second = compile_e_plan("SCN-07", plan_version=2).plan
    return first, second


def _bindings_for(
    selection: WorkflowSelectionDecision,
    *,
    branches: int,
) -> tuple[PlanStepBinding, ...]:
    bindings: list[PlanStepBinding] = []
    for stage_index, stage in enumerate(selection.stages):
        responsibilities = list(_REQUIRED[stage.workflow_kind])
        responsibilities.extend(stage.materialized_optional_responsibilities)
        if (
            stage_index > 0
            and selection.stages[stage_index - 1].workflow_kind is WorkflowKind.WF_8
            and stage.workflow_kind is WorkflowKind.WF_6
        ):
            responsibilities.remove(R.EVIDENCE)
        for responsibility in responsibilities:
            if responsibility in {R.EVIDENCE, R.VARIANT_GENERATION} and stage.workflow_kind in {
                WorkflowKind.WF_8,
                WorkflowKind.WF_9,
            }:
                bindings.extend(
                    _binding(stage_index, responsibility, index, branch_index=index)
                    for index in range(branches)
                )
            else:
                bindings.append(_binding(stage_index, responsibility, 0))
    return tuple(bindings)


def _binding(
    stage_index: int,
    responsibility: R,
    suffix: int,
    *,
    branch_index: int | None = None,
) -> PlanStepBinding:
    capability = _CAPABILITY[responsibility]
    return PlanStepBinding(
        stage_index=stage_index,
        responsibility=responsibility,
        step_id=f"s{stage_index}-{responsibility.value.casefold()}-{suffix}",
        objective=f"Execute {responsibility.value}",
        capability_id=CapabilityId(capability) if capability is not None else None,
        permission_scope_ref=(
            f"scope:s{stage_index}:{responsibility.value.casefold()}"
            if responsibility in _EXECUTABLE
            else None
        ),
        success_criteria={"completed": True},
        failure_policy=FailurePolicy.STOP,
        output_contract={"type": "result"},
        branch_index=branch_index,
    )


def _execute_evidence_branch(
    case_code: str,
    step_id: str,
    source: SyntheticSourceEntry,
    branch_index: int,
) -> EvidenceBranchWitness:
    candidate = RetrievalCandidate(
        candidate_id=f"candidate-{case_code.casefold()}-{branch_index}",
        channel=RetrievalChannel.STRUCTURED,
        source_ref=source.source_ref.value,
        source_kind="synthetic_fixture",
        locator=f"fixture:{case_code.casefold()}:{branch_index}",
        signals=RetrievalSignals(structured_rank=branch_index),
        canonical_object_ref=source.source_ref.value,
        version_or_checksum=source.version_code,
        provenance={"fixture": case_code},
        authority={"basis": "test_only"},
        metadata={"freshness": "CURRENT"},
    )
    responses = {
        channel: RetrievalSearchResult(
            channel,
            (candidate,) if channel is RetrievalChannel.STRUCTURED else (),
        )
        for channel in (
            RetrievalChannel.STRUCTURED,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.RELATIONAL,
            RetrievalChannel.SEMANTIC,
        )
    }
    search = RecordingEvidenceSearchPort(responses)
    content = RecordingDocumentContentPort(
        {
            candidate.candidate_id: DocumentContentResult(
                candidate.candidate_id,
                candidate.source_ref,
                candidate.locator,
                source.text,
                E_NOW,
                candidate.source_kind,
                candidate.version_or_checksum,
                provenance={"fixture": case_code},
                metadata={"branch_index": branch_index},
            )
        }
    )
    agent = EvidenceAgent(RetrievalCoordinator(search), content)
    request = EvidenceRequest(
        meta=_invocation_meta(case_code, step_id, AgentId.AG_02),
        search_goal=f"Resolve independent synthetic source branch {branch_index}",
        scope={"case": case_code, "branch_index": branch_index},
        source_policy={"kinds": ("synthetic_fixture",)},
        filters={"source_ref": source.source_ref.value},
        required_authority=None,
        max_items=1,
    )
    retrieval = agent.search_evidence(request=request)
    fused = retrieval.ranked_candidates[0]
    materialized = agent.fetch_evidence_item(
        request=EvidenceFetchRequest(
            f"evidence:{case_code.casefold()}:{branch_index}",
            request,
            retrieval,
            fused,
        )
    )
    coverage = agent.assess_evidence_coverage(
        retrieval=retrieval,
        materialized=(materialized,),
    )
    status = (
        AgentResultStatus.PARTIAL
        if coverage.status is EvidenceCoverageStatus.PARTIAL
        else AgentResultStatus.SUCCEEDED
    )
    evidence_set = agent.build_evidence_set(
        build_request=EvidenceSetBuildRequest(
            request,
            _agent_result_meta(request.meta, AgentId.AG_02, status=status),
            retrieval,
            (materialized,),
        )
    )
    return EvidenceBranchWitness(
        request,
        evidence_set,
        len(search.calls),
        len(content.calls),
        source.text,
    )


def _generate_candidate(
    case_code: str,
    step_id: str,
    production_kind: str,
    sections: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    production_id: str,
) -> GeneratedCandidateWitness:
    request = ProductionRequest(
        meta=_invocation_meta(case_code, step_id, AgentId.AG_03),
        production_kind=production_kind,
        brief=f"Create bounded synthetic {production_kind}",
        output_format="structured",
        pedagogical_context={"case": case_code},
        constraints={"synthetic": True},
        evidence_refs=evidence_refs,
        target_ref=None,
        expected_sections=sections,
    )
    technical = GenerationPortResult(
        step_id,
        GenerationOperation.GENERATE,
        GenerationPortResultStatus.SUCCEEDED,
        content=f"Synthetic output for {production_id}.",
        structured_payload={
            "sections": {
                section: f"Synthetic {section} for {production_id}." for section in sections
            }
        },
        evidence_refs_used=evidence_refs,
        execution_metadata={"port_mode": "deterministic_test"},
    )
    port = RecordingGenerationPort({step_id: technical})
    generator = GeneratorAgent(GenerationCoordinator(port))
    prepared, result = generator.generate_production(
        request=GenerationPreparationRequest(
            CapabilityId("CAP-G01"),
            request,
            resolved_inputs={"case": case_code},
            output_contract={"type": "structured_candidate"},
        )
    )
    guard = GenerationOutputGuard().assess(
        request=GenerationGuardRequest(
            prepared,
            result,
            GenerationGuardPolicy(
                require_structured_payload=True,
                required_payload_keys=("sections",),
                allowed_payload_keys=("sections",),
                section_container_key="sections",
            ),
        )
    )
    candidate = generator.build_candidate(
        request=ProductionCandidateBuildRequest(
            request,
            prepared,
            result,
            guard,
            _agent_result_meta(request.meta, AgentId.AG_03),
            production_id,
        )
    )
    return GeneratedCandidateWitness(request, candidate, guard, len(port.calls))


def _review_candidate(
    case_code: str,
    candidate: ProductionCandidate,
    target_ref: ObjectVersionRef,
) -> ReviewWitness:
    request = ReviewRequest(
        meta=_invocation_meta(case_code, f"{case_code.casefold()}-review", AgentId.AG_04),
        target_production_ref=target_ref,
        review_dimensions=(ReviewDimension.PEDAGOGY, ReviewDimension.STRUCTURE),
        criteria={"independent": True},
        evidence_refs=candidate.evidence_refs_used,
        severity_policy={"blocking": "reject"},
        context_slice={"case": case_code},
        independence_requirements={"separate_from_generation": True},
    )
    technical = ReviewPortResult(
        request.meta.step_id,
        ReviewOperation.SEMANTIC_REVIEW,
        ReviewPortResultStatus.SUCCEEDED,
        structured_payload={
            "overall_assessment": OverallAssessment.ACCEPTABLE.value,
            "correction_required": False,
            "coverage": (ReviewDimension.PEDAGOGY.value, ReviewDimension.STRUCTURE.value),
            "confidence": {"level": "high"},
        },
        evidence_refs_used=candidate.evidence_refs_used,
    )
    port = RecordingReviewPort(result=technical)
    reviewer = ReviewerAgent(ReviewCoordinator(port))
    prepared, result = reviewer.semantic_review(
        request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"),
            request,
            ResolvedReviewTarget(
                target_ref,
                candidate.content,
                candidate.structured_payload,
            ),
            resolved_inputs={"candidate_state": candidate.validation_state.value},
            output_contract={"type": "semantic_review"},
        )
    )
    review = reviewer.build_review_result(
        request=ReviewResultMaterializationRequest(
            prepared,
            result,
            ContractMeta(
                AGENT_CONTRACT_SCHEMA_V1_0,
                request.meta.run_id,
                request.meta.step_id,
                request.meta.parent_step_id,
                request.meta.correlation_id,
                E_LATER,
                ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
                ReviewStatus.COMPLETED,
            ),
            f"review:{case_code.casefold()}",
        )
    )
    return ReviewWitness(review, len(port.calls))


def _route_application(
    use_case_id: str,
    capability_id: str,
    payload: dict[str, object],
    *,
    idempotency_key: str | None = None,
    matrix_gate_satisfied: bool = False,
) -> ApplicationRouteWitness:
    from backend.agent_runtime.policy import PolicyFacts

    request, context = make_request(
        use_case_id,
        capability_code=capability_id,
        idempotency_key=idempotency_key,
        payload=payload,
        requested_effect=(
            {"effect_type": "promotion_request", "production_ref": payload["production_ref"]}
            if use_case_id == "application.request_promotion"
            else None
        ),
        policy_facts=PolicyFacts(matrix_gate_satisfied=matrix_gate_satisfied),
    )
    router, inbound = make_router(request)
    result = router.route(
        agent_id=AgentId.AG_01,
        request=request,
        context=context,
        evaluated_at=ROUTING_NOW,
    )
    return ApplicationRouteWitness(
        use_case_id,
        capability_id,
        len(inbound.calls),
        result.outcome.success,
        request.idempotency_key,
    )


def _event_for_step(plan: Plan, step_id: str) -> str:
    step = next(item for item in plan.steps if item.step_id == step_id)
    if step.kind is StepKind.JOIN:
        return "JOIN"
    if step.kind is StepKind.DECISION:
        return "SELECTION"
    capability = step.capability_id.value if step.capability_id is not None else "NONE"
    return {
        "CAP-E01": f"EVIDENCE_BRANCH_{step.parallel_group and step_id.rsplit('-', 1)[-1]}",
        "CAP-G01": (
            f"VARIANT_{step_id.rsplit('-', 1)[-1]}"
            if step.parallel_group is not None
            else "GENERATION"
        ),
        "CAP-G03": "CORRECTION",
        "CAP-A01": "VALIDATION",
        "CAP-V01": "REVIEW",
        "CAP-R02": "FINAL_APPLICATION_READ",
        "CAP-O05": "GATE",
        "CAP-A02": "PROMOTION_REQUEST",
    }.get(capability, capability)


def _step_for(plan: Plan, capability_id: str) -> StepSpec:
    return next(step for step in plan.steps if step.capability_id == CapabilityId(capability_id))


def _candidate_version(candidate: ProductionCandidate, version: str) -> ObjectVersionRef:
    return _version(candidate.production_id, version)


def _version(object_id: str, version: str) -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", object_id)),
        VersionRef(version),
    )


def _invocation_meta(case_code: str, step_id: str, agent_id: AgentId) -> ContractMeta[InvocationStatus]:
    suffix = case_code.casefold()
    return ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        f"run-{suffix}",
        step_id,
        None,
        CorrelationId(f"corr-{suffix}"),
        E_NOW,
        ActorRef(ActorKind.AGENT, agent_id.value),
        InvocationStatus.PLANNED,
    )


def _agent_result_meta(
    invocation: ContractMeta[InvocationStatus],
    agent_id: AgentId,
    *,
    status: AgentResultStatus = AgentResultStatus.SUCCEEDED,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        invocation.run_id,
        invocation.step_id,
        invocation.parent_step_id,
        invocation.correlation_id,
        E_LATER,
        ActorRef(ActorKind.AGENT, agent_id.value),
        status,
    )


def candidate_sections(candidate: ProductionCandidate) -> tuple[str, ...]:
    sections = candidate.structured_payload.get("sections")
    if not isinstance(sections, Mapping):
        return ()
    return tuple(str(key) for key in sections)


def candidate_is_bounded(candidate: ProductionCandidate, evidence_refs: tuple[str, ...]) -> bool:
    return (
        candidate.validation_state is ProductionValidationState.CANDIDATE
        and set(candidate.evidence_refs_used).issubset(evidence_refs)
    )
