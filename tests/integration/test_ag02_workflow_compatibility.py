from __future__ import annotations

from datetime import UTC, datetime

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    EvidenceRequest,
    EvidenceSet,
    ExecutorKind,
    InvocationStatus,
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
from backend.shared_kernel.time import Instant
from tests.support.orchestration_fakes import (
    FakePreLaunchGuard,
    FakeWorkflowCompletionEvaluator,
    RecordingStepRunner,
    run_until_decisive,
)

R = WorkflowResponsibility
NOW = Instant(datetime(2026, 8, 25, 17, 0, tzinfo=UTC))

_CAPABILITY = {
    R.EVIDENCE: "CAP-E01",
    R.GENERATE_TRANSFORM: "CAP-G01",
    R.DETERMINISTIC_VALIDATION: "CAP-A01",
    R.REVIEW: "CAP-V01",
    R.EVIDENCE_JOIN: None,
}
_REQUIRED = {
    WorkflowKind.WF_1: (R.EVIDENCE,),
    WorkflowKind.WF_4: (R.EVIDENCE, R.GENERATE_TRANSFORM),
    WorkflowKind.WF_6: (
        R.EVIDENCE,
        R.GENERATE_TRANSFORM,
        R.DETERMINISTIC_VALIDATION,
        R.REVIEW,
    ),
    WorkflowKind.WF_8: (R.EVIDENCE, R.EVIDENCE_JOIN),
}


def _binding(
    stage_index: int,
    responsibility: R,
    *,
    suffix: str = "0",
    branch_index: int | None = None,
) -> PlanStepBinding:
    capability = _CAPABILITY[responsibility]
    executable = responsibility is not R.EVIDENCE_JOIN
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


def _bindings(selection, branches: int) -> tuple[PlanStepBinding, ...]:
    values: list[PlanStepBinding] = []
    for stage_index, stage in enumerate(selection.stages):
        responsibilities = list(_REQUIRED[stage.workflow_kind])
        responsibilities.extend(stage.materialized_optional_responsibilities)
        if (
            stage_index > 0
            and selection.stages[stage_index - 1].workflow_kind is WorkflowKind.WF_8
            and stage.workflow_kind in {WorkflowKind.WF_4, WorkflowKind.WF_6}
        ):
            responsibilities.remove(R.EVIDENCE)
        for responsibility in responsibilities:
            if stage.workflow_kind is WorkflowKind.WF_8 and responsibility is R.EVIDENCE:
                values.extend(
                    _binding(
                        stage_index,
                        responsibility,
                        suffix=str(index),
                        branch_index=index,
                    )
                    for index in range(branches)
                )
            else:
                values.append(_binding(stage_index, responsibility))
    return tuple(values)


def _compile(requirements: WorkflowRequirements, *, branches: int = 1) -> Plan:
    selection = WorkflowSelector().select(requirements)
    return PlanCompiler().compile(
        PlanCompilationRequest(
            selection=selection,
            plan_id="phase-12-7-f-plan",
            run_id="phase-12-7-f-run",
            plan_version=1,
            objective="Prove declarative workflow compatibility",
            success_criteria={"fake_completion": True},
            stop_conditions={"failure": "stop"},
            bindings=_bindings(selection, branches),
            gate_refs=("opaque-gate-ref",),
        )
    )


def _success_evaluator() -> FakeWorkflowCompletionEvaluator:
    return FakeWorkflowCompletionEvaluator(
        WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "FAKE_COMPLETE")
    )


def _run(plan: Plan, runner: RecordingStepRunner):
    return run_until_decisive(
        plan=plan,
        run_state=initialize_run_state(plan, CorrelationId("corr-workflow-f")),
        now=NOW,
        guard=FakePreLaunchGuard(),
        runner=runner,
        completion_evaluator=_success_evaluator(),
    )


def test_wf1_topology_runs_one_opaque_evidence_step_with_fake_completion() -> None:
    plan = _compile(WorkflowRequirements(external_evidence_required=True))
    assert plan.workflow_kind == "WF-1"
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.executor.kind is ExecutorKind.AG_02
    assert step.capability_id == CapabilityId("CAP-E01")
    assert step.permission_scope_ref == "opaque-scope-ref"
    assert step.kind is StepKind.AGENT

    runner = RecordingStepRunner()
    results = _run(plan, runner)
    assert runner.calls == [(step.step_id, 1)]
    assert results[-1].decision.action is CoordinationAction.COMPLETE
    assert results[-1].decision.run_state.status is WorkflowStatus.SUCCEEDED


def test_wf4_handoff_uses_only_ag02_then_fake_ag03() -> None:
    plan = _compile(
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
        )
    )
    evidence, generation = plan.steps
    evidence_set = EvidenceSet(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="real-evidence-run",
            step_id="real-evidence-step",
            parent_step_id=None,
            correlation_id=CorrelationId("real-evidence-corr"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
            status=AgentResultStatus.SUCCEEDED,
        ),
        evidence_items=(),
        coverage={"status": "EMPTY"},
    )
    artifact_by_ref = {"evidence-set-ref": evidence_set}
    runner = RecordingStepRunner(
        {
            evidence.step_id: StepExecutionResult(
                StepRuntimeStatus.SUCCEEDED,
                ("evidence-set-ref",),
            ),
            generation.step_id: StepExecutionResult(
                StepRuntimeStatus.SUCCEEDED,
                ("fake-production-ref",),
            ),
        }
    )
    _run(plan, runner)

    assert tuple(step.executor.kind for step in plan.steps) == (ExecutorKind.AG_02, ExecutorKind.AG_03)
    assert tuple(step.capability_id for step in plan.steps) == (CapabilityId("CAP-E01"), CapabilityId("CAP-G01"))
    assert generation.depends_on == (evidence.step_id,)
    assert artifact_by_ref["evidence-set-ref"] is evidence_set
    assert tuple(step_id for step_id, _ in runner.calls) == (evidence.step_id, generation.step_id)
    assert all(step.executor.kind not in {ExecutorKind.AG_04, ExecutorKind.APPLICATION} for step in plan.steps)


def test_wf6_exact_chain_has_no_promotion_or_unrequested_application_step() -> None:
    plan = _compile(
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
    assert tuple(step.depends_on for step in plan.steps[1:]) == tuple(
        (step.step_id,) for step in plan.steps[:-1]
    )

    runner = RecordingStepRunner()
    _run(plan, runner)
    assert tuple(step_id for step_id, _ in runner.calls) == tuple(step.step_id for step in plan.steps)


def test_wf8_five_branches_are_contiguous_grouped_and_joined_after_four_plus_one() -> None:
    requirements = WorkflowRequirements(
        external_evidence_required=True,
        parallel_evidence_branches=5,
        parallel_evidence_independent=True,
    )
    selection = WorkflowSelector().select(requirements)
    branch_bindings = tuple(
        binding
        for binding in _bindings(selection, 5)
        if binding.responsibility is R.EVIDENCE
    )
    plan = _compile(requirements, branches=5)
    evidence = tuple(step for step in plan.steps if step.executor.kind is ExecutorKind.AG_02)
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    assert len(evidence) == 5
    assert tuple(binding.branch_index for binding in branch_bindings) == tuple(range(5))
    assert len({step.parallel_group for step in evidence}) == 1
    assert evidence[0].parallel_group is not None
    assert join.capability_id == CapabilityId("CAP-O04")
    assert join.depends_on == tuple(step.step_id for step in evidence)

    runner = RecordingStepRunner()
    executor = PlanExecutor(DeterministicScheduler(), FakePreLaunchGuard(), runner)
    initial = initialize_run_state(plan, CorrelationId("corr-wf8-five"))
    first = executor.execute_cycle(plan=plan, run_state=initial, now=NOW)
    second = executor.execute_cycle(plan=plan, run_state=first.run_state, now=NOW)
    third = executor.execute_cycle(plan=plan, run_state=second.run_state, now=NOW)
    assert len(first.launched_step_ids) == 4
    assert len(second.launched_step_ids) == 1
    assert third.launched_step_ids == (join.step_id,)
    assert tuple(step_id for step_id, _ in runner.calls[:5]) == tuple(step.step_id for step in evidence)


def test_wf8_to_wf4_continuation_starts_after_join_without_extra_ag02() -> None:
    plan = _compile(
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
            parallel_evidence_branches=5,
            parallel_evidence_independent=True,
        ),
        branches=5,
    )
    evidence = tuple(step for step in plan.steps if step.executor.kind is ExecutorKind.AG_02)
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    generation = next(step for step in plan.steps if step.executor.kind is ExecutorKind.AG_03)
    assert len(evidence) == 5
    assert generation.depends_on == (join.step_id,)
    assert sum(step.capability_id == CapabilityId("CAP-E01") for step in plan.steps) == 5
    assert tuple(step.executor.kind for step in plan.steps[-2:]) == (ExecutorKind.RUNTIME, ExecutorKind.AG_03)


def test_wf8_to_wf6_continuation_begins_only_after_join() -> None:
    plan = _compile(
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
            deterministic_validation_required=True,
            independent_review_required=True,
            parallel_evidence_branches=5,
            parallel_evidence_independent=True,
        ),
        branches=5,
    )
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    continuation = tuple(step for step in plan.steps if step.executor.kind in {ExecutorKind.AG_03, ExecutorKind.APPLICATION, ExecutorKind.AG_04})
    assert tuple(step.executor.kind for step in continuation) == (ExecutorKind.AG_03, ExecutorKind.APPLICATION, ExecutorKind.AG_04)
    assert continuation[0].depends_on == (join.step_id,)
    assert tuple(step.capability_id for step in continuation) == (CapabilityId("CAP-G01"), CapabilityId("CAP-A01"), CapabilityId("CAP-V01"))
    assert sum(step.executor.kind is ExecutorKind.AG_02 for step in plan.steps) == 5


def test_three_search_rag_branches_keep_distinct_requests_outputs_and_join_refs() -> None:
    plan = _compile(
        WorkflowRequirements(
            external_evidence_required=True,
            parallel_evidence_branches=3,
            parallel_evidence_independent=True,
        ),
        branches=3,
    )
    evidence = tuple(step for step in plan.steps if step.executor.kind is ExecutorKind.AG_02)
    requests = tuple(
        EvidenceRequest(
            meta=ContractMeta(
                schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                run_id="multi-rag-run",
                step_id=step.step_id,
                parent_step_id=None,
                correlation_id=CorrelationId("multi-rag-corr"),
                created_at=NOW,
                actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
                status=InvocationStatus.PLANNED,
            ),
            search_goal=f"Independent evidence question {index}",
            scope={"branch": index},
            source_policy={"kinds": ("canonical",)},
            filters={"active": True},
            max_items=3,
        )
        for index, step in enumerate(evidence)
    )
    result_refs = tuple(f"evidence-set-branch-{index}" for index in range(3))
    join_summary = {reference: f"summary for {request.search_goal}" for reference, request in zip(result_refs, requests, strict=True)}
    runner = RecordingStepRunner(
        {
            step.step_id: StepExecutionResult(StepRuntimeStatus.SUCCEEDED, (reference,))
            for step, reference in zip(evidence, result_refs, strict=True)
        }
    )
    _run(plan, runner)

    assert len({request.meta.step_id for request in requests}) == 3
    assert len({request.search_goal for request in requests}) == 3
    assert all(step.capability_id == CapabilityId("CAP-E01") for step in evidence)
    assert tuple(join_summary) == result_refs
    assert all(isinstance(value, str) for value in join_summary.values())
    assert not any(isinstance(value, EvidenceSet) for value in join_summary.values())
    assert sum(step.executor.kind is ExecutorKind.AG_02 for step in plan.steps) == 3
