from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.contracts import (
    ExecutorKind,
    FailurePolicy,
    StepKind,
    WorkflowStatus,
)
from backend.agent_runtime.orchestration import (
    CompletionDisposition,
    CoordinationAction,
    HumanGateAnchor,
    HumanGateBinding,
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
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    Plan,
    PlanExecutor,
    PreLaunchDisposition,
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
NOW = Instant(datetime(2026, 8, 25, 16, 0, tzinfo=UTC))

_CAPABILITY = {
    R.DIRECT_APPLICATION: "CAP-R01",
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

_REQUIRED = {
    WorkflowKind.WF_0: (R.DIRECT_APPLICATION,),
    WorkflowKind.WF_1: (R.EVIDENCE,),
    WorkflowKind.WF_2: (R.GENERATE_TRANSFORM,),
    WorkflowKind.WF_3: (R.REVIEW,),
    WorkflowKind.WF_4: (R.EVIDENCE, R.GENERATE_TRANSFORM),
    WorkflowKind.WF_5: (R.GENERATE_TRANSFORM, R.REVIEW),
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

_EXECUTABLE_RESPONSIBILITIES = {
    R.DIRECT_APPLICATION,
    R.EVIDENCE,
    R.GENERATE_TRANSFORM,
    R.REVIEW,
    R.DETERMINISTIC_VALIDATION,
    R.CORRECTION,
    R.VARIANT_GENERATION,
    R.PROMOTION,
}


@dataclass(frozen=True, slots=True)
class WorkflowScenario:
    name: str
    requirements: WorkflowRequirements
    expected_stages: tuple[WorkflowKind, ...]


SCENARIOS = (
    WorkflowScenario(
        "WF-0",
        WorkflowRequirements(application_action_required=True),
        (WorkflowKind.WF_0,),
    ),
    WorkflowScenario(
        "WF-1",
        WorkflowRequirements(external_evidence_required=True),
        (WorkflowKind.WF_1,),
    ),
    WorkflowScenario(
        "WF-2",
        WorkflowRequirements(production_required=True),
        (WorkflowKind.WF_2,),
    ),
    WorkflowScenario(
        "WF-3",
        WorkflowRequirements(independent_review_required=True),
        (WorkflowKind.WF_3,),
    ),
    WorkflowScenario(
        "WF-4",
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
        ),
        (WorkflowKind.WF_4,),
    ),
    WorkflowScenario(
        "WF-5",
        WorkflowRequirements(
            production_required=True,
            independent_review_required=True,
        ),
        (WorkflowKind.WF_5,),
    ),
    WorkflowScenario(
        "WF-6",
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
            independent_review_required=True,
        ),
        (WorkflowKind.WF_6,),
    ),
    WorkflowScenario(
        "WF-7",
        WorkflowRequirements(
            correction_required=True,
            independent_review_required=True,
        ),
        (WorkflowKind.WF_7,),
    ),
    WorkflowScenario(
        "WF-8",
        WorkflowRequirements(
            external_evidence_required=True,
            parallel_evidence_branches=2,
            parallel_evidence_independent=True,
        ),
        (WorkflowKind.WF_8,),
    ),
    WorkflowScenario(
        "WF-9",
        WorkflowRequirements(
            production_required=True,
            variant_count=2,
            variants_explicitly_useful=True,
        ),
        (WorkflowKind.WF_9,),
    ),
    WorkflowScenario(
        "WF-10",
        WorkflowRequirements(
            production_required=True,
            human_gate_required=True,
        ),
        (WorkflowKind.WF_2,),
    ),
    WorkflowScenario(
        "WF-11",
        WorkflowRequirements(promotion_required=True),
        (WorkflowKind.WF_11,),
    ),
)


def _binding(
    stage_index: int,
    responsibility: R,
    suffix: str = "0",
    *,
    branch_index: int | None = None,
) -> PlanStepBinding:
    capability = _CAPABILITY[responsibility]
    return PlanStepBinding(
        stage_index=stage_index,
        responsibility=responsibility,
        step_id=f"s{stage_index}-{responsibility.value.lower()}-{suffix}",
        objective=f"Materialize {responsibility.value}",
        capability_id=CapabilityId(capability) if capability is not None else None,
        permission_scope_ref=(
            "scope-test"
            if responsibility in _EXECUTABLE_RESPONSIBILITIES
            else None
        ),
        output_contract={"type": "result"},
        branch_index=branch_index,
    )


def _bindings_for(
    selection: WorkflowSelectionDecision,
    *,
    branches: int = 2,
    wf0_operations: int = 1,
) -> tuple[PlanStepBinding, ...]:
    bindings: list[PlanStepBinding] = []
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
            if stage.workflow_kind is WorkflowKind.WF_0:
                bindings.extend(
                    _binding(stage_index, responsibility, str(operation))
                    for operation in range(wf0_operations)
                )
            elif responsibility in {R.EVIDENCE, R.VARIANT_GENERATION} and (
                stage.workflow_kind in {WorkflowKind.WF_8, WorkflowKind.WF_9}
            ):
                bindings.extend(
                    _binding(
                        stage_index,
                        responsibility,
                        str(branch_index),
                        branch_index=branch_index,
                    )
                    for branch_index in range(branches)
                )
            else:
                bindings.append(_binding(stage_index, responsibility))
    return tuple(bindings)


def _human_gate(anchor: HumanGateAnchor) -> HumanGateBinding:
    return HumanGateBinding(
        step_id="human-gate",
        objective="Obtain an explicit human decision",
        anchor=anchor,
        success_criteria={"decision": "recorded"},
        failure_policy=FailurePolicy.STOP,
        output_contract={"type": "gate-result"},
    )


def _compile(
    requirements: WorkflowRequirements,
    *,
    branches: int = 2,
    human_anchor: HumanGateAnchor | None = None,
    wf0_operations: int = 1,
) -> tuple[WorkflowSelectionDecision, Plan]:
    selection = WorkflowSelector().select(requirements)
    gate = _human_gate(human_anchor) if human_anchor is not None else None
    request = PlanCompilationRequest(
        selection=selection,
        plan_id="plan-canonical",
        run_id="run-canonical",
        plan_version=1,
        objective="Execute a canonical workflow scenario",
        success_criteria={"complete": True},
        stop_conditions={"failure": "stop"},
        bindings=_bindings_for(
            selection,
            branches=branches,
            wf0_operations=wf0_operations,
        ),
        human_gate=gate,
        gate_refs=("gate-ref-test",),
    )
    return selection, PlanCompiler().compile(request)


def _succeeded_evaluator() -> FakeWorkflowCompletionEvaluator:
    return FakeWorkflowCompletionEvaluator(
        WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "FAKE_COMPLETE")
    )


def _step_for_capability(plan: Plan, capability: str):
    return next(
        step for step in plan.steps if step.capability_id == CapabilityId(capability)
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item.name)
def test_selector_and_compiler_cover_the_canonical_workflow_matrix(
    scenario: WorkflowScenario,
) -> None:
    selection, plan = _compile(
        scenario.requirements,
        human_anchor=(
            HumanGateAnchor.BEFORE_FIRST_STAGE
            if scenario.name == "WF-10"
            else None
        ),
    )
    assert tuple(stage.workflow_kind for stage in selection.stages) == scenario.expected_stages
    assert WorkflowKind.WF_10 not in tuple(
        stage.workflow_kind for stage in selection.stages
    )
    if scenario.name == "WF-10":
        assert selection.overlays == (WorkflowKind.WF_10,)
        assert plan.workflow_kind == "WF-2|overlay:WF-10"
    else:
        assert selection.overlays == ()
        assert plan.workflow_kind == "+".join(item.value for item in scenario.expected_stages)


@pytest.mark.parametrize(
    ("requirements", "allowed_executors"),
    [
        (
            WorkflowRequirements(application_action_required=True),
            {ExecutorKind.APPLICATION},
        ),
        (
            WorkflowRequirements(external_evidence_required=True),
            {ExecutorKind.AG_02},
        ),
        (
            WorkflowRequirements(production_required=True),
            {ExecutorKind.AG_03},
        ),
        (
            WorkflowRequirements(independent_review_required=True),
            {ExecutorKind.AG_04},
        ),
    ],
)
def test_wf0_to_wf3_use_only_the_required_execution_authority(
    requirements: WorkflowRequirements,
    allowed_executors: set[ExecutorKind],
) -> None:
    _, plan = _compile(requirements, wf0_operations=2)
    assert {step.executor.kind for step in plan.steps} == allowed_executors
    if allowed_executors == {ExecutorKind.APPLICATION}:
        assert len(plan.steps) == 2
        assert all(step.kind is StepKind.USE_CASE for step in plan.steps)
    assert all(step.permission_scope_ref == "scope-test" for step in plan.steps)

    runner = RecordingStepRunner()
    evaluator = _succeeded_evaluator()
    results = run_until_decisive(
        plan=plan,
        run_state=initialize_run_state(plan, CorrelationId("corr-canonical")),
        now=NOW,
        guard=FakePreLaunchGuard(),
        runner=runner,
        completion_evaluator=evaluator,
    )
    assert results[-1].decision.action is CoordinationAction.COMPLETE
    assert results[-1].decision.run_state.status is WorkflowStatus.SUCCEEDED
    assert tuple(step_id for step_id, _ in runner.calls) == tuple(
        step.step_id for step in plan.steps
    )
    assert len(evaluator.calls) == 1


@pytest.mark.parametrize(
    ("requirements", "expected_executors", "expected_capabilities"),
    [
        (
            WorkflowRequirements(
                external_evidence_required=True,
                production_required=True,
            ),
            (ExecutorKind.AG_02, ExecutorKind.AG_03),
            ("CAP-E01", "CAP-G01"),
        ),
        (
            WorkflowRequirements(
                production_required=True,
                independent_review_required=True,
                deterministic_validation_required=True,
            ),
            (ExecutorKind.AG_03, ExecutorKind.APPLICATION, ExecutorKind.AG_04),
            ("CAP-G01", "CAP-A01", "CAP-V01"),
        ),
        (
            WorkflowRequirements(
                external_evidence_required=True,
                production_required=True,
                independent_review_required=True,
            ),
            (
                ExecutorKind.AG_02,
                ExecutorKind.AG_03,
                ExecutorKind.APPLICATION,
                ExecutorKind.AG_04,
            ),
            ("CAP-E01", "CAP-G01", "CAP-A01", "CAP-V01"),
        ),
    ],
)
def test_wf4_wf5_wf6_have_exact_acyclic_execution_order(
    requirements: WorkflowRequirements,
    expected_executors: tuple[ExecutorKind, ...],
    expected_capabilities: tuple[str, ...],
) -> None:
    _, plan = _compile(requirements)
    assert tuple(step.executor.kind for step in plan.steps) == expected_executors
    assert tuple(
        step.capability_id.value if step.capability_id is not None else None
        for step in plan.steps
    ) == expected_capabilities
    for predecessor, successor in zip(plan.steps, plan.steps[1:], strict=False):
        assert successor.depends_on == (predecessor.step_id,)
    assert all(step.capability_id != CapabilityId("CAP-A02") for step in plan.steps)


def test_wf2_and_wf4_materialize_validation_only_when_selected() -> None:
    cases = (
        WorkflowRequirements(production_required=True),
        WorkflowRequirements(
            production_required=True,
            deterministic_validation_required=True,
        ),
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
        ),
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
            deterministic_validation_required=True,
        ),
    )
    plans = tuple(_compile(requirements)[1] for requirements in cases)
    assert [
        sum(step.capability_id == CapabilityId("CAP-A01") for step in plan.steps)
        for plan in plans
    ] == [0, 1, 0, 1]


def test_wf7_is_correction_then_new_optional_review_without_dag_cycle() -> None:
    _, plan = _compile(
        WorkflowRequirements(
            correction_required=True,
            independent_review_required=True,
        )
    )
    correction, review = plan.steps
    assert correction.executor.kind is ExecutorKind.AG_03
    assert correction.capability_id == CapabilityId("CAP-G03")
    assert review.executor.kind is ExecutorKind.AG_04
    assert review.step_id != correction.step_id
    assert review.depends_on == (correction.step_id,)
    assert correction.step_id not in correction.depends_on


@pytest.mark.parametrize(
    ("requirements", "branch_executor"),
    [
        (
            WorkflowRequirements(
                external_evidence_required=True,
                parallel_evidence_branches=5,
                parallel_evidence_independent=True,
            ),
            ExecutorKind.AG_02,
        ),
        (
            WorkflowRequirements(
                production_required=True,
                variant_count=5,
                variants_explicitly_useful=True,
            ),
            ExecutorKind.AG_03,
        ),
    ],
)
def test_wf8_wf9_five_way_fanout_launches_at_most_four_per_cycle(
    requirements: WorkflowRequirements,
    branch_executor: ExecutorKind,
) -> None:
    selection, plan = _compile(requirements, branches=5)
    parallel_responsibility = (
        R.EVIDENCE
        if branch_executor is ExecutorKind.AG_02
        else R.VARIANT_GENERATION
    )
    bindings = tuple(
        binding
        for binding in _bindings_for(selection, branches=5)
        if binding.responsibility is parallel_responsibility
    )
    assert tuple(binding.branch_index for binding in bindings) == tuple(range(5))
    branch_steps = tuple(
        step for step in plan.steps if step.executor.kind is branch_executor
    )
    assert len(branch_steps) == 5
    assert tuple(step.parallel_group for step in branch_steps) == (
        branch_steps[0].parallel_group,
    ) * 5
    assert branch_steps[0].parallel_group is not None

    runner = RecordingStepRunner()
    executor = PlanExecutor(
        scheduler=DeterministicScheduler(),
        prelaunch_guard=FakePreLaunchGuard(),
        runner=runner,
    )
    first = executor.execute_cycle(
        plan=plan,
        run_state=initialize_run_state(plan, CorrelationId("corr-fanout")),
        now=NOW,
    )
    second = executor.execute_cycle(plan=plan, run_state=first.run_state, now=NOW)

    assert len(first.launched_step_ids) == 4
    assert len(second.launched_step_ids) == 1
    assert set(first.launched_step_ids).isdisjoint(second.launched_step_ids)
    assert len(first.launched_step_ids) <= 4
    assert len(second.launched_step_ids) <= 4


def test_wf8_join_depends_on_all_contiguous_branches_and_handoff_adds_no_ag02() -> None:
    requirements = WorkflowRequirements(
        external_evidence_required=True,
        production_required=True,
        parallel_evidence_branches=5,
        parallel_evidence_independent=True,
    )
    selection, plan = _compile(requirements, branches=5)
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_8,
        WorkflowKind.WF_4,
    )
    evidence = tuple(
        step for step in plan.steps if step.executor.kind is ExecutorKind.AG_02
    )
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    generation = next(
        step for step in plan.steps if step.executor.kind is ExecutorKind.AG_03
    )
    assert len(evidence) == 5
    assert join.capability_id == CapabilityId("CAP-O04")
    assert join.depends_on == tuple(step.step_id for step in evidence)
    assert generation.depends_on == (join.step_id,)


def test_wf9_join_precedes_runtime_decision_without_real_selection() -> None:
    _, plan = _compile(
        WorkflowRequirements(
            production_required=True,
            variant_count=3,
            variants_explicitly_useful=True,
        ),
        branches=3,
    )
    variants = tuple(
        step for step in plan.steps if step.executor.kind is ExecutorKind.AG_03
    )
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    decision = next(step for step in plan.steps if step.kind is StepKind.DECISION)
    assert join.depends_on == tuple(step.step_id for step in variants)
    assert decision.executor.kind is ExecutorKind.RUNTIME
    assert decision.capability_id is None
    assert decision.depends_on == (join.step_id,)
    runner = RecordingStepRunner()
    results = run_until_decisive(
        plan=plan,
        run_state=initialize_run_state(plan, CorrelationId("corr-variants")),
        now=NOW,
        guard=FakePreLaunchGuard(),
        runner=runner,
        completion_evaluator=_succeeded_evaluator(),
    )
    assert results[-1].decision.action is CoordinationAction.COMPLETE
    assert (decision.step_id, 1) in runner.calls


@pytest.mark.parametrize(
    ("anchor", "requirements"),
    [
        (
            HumanGateAnchor.BEFORE_FIRST_STAGE,
            WorkflowRequirements(
                production_required=True,
                human_gate_required=True,
            ),
        ),
        (
            HumanGateAnchor.AFTER_EVIDENCE,
            WorkflowRequirements(
                external_evidence_required=True,
                production_required=True,
                human_gate_required=True,
                parallel_evidence_branches=2,
                parallel_evidence_independent=True,
            ),
        ),
        (
            HumanGateAnchor.BEFORE_PROMOTION,
            WorkflowRequirements(
                promotion_required=True,
                human_gate_required=True,
            ),
        ),
    ],
)
def test_wf10_overlay_waits_without_gate_consumption_or_downstream_launch(
    anchor: HumanGateAnchor,
    requirements: WorkflowRequirements,
) -> None:
    selection, plan = _compile(
        requirements,
        human_anchor=anchor,
    )
    assert selection.overlays == (WorkflowKind.WF_10,)
    human = next(step for step in plan.steps if step.step_id == "human-gate")
    assert human.kind is StepKind.GATE
    assert human.executor.kind is ExecutorKind.RUNTIME
    assert human.capability_id == CapabilityId("CAP-O05")

    runner = RecordingStepRunner()
    results = run_until_decisive(
        plan=plan,
        run_state=initialize_run_state(plan, CorrelationId(f"corr-{anchor.value}")),
        now=NOW,
        guard=FakePreLaunchGuard(
            {human.step_id: PreLaunchDisposition.WAITING_GATE}
        ),
        runner=runner,
        completion_evaluator=_succeeded_evaluator(),
    )
    last = results[-1]
    assert last.decision.action is CoordinationAction.WAIT_GATE
    assert last.decision.run_state.status is WorkflowStatus.WAITING_GATE
    assert human.step_id not in tuple(step_id for step_id, _ in runner.calls)
    downstream = {
        step.step_id for step in plan.steps if human.step_id in step.depends_on
    }
    assert downstream.isdisjoint(step_id for step_id, _ in runner.calls)

    if anchor is HumanGateAnchor.AFTER_EVIDENCE:
        predecessor = next(step for step in plan.steps if step.step_id in human.depends_on)
        assert predecessor.kind is StepKind.JOIN
    if anchor is HumanGateAnchor.BEFORE_PROMOTION:
        gates = tuple(step for step in plan.steps if step.kind is StepKind.GATE)
        assert len(gates) == 2
        assert {step.step_id for step in gates} == {"human-gate", "s0-gate-0"}


def test_wf11_policy_gate_is_required_ancestor_and_blocks_promotion() -> None:
    selection, plan = _compile(WorkflowRequirements(promotion_required=True))
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_11,
    )
    validation = _step_for_capability(plan, "CAP-A01")
    gate = _step_for_capability(plan, "CAP-O05")
    promotion = _step_for_capability(plan, "CAP-A02")
    assert validation.executor.kind is ExecutorKind.APPLICATION
    assert gate.kind is StepKind.GATE
    assert promotion.executor.kind is ExecutorKind.APPLICATION
    assert gate.depends_on == (validation.step_id,)
    assert promotion.depends_on == (gate.step_id,)

    runner = RecordingStepRunner()
    results = run_until_decisive(
        plan=plan,
        run_state=initialize_run_state(plan, CorrelationId("corr-policy-gate")),
        now=NOW,
        guard=FakePreLaunchGuard(
            {gate.step_id: PreLaunchDisposition.WAITING_GATE}
        ),
        runner=runner,
        completion_evaluator=_succeeded_evaluator(),
    )
    assert results[-1].decision.action is CoordinationAction.WAIT_GATE
    assert tuple(step_id for step_id, _ in runner.calls) == (validation.step_id,)
    assert results[-1].decision.run_state.step_states[promotion.step_id].status in {
        StepRuntimeStatus.PENDING,
        StepRuntimeStatus.READY,
    }


def test_selector_and_compiler_are_repeatable_for_identical_inputs() -> None:
    requirements = WorkflowRequirements(
        external_evidence_required=True,
        production_required=True,
        deterministic_validation_required=True,
        parallel_evidence_branches=3,
        parallel_evidence_independent=True,
    )
    first_selection, first_plan = _compile(requirements, branches=3)
    second_selection, second_plan = _compile(requirements, branches=3)
    assert first_selection == second_selection
    first_structure = tuple(
        (
            step.step_id,
            step.depends_on,
            step.kind,
            step.executor,
            step.capability_id,
            step.parallel_group,
        )
        for step in first_plan.steps
    )
    second_structure = tuple(
        (
            step.step_id,
            step.depends_on,
            step.kind,
            step.executor,
            step.capability_id,
            step.parallel_group,
        )
        for step in second_plan.steps
    )
    assert first_plan.workflow_kind == second_plan.workflow_kind
    assert first_structure == second_structure
