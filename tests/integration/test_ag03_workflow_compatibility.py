from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.generation import (
    GenerationCandidateMaterializationError,
    GenerationClaimAttribution,
    GenerationClaimClass,
    GenerationCoordinator,
    GenerationGuardDisposition,
    GenerationGuardPolicy,
    GenerationGuardRequest,
    GenerationOperation,
    GenerationOutputGuard,
    GenerationPortResult,
    GenerationPortResultStatus,
    GenerationPreparationRequest,
    GeneratorAgent,
    ProductionCandidateBuildRequest,
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
    EvidenceItem,
    EvidenceSet,
    ExecutorKind,
    InvocationStatus,
    ProductionCandidate,
    ProductionRequest,
    ProductionValidationState,
    StepKind,
    WorkflowStatus,
)
from backend.agent_runtime.orchestration import (
    CompletionDisposition,
    CoordinationAction,
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
    WorkflowCompletionDecision,
    WorkflowKind,
    WorkflowRequirements,
    WorkflowResponsibility,
    WorkflowSelector,
)
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    Plan,
    PlanExecutor,
    StepExecutionResult,
    StepRuntimeStatus,
    initialize_run_state,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant
from tests.support.generation_fakes import RecordingGenerationPort, ScenarioArtifacts
from tests.support.orchestration_fakes import (
    FakePreLaunchGuard,
    FakeWorkflowCompletionEvaluator,
    RecordingStepRunner,
    run_until_decisive,
)

R = WorkflowResponsibility
NOW = Instant(datetime(2026, 8, 26, 9, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 26, 9, 1, tzinfo=UTC))

_REQUIRED = {
    WorkflowKind.WF_2: (R.GENERATE_TRANSFORM,),
    WorkflowKind.WF_4: (R.EVIDENCE, R.GENERATE_TRANSFORM),
    WorkflowKind.WF_5: (R.GENERATE_TRANSFORM, R.REVIEW),
    WorkflowKind.WF_6: (
        R.EVIDENCE,
        R.GENERATE_TRANSFORM,
        R.DETERMINISTIC_VALIDATION,
        R.REVIEW,
    ),
    WorkflowKind.WF_7: (R.CORRECTION,),
    WorkflowKind.WF_9: (
        R.VARIANT_GENERATION,
        R.VARIANT_JOIN,
        R.VARIANT_SELECTION,
    ),
}


def _capability(
    responsibility: R,
    generation_capability: str,
) -> str | None:
    return {
        R.EVIDENCE: "CAP-E01",
        R.GENERATE_TRANSFORM: generation_capability,
        R.DETERMINISTIC_VALIDATION: "CAP-A01",
        R.REVIEW: "CAP-V01",
        R.CORRECTION: "CAP-G03",
        R.VARIANT_GENERATION: "CAP-G01",
        R.VARIANT_JOIN: None,
        R.VARIANT_SELECTION: None,
    }[responsibility]


def _binding(
    stage_index: int,
    responsibility: R,
    generation_capability: str,
    *,
    suffix: str = "0",
    branch_index: int | None = None,
) -> PlanStepBinding:
    capability = _capability(responsibility, generation_capability)
    executable = responsibility not in {R.VARIANT_JOIN, R.VARIANT_SELECTION}
    return PlanStepBinding(
        stage_index=stage_index,
        responsibility=responsibility,
        step_id=f"s{stage_index}-{responsibility.value.lower()}-{suffix}",
        objective=f"Test-only {responsibility.value}",
        capability_id=CapabilityId(capability) if capability else None,
        permission_scope_ref="opaque-scope-ref" if executable else None,
        output_contract={"type": "opaque-result-ref"},
        branch_index=branch_index,
    )


def _bindings(
    selection,
    generation_capability: str,
    *,
    variants: int,
) -> tuple[PlanStepBinding, ...]:
    values: list[PlanStepBinding] = []
    for stage_index, stage in enumerate(selection.stages):
        responsibilities = list(_REQUIRED[stage.workflow_kind])
        responsibilities.extend(stage.materialized_optional_responsibilities)
        for responsibility in responsibilities:
            if responsibility is R.VARIANT_GENERATION:
                values.extend(
                    _binding(
                        stage_index,
                        responsibility,
                        generation_capability,
                        suffix=str(index),
                        branch_index=index,
                    )
                    for index in range(variants)
                )
            else:
                values.append(
                    _binding(stage_index, responsibility, generation_capability)
                )
    return tuple(values)


def _compile(
    requirements: WorkflowRequirements,
    *,
    generation_capability: str = "CAP-G01",
    variants: int = 1,
    plan_version: int = 1,
) -> tuple[object, Plan]:
    selection = WorkflowSelector().select(requirements)
    plan = PlanCompiler().compile(
        PlanCompilationRequest(
            selection=selection,
            plan_id=f"phase-12-8-g-plan-{plan_version}",
            run_id=f"phase-12-8-g-run-{plan_version}",
            plan_version=plan_version,
            objective="Prove topology compatibility without capability dispatch",
            success_criteria={"fake_completion": True},
            stop_conditions={"failure": "stop"},
            bindings=_bindings(
                selection,
                generation_capability,
                variants=variants,
            ),
            gate_refs=("opaque-gate-ref",),
        )
    )
    return selection, plan


def _evaluator() -> FakeWorkflowCompletionEvaluator:
    return FakeWorkflowCompletionEvaluator(
        WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "FAKE_COMPLETE")
    )


def _run(plan: Plan, runner: RecordingStepRunner):
    return run_until_decisive(
        plan=plan,
        run_state=initialize_run_state(
            plan,
            CorrelationId(f"corr-{plan.plan_id}-{plan.plan_version}"),
        ),
        now=NOW,
        guard=FakePreLaunchGuard(),
        runner=runner,
        completion_evaluator=_evaluator(),
    )


def _production_request(
    step_id: str,
    *,
    evidence_refs: tuple[str, ...] = ("evidence:one",),
    brief: str = "Generate a bounded variant.",
) -> ProductionRequest:
    return ProductionRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-real-generation-g",
            step_id,
            None,
            CorrelationId("corr-real-generation-g"),
            NOW,
            ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            InvocationStatus.PLANNED,
        ),
        production_kind="lesson_plan",
        brief=brief,
        output_format="markdown",
        pedagogical_context={"audience": "beginner"},
        constraints={"duration_minutes": 30},
        evidence_refs=evidence_refs,
        expected_sections=("Objectives",),
    )


def _candidate_meta(
    request: ProductionRequest,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        request.meta.run_id,
        request.meta.step_id,
        None,
        request.meta.correlation_id,
        LATER,
        ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        AgentResultStatus.SUCCEEDED,
    )


def _execute_real_candidates(
    count: int,
    *,
    blocked_index: int | None = None,
) -> tuple[
    tuple[ProductionCandidate, ...],
    RecordingGenerationPort,
    ScenarioArtifacts,
]:
    requests = tuple(
        _production_request(
            f"variant-step-{index}",
            brief=f"Generate explicit variant {index}.",
        )
        for index in range(count)
    )
    results = {
        request.meta.step_id: GenerationPortResult(
            request.meta.step_id,
            GenerationOperation.GENERATE,
            GenerationPortResultStatus.SUCCEEDED,
            content=f"Distinct variant content {index}.",
            structured_payload=(
                {}
                if blocked_index == index
                else {"sections": {"Objectives": f"Variant {index}"}}
            ),
            evidence_refs_used=("evidence:one",),
        )
        for index, request in enumerate(requests)
    }
    port = RecordingGenerationPort(results)
    agent = GeneratorAgent(GenerationCoordinator(port))
    artifacts = ScenarioArtifacts()
    candidates: list[ProductionCandidate] = []
    for index, request in enumerate(requests):
        prepared, technical = agent.generate_production(
            request=GenerationPreparationRequest(
                CapabilityId("CAP-G01"),
                request,
                resolved_inputs={"variant_index": index},
                output_contract={"type": "lesson_plan"},
            )
        )
        policy = (
            GenerationGuardPolicy(section_container_key="sections")
            if blocked_index == index
            else GenerationGuardPolicy(grounding_required=True)
        )
        attributions = (
            ()
            if blocked_index == index
            else (
                GenerationClaimAttribution(
                    f"claim:variant:{index}",
                    GenerationClaimClass.GROUNDED,
                    ("evidence:one",),
                ),
            )
        )
        assessment = GenerationOutputGuard().assess(
            request=GenerationGuardRequest(
                prepared,
                technical,
                policy,
                attributions,
            )
        )
        if blocked_index == index:
            assert assessment.disposition is GenerationGuardDisposition.REPAIR_REQUIRED
            with pytest.raises(GenerationCandidateMaterializationError):
                ProductionCandidateBuildRequest(
                    request,
                    prepared,
                    technical,
                    assessment,
                    _candidate_meta(request),
                    f"variant-candidate-{index}",
                )
            continue
        candidate = agent.build_candidate(
            request=ProductionCandidateBuildRequest(
                request,
                prepared,
                technical,
                assessment,
                _candidate_meta(request),
                f"variant-candidate-{index}",
            )
        )
        candidates.append(candidate)
        artifacts.publish(f"variant-ref-{index}", candidate)
    return tuple(candidates), port, artifacts


def _version(version: str) -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "wf7-lesson")),
        VersionRef(version),
    )


@pytest.mark.parametrize("capability", ("CAP-G01", "CAP-G02"))
def test_wf2_accepts_exactly_one_ag03_generation_or_transformation_step(
    capability: str,
) -> None:
    selection, plan = _compile(
        WorkflowRequirements(production_required=True),
        generation_capability=capability,
    )
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_2,
    )
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.kind is StepKind.AGENT
    assert step.executor.kind is ExecutorKind.AG_03
    assert step.capability_id == CapabilityId(capability)
    assert step.permission_scope_ref == "opaque-scope-ref"
    assert all(
        item.executor.kind
        not in {ExecutorKind.AG_02, ExecutorKind.AG_04, ExecutorKind.APPLICATION}
        for item in plan.steps
    )


def test_wf2_optional_validation_is_application_cap_a01_only() -> None:
    _, plan = _compile(
        WorkflowRequirements(
            production_required=True,
            deterministic_validation_required=True,
        )
    )
    assert tuple(step.executor.kind for step in plan.steps) == (
        ExecutorKind.AG_03,
        ExecutorKind.APPLICATION,
    )
    assert tuple(step.capability_id for step in plan.steps) == (
        CapabilityId("CAP-G01"),
        CapabilityId("CAP-A01"),
    )
    assert all(step.capability_id != CapabilityId("CAP-A02") for step in plan.steps)


def test_wf4_evidence_handoff_is_explicit_and_generation_remains_bounded() -> None:
    _, plan = _compile(
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
        )
    )
    evidence_step, generation_step = plan.steps
    evidence_set = EvidenceSet(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-evidence-g",
            evidence_step.step_id,
            None,
            CorrelationId("corr-evidence-g"),
            NOW,
            ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
            AgentResultStatus.SUCCEEDED,
        ),
        evidence_items=(
            EvidenceItem(
                evidence_id="evidence:caller-prepared",
                source_ref="source:wf4",
                source_kind="canonical_document",
                locator="document:wf4",
                retrieved_at=NOW,
                relevance={"rank": 1},
                authority={"kind": "canonical"},
                excerpt_or_summary="Bounded evidence summary.",
                checksum_or_version="v1",
            ),
        ),
        coverage={"status": "COVERED"},
    )
    artifacts = ScenarioArtifacts()
    artifacts.publish("evidence-set-ref", evidence_set)
    runner = RecordingStepRunner(
        {
            evidence_step.step_id: StepExecutionResult(
                StepRuntimeStatus.SUCCEEDED,
                ("evidence-set-ref",),
            ),
            generation_step.step_id: StepExecutionResult(
                StepRuntimeStatus.SUCCEEDED,
                ("candidate-ref",),
            ),
        }
    )
    _run(plan, runner)

    canonical = _production_request(
        generation_step.step_id,
        evidence_refs=(evidence_set.evidence_items[0].evidence_id,),
    )
    technical = GenerationPortResult(
        canonical.meta.step_id,
        GenerationOperation.GENERATE,
        GenerationPortResultStatus.SUCCEEDED,
        content="Evidence-bounded output.",
        evidence_refs_used=("evidence:caller-prepared",),
    )
    port = RecordingGenerationPort({canonical.meta.step_id: technical})
    agent = GeneratorAgent(GenerationCoordinator(port))
    prepared, result = agent.generate_production(
        request=GenerationPreparationRequest(CapabilityId("CAP-G01"), canonical)
    )
    guard = GenerationOutputGuard().assess(
        request=GenerationGuardRequest(
            prepared,
            result,
            GenerationGuardPolicy(grounding_required=True),
            (
                GenerationClaimAttribution(
                    "claim:wf4",
                    GenerationClaimClass.GROUNDED,
                    ("evidence:caller-prepared",),
                ),
            ),
        )
    )
    candidate = agent.build_candidate(
        request=ProductionCandidateBuildRequest(
            canonical,
            prepared,
            result,
            guard,
            _candidate_meta(canonical),
            "candidate:wf4",
        )
    )

    assert tuple(step.executor.kind for step in plan.steps) == (
        ExecutorKind.AG_02,
        ExecutorKind.AG_03,
    )
    assert generation_step.depends_on == (evidence_step.step_id,)
    assert tuple(step_id for step_id, _ in runner.calls) == (
        evidence_step.step_id,
        generation_step.step_id,
    )
    assert artifacts.resolve("evidence-set-ref") is evidence_set
    assert candidate.evidence_refs_used == ("evidence:caller-prepared",)
    assert port.calls == [prepared.port_request]


def test_wf5_generation_precedes_fake_review_with_optional_validation() -> None:
    cases = (
        (
            WorkflowRequirements(
                production_required=True,
                independent_review_required=True,
            ),
            (ExecutorKind.AG_03, ExecutorKind.AG_04),
            ("CAP-G01", "CAP-V01"),
        ),
        (
            WorkflowRequirements(
                production_required=True,
                deterministic_validation_required=True,
                independent_review_required=True,
            ),
            (ExecutorKind.AG_03, ExecutorKind.APPLICATION, ExecutorKind.AG_04),
            ("CAP-G01", "CAP-A01", "CAP-V01"),
        ),
    )
    for requirements, executors, capabilities in cases:
        _, plan = _compile(requirements)
        assert tuple(step.executor.kind for step in plan.steps) == executors
        assert tuple(
            step.capability_id.value if step.capability_id else None
            for step in plan.steps
        ) == capabilities
        assert tuple(step.depends_on for step in plan.steps[1:]) == tuple(
            (step.step_id,) for step in plan.steps[:-1]
        )


def test_wf6_executes_exact_evidence_generation_validation_review_chain() -> None:
    _, plan = _compile(
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
            deterministic_validation_required=True,
            independent_review_required=True,
        )
    )
    assert tuple(step.executor.kind for step in plan.steps) == (
        ExecutorKind.AG_02,
        ExecutorKind.AG_03,
        ExecutorKind.APPLICATION,
        ExecutorKind.AG_04,
    )
    assert tuple(step.capability_id for step in plan.steps) == (
        CapabilityId("CAP-E01"),
        CapabilityId("CAP-G01"),
        CapabilityId("CAP-A01"),
        CapabilityId("CAP-V01"),
    )
    assert all(step.capability_id != CapabilityId("CAP-A02") for step in plan.steps)
    runner = RecordingStepRunner()
    results = _run(plan, runner)
    assert tuple(step_id for step_id, _ in runner.calls) == tuple(
        step.step_id for step in plan.steps
    )
    assert results[-1].decision.action is CoordinationAction.COMPLETE
    assert results[-1].decision.run_state.status is WorkflowStatus.SUCCEEDED


def test_wf7_correction_is_cap_g03_and_optional_review_is_downstream() -> None:
    _, correction_only = _compile(WorkflowRequirements(correction_required=True))
    assert len(correction_only.steps) == 1
    assert correction_only.steps[0].capability_id == CapabilityId("CAP-G03")
    assert correction_only.steps[0].executor.kind is ExecutorKind.AG_03
    assert all(
        step.capability_id not in {CapabilityId("CAP-G01"), CapabilityId("CAP-G02")}
        for step in correction_only.steps
    )

    _, with_review = _compile(
        WorkflowRequirements(
            correction_required=True,
            independent_review_required=True,
        )
    )
    correction, review = with_review.steps
    assert review.executor.kind is ExecutorKind.AG_04
    assert review.capability_id == CapabilityId("CAP-V01")
    assert review.depends_on == (correction.step_id,)


def test_wf7_second_correction_is_a_new_plan_version_not_a_local_loop() -> None:
    _, plan_v1 = _compile(
        WorkflowRequirements(correction_required=True),
        plan_version=1,
    )
    _run(plan_v1, RecordingStepRunner())
    request_v1 = CorrectionRequest(
        ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-wf7",
            plan_v1.steps[0].step_id,
            None,
            CorrelationId("corr-wf7"),
            NOW,
            ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            InvocationStatus.PLANNED,
        ),
        _version("v1"),
        "review:wf7:v1",
        ("finding-v1",),
    )
    candidate_v2 = ProductionCandidate(
        _candidate_meta(_production_request("candidate-wf7-v2")),
        "candidate-wf7-v2",
        "lesson_plan",
        content="Corrected v2.",
        lineage={"parent_production_ref": _version("v1")},
    )
    result_v2 = CorrectionResult(
        ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            request_v1.meta.run_id,
            request_v1.meta.step_id,
            None,
            request_v1.meta.correlation_id,
            LATER,
            ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            AgentResultStatus.SUCCEEDED,
        ),
        request_v1,
        _version("v2"),
        _version("v1"),
        ("finding-v1",),
        (),
        "Produced v2.",
        {"capability_id": "CAP-G03"},
    )
    request_v2 = CorrectionRequest(
        ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-wf7-v2",
            "correction-v2-step",
            None,
            CorrelationId("corr-wf7-v2"),
            NOW,
            ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            InvocationStatus.PLANNED,
        ),
        result_v2.new_production_ref,
        "review:wf7:v2",
        ("finding-v2",),
    )
    _, plan_v2 = _compile(
        WorkflowRequirements(correction_required=True),
        plan_version=2,
    )
    _run(plan_v2, RecordingStepRunner())

    assert candidate_v2.validation_state is ProductionValidationState.CANDIDATE
    assert request_v2.target_production_ref == _version("v2")
    assert plan_v1.plan_version == 1 and plan_v2.plan_version == 2
    assert plan_v1.plan_id != plan_v2.plan_id
    assert len(plan_v1.steps) == len(plan_v2.steps) == 1
    assert plan_v1.steps[0].capability_id == plan_v2.steps[0].capability_id == CapabilityId("CAP-G03")


def test_wf9_five_variants_schedule_as_four_plus_one_join_then_selection() -> None:
    selection, plan = _compile(
        WorkflowRequirements(
            production_required=True,
            variant_count=5,
            variants_explicitly_useful=True,
        ),
        variants=5,
    )
    bindings = tuple(
        binding
        for binding in _bindings(selection, "CAP-G01", variants=5)
        if binding.responsibility is R.VARIANT_GENERATION
    )
    variants = tuple(
        step for step in plan.steps if step.executor.kind is ExecutorKind.AG_03
    )
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    decision = next(step for step in plan.steps if step.kind is StepKind.DECISION)
    assert len(variants) == 5
    assert tuple(binding.branch_index for binding in bindings) == tuple(range(5))
    assert len({step.parallel_group for step in variants}) == 1
    assert variants[0].parallel_group is not None
    assert join.executor.kind is ExecutorKind.RUNTIME
    assert join.capability_id == CapabilityId("CAP-O04")
    assert join.depends_on == tuple(step.step_id for step in variants)
    assert decision.executor.kind is ExecutorKind.RUNTIME
    assert decision.capability_id is None
    assert decision.depends_on == (join.step_id,)

    runner = RecordingStepRunner()
    executor = PlanExecutor(DeterministicScheduler(), FakePreLaunchGuard(), runner)
    initial = initialize_run_state(plan, CorrelationId("corr-wf9-five"))
    first = executor.execute_cycle(plan=plan, run_state=initial, now=NOW)
    second = executor.execute_cycle(plan=plan, run_state=first.run_state, now=NOW)
    third = executor.execute_cycle(plan=plan, run_state=second.run_state, now=NOW)
    fourth = executor.execute_cycle(plan=plan, run_state=third.run_state, now=NOW)
    assert len(first.launched_step_ids) == 4
    assert len(second.launched_step_ids) == 1
    assert third.launched_step_ids == (join.step_id,)
    assert fourth.launched_step_ids == (decision.step_id,)


def test_wf9_five_real_variants_are_distinct_candidates_and_selection_is_opaque() -> None:
    candidates, port, artifacts = _execute_real_candidates(5)
    join_summary = {
        "variant_refs": artifacts.references(),
        "production_ids": tuple(item.production_id for item in candidates),
    }
    selected_ref = "variant-ref-2"

    assert len(candidates) == 5
    assert len(port.calls) == 5
    assert len({item.production_id for item in candidates}) == 5
    assert len({item.content for item in candidates}) == 5
    assert all(
        item.validation_state is ProductionValidationState.CANDIDATE
        for item in candidates
    )
    assert join_summary == {
        "variant_refs": tuple(f"variant-ref-{index}" for index in range(5)),
        "production_ids": tuple(
            f"variant-candidate-{index}" for index in range(5)
        ),
    }
    assert artifacts.resolve(selected_ref) is candidates[2]
    assert candidates[2].validation_state is ProductionValidationState.CANDIDATE
    assert "truth_score" not in join_summary


def test_wf9_blocked_variant_is_not_published_and_requires_future_policy() -> None:
    candidates, port, artifacts = _execute_real_candidates(5, blocked_index=4)
    assert len(port.calls) == 5
    assert len(candidates) == 4
    assert artifacts.references() == tuple(
        f"variant-ref-{index}" for index in range(4)
    )
    with pytest.raises(KeyError):
        artifacts.resolve("variant-ref-4")
