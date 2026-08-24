from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    AgentId,
    ExecutorKind,
    ExecutorRef,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.orchestration import (
    CompletionDisposition,
    CoordinationAction,
    OrchestrationCoordinator,
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
    WorkflowCompletionDecision,
    WorkflowRequirements,
    WorkflowResponsibility,
    WorkflowSelector,
)
from backend.agent_runtime.registry import (
    BASELINE_AGENT_REGISTRY,
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityClass,
    CapabilityExecutionRoute,
)
from backend.agent_runtime.runtime import (
    ExecutionCycleResult,
    ExecutionDirective,
    ExecutionDirectiveCode,
    Plan,
    PlanHistory,
    PlanRevisionCode,
    PlanRevisionEngine,
    RunState,
    StepRuntimeStatus,
    StepState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.orchestration_fakes import (
    FakePreLaunchGuard,
    FakeWorkflowCompletionEvaluator,
    RecordingStepRunner,
)

R = WorkflowResponsibility
NOW = Instant(datetime(2026, 8, 25, 17, 0, tzinfo=UTC))
STARTED = Instant(NOW.value - timedelta(minutes=5))


def _step(
    step_id: str,
    *,
    kind: StepKind = StepKind.USE_CASE,
    capability: str | None = "CAP-R01",
    executor: ExecutorKind = ExecutorKind.APPLICATION,
    depends_on: tuple[str, ...] = (),
) -> StepSpec:
    executable = kind in {StepKind.USE_CASE, StepKind.AGENT, StepKind.TOOL}
    return StepSpec(
        step_id=step_id,
        kind=kind,
        capability_id=CapabilityId(capability) if capability is not None else None,
        executor=ExecutorRef(executor),
        objective=f"Execute {step_id}",
        depends_on=depends_on,
        permission_scope_ref="scope-test" if executable else None,
        output_contract={"type": "result"},
    )


def _plan(
    version: int = 1,
    *steps: StepSpec,
    workflow_kind: str = "WF-TEST",
    objective: str = "Stable objective",
) -> Plan:
    return Plan(
        plan_id="plan-authority",
        run_id="run-authority",
        plan_version=version,
        objective=objective,
        success_criteria={"complete": True},
        workflow_kind=workflow_kind,
        steps=steps or (_step("work"),),
        stop_conditions={"failure": "stop"},
    )


def _state(
    step_id: str,
    status: StepRuntimeStatus,
    *,
    attempt_count: int = 1,
) -> StepState:
    if status is StepRuntimeStatus.RUNNING:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            attempt_count=attempt_count,
        )
    if status in {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.SKIPPED,
        StepRuntimeStatus.CANCELLED,
    }:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=attempt_count,
            result_refs=(f"result-{step_id}",),
        )
    if status is StepRuntimeStatus.FAILED:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=attempt_count,
            block_reason="failed",
        )
    return StepState(step_id, status, attempt_count=attempt_count)


def _run_state(
    plan: Plan,
    statuses: dict[str, StepRuntimeStatus],
    *,
    status: WorkflowStatus = WorkflowStatus.RUNNING,
    attempts: dict[str, int] | None = None,
) -> RunState:
    attempts = attempts or {}
    return RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-authority"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=status,
        step_states={
            step.step_id: _state(
                step.step_id,
                statuses[step.step_id],
                attempt_count=attempts.get(step.step_id, 1),
            )
            for step in plan.steps
        },
        started_at=STARTED,
    )


def _coordinator(
    disposition: CompletionDisposition = CompletionDisposition.SUCCEEDED,
) -> tuple[OrchestrationCoordinator, FakeWorkflowCompletionEvaluator]:
    evaluator = FakeWorkflowCompletionEvaluator(
        WorkflowCompletionDecision(disposition, f"FAKE_{disposition.value}")
    )
    return OrchestrationCoordinator(evaluator), evaluator


def _revision_codes(result) -> tuple[PlanRevisionCode, ...]:
    return tuple(issue.code for issue in result.issues)


def test_agent_and_executor_vocabularies_stop_at_ag04_without_ag01_executor() -> None:
    assert tuple(item.agent_id for item in BASELINE_AGENT_REGISTRY.all()) == (
        AgentId.AG_01,
        AgentId.AG_02,
        AgentId.AG_03,
        AgentId.AG_04,
    )
    assert {item.value for item in AgentId} == {"AG-01", "AG-02", "AG-03", "AG-04"}
    assert "AG-05" not in {item.value for item in AgentId}
    assert "AG_01" not in ExecutorKind.__members__
    assert "AG-05" not in {item.value for item in ExecutorKind}


@pytest.mark.parametrize(
    ("agent_id", "allowed_prefix", "forbidden_prefixes", "capability_class"),
    [
        (
            AgentId.AG_02,
            "CAP-E",
            ("CAP-G", "CAP-V"),
            CapabilityClass.EVIDENCE,
        ),
        (
            AgentId.AG_03,
            "CAP-G",
            ("CAP-E", "CAP-V"),
            CapabilityClass.GENERATE_TRANSFORM,
        ),
        (
            AgentId.AG_04,
            "CAP-V",
            ("CAP-E", "CAP-G"),
            CapabilityClass.REVIEW,
        ),
    ],
)
def test_specialist_capabilities_remain_disjoint(
    agent_id: AgentId,
    allowed_prefix: str,
    forbidden_prefixes: tuple[str, ...],
    capability_class: CapabilityClass,
) -> None:
    owned = BASELINE_CAPABILITY_REGISTRY.owned_by(agent_id)
    assert owned
    assert all(item.capability_id.value.startswith(allowed_prefix) for item in owned)
    assert all(item.capability_class is capability_class for item in owned)
    assert all(
        not item.capability_id.value.startswith(forbidden_prefixes) for item in owned
    )


def test_application_actions_are_not_rewritten_as_agent_execution() -> None:
    application_actions = BASELINE_CAPABILITY_REGISTRY.by_class(
        CapabilityClass.APPLICATION_ACTION
    )
    assert application_actions
    assert all(
        item.execution_route is CapabilityExecutionRoute.APPLICATION
        and item.owner_agent is None
        for item in application_actions
    )


def test_compiler_preserves_opaque_permission_ref_without_granting_authority() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(application_action_required=True)
    )
    request = PlanCompilationRequest(
        selection=selection,
        plan_id="plan-scope",
        run_id="run-scope",
        plan_version=1,
        objective="Preserve opaque scope",
        success_criteria={"complete": True},
        stop_conditions={"failure": "stop"},
        bindings=(
            PlanStepBinding(
                stage_index=0,
                responsibility=R.DIRECT_APPLICATION,
                step_id="application-action",
                objective="Call Application inbound boundary",
                capability_id=CapabilityId("CAP-R01"),
                permission_scope_ref="opaque-scope-ref",
                output_contract={"type": "result"},
            ),
        ),
    )
    plan = PlanCompiler().compile(request)
    assert plan.steps[0].executor.kind is ExecutorKind.APPLICATION
    assert plan.steps[0].permission_scope_ref == "opaque-scope-ref"


def test_reconciliation_dominates_without_an_automatic_followup_cycle() -> None:
    plan = _plan(1, _step("running"))
    run_state = _run_state(plan, {"running": StepRuntimeStatus.RUNNING})
    runner = RecordingStepRunner()
    coordinator, evaluator = _coordinator()
    cycle = ExecutionCycleResult(
        run_state,
        directives=(
            ExecutionDirective(
                ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED,
                reason_code="RUN_DEADLINE_EXCEEDED",
            ),
            ExecutionDirective(
                ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
                step_id="running",
                reason_code="EFFECT_UNKNOWN",
            ),
        ),
    )
    decision = coordinator.coordinate(plan=plan, cycle=cycle, now=NOW)
    assert decision.action is CoordinationAction.RECONCILIATION_REQUIRED
    assert decision.run_state is run_state
    assert runner.calls == []
    assert evaluator.calls == []


def test_retry_is_requested_without_state_or_attempt_mutation() -> None:
    plan = _plan(1, _step("failed"))
    run_state = _run_state(
        plan,
        {"failed": StepRuntimeStatus.FAILED},
        attempts={"failed": 2},
    )
    coordinator, evaluator = _coordinator()
    runner = RecordingStepRunner()
    decision = coordinator.coordinate(
        plan=plan,
        cycle=ExecutionCycleResult(
            run_state,
            directives=(
                ExecutionDirective(
                    ExecutionDirectiveCode.RETRY_REQUIRED,
                    step_id="failed",
                    reason_code="SAFE_RETRY_REQUIRES_COORDINATION",
                ),
            ),
        ),
        now=NOW,
    )
    assert decision.action is CoordinationAction.RETRY_REQUIRED
    assert decision.run_state is run_state
    assert decision.run_state.step_states["failed"].attempt_count == 2
    assert runner.calls == []
    assert evaluator.calls == []


def test_partial_requires_review_without_completion_or_promotion() -> None:
    plan = _plan(1, _step("partial"))
    run_state = _run_state(plan, {"partial": StepRuntimeStatus.PARTIAL})
    coordinator, evaluator = _coordinator()
    decision = coordinator.coordinate(
        plan=plan,
        cycle=ExecutionCycleResult(
            run_state,
            directives=(
                ExecutionDirective(
                    ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION,
                    step_id="partial",
                    reason_code="PARTIAL_RESULT_REQUIRES_POLICY",
                ),
            ),
        ),
        now=NOW,
    )
    assert decision.action is CoordinationAction.REVIEW_PARTIAL
    assert decision.run_state.status is WorkflowStatus.RUNNING
    assert all(step.capability_id != CapabilityId("CAP-A02") for step in plan.steps)
    assert evaluator.calls == []


@pytest.mark.parametrize(
    ("disposition", "expected_action", "expected_status"),
    [
        (
            CompletionDisposition.SUCCEEDED,
            CoordinationAction.COMPLETE,
            WorkflowStatus.SUCCEEDED,
        ),
        (
            CompletionDisposition.PARTIAL,
            CoordinationAction.COMPLETE,
            WorkflowStatus.PARTIAL,
        ),
        (
            CompletionDisposition.REPLAN_REQUIRED,
            CoordinationAction.REPLAN_REQUIRED,
            WorkflowStatus.REPLANNING,
        ),
    ],
)
def test_quiescence_requires_one_explicit_completion_evaluation(
    disposition: CompletionDisposition,
    expected_action: CoordinationAction,
    expected_status: WorkflowStatus,
) -> None:
    plan = _plan(1, _step("done"))
    run_state = _run_state(plan, {"done": StepRuntimeStatus.SUCCEEDED})
    coordinator, evaluator = _coordinator(disposition)
    decision = coordinator.coordinate(
        plan=plan,
        cycle=ExecutionCycleResult(run_state),
        now=NOW,
    )
    assert decision.action is expected_action
    assert decision.run_state.status is expected_status
    assert len(evaluator.calls) == 1


def test_wf7_second_correction_cycle_is_adopted_as_plan_version_two() -> None:
    correction = _step(
        "correction-v1",
        kind=StepKind.AGENT,
        capability="CAP-G03",
        executor=ExecutorKind.AG_03,
    )
    review = _step(
        "review-v1",
        kind=StepKind.AGENT,
        capability="CAP-V01",
        executor=ExecutorKind.AG_04,
        depends_on=(correction.step_id,),
    )
    current = _plan(1, correction, review, workflow_kind="WF-7")
    run_state = _run_state(
        current,
        {
            correction.step_id: StepRuntimeStatus.SUCCEEDED,
            review.step_id: StepRuntimeStatus.FAILED,
        },
        status=WorkflowStatus.REPLANNING,
        attempts={correction.step_id: 1, review.step_id: 2},
    )
    correction_v2 = replace(
        correction,
        step_id="correction-v2",
        depends_on=(review.step_id,),
    )
    review_v2 = replace(
        review,
        step_id="review-v2",
        depends_on=(correction_v2.step_id,),
    )
    replacement = replace(
        current,
        plan_version=2,
        steps=(*current.steps, correction_v2, review_v2),
    )
    coordinator, _ = _coordinator()
    result = coordinator.apply_replan(
        history=PlanHistory((current,)),
        run_state=run_state,
        replacement=replacement,
    )
    assert result.accepted
    assert result.history is not None and result.history.latest.plan_version == 2
    assert result.run_state is not None
    assert result.run_state.step_states[correction.step_id] is run_state.step_states[
        correction.step_id
    ]
    assert result.run_state.step_states[review.step_id].status is StepRuntimeStatus.PENDING
    assert result.run_state.step_states[review.step_id].attempt_count == 2
    assert result.added_step_ids == (correction_v2.step_id, review_v2.step_id)


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda plan: replace(plan, plan_version=2),
            PlanRevisionCode.NO_STRUCTURAL_PROGRESS,
        ),
        (
            lambda plan: replace(
                plan,
                plan_version=3,
                steps=(*plan.steps, _step("new-version")),
            ),
            PlanRevisionCode.VERSION_NOT_SEQUENTIAL,
        ),
        (
            lambda plan: replace(
                plan,
                plan_version=2,
                objective="Drifted objective",
                steps=(*plan.steps, _step("new-objective")),
            ),
            PlanRevisionCode.OBJECTIVE_MISMATCH,
        ),
        (
            lambda plan: replace(
                plan,
                plan_version=2,
                workflow_kind="WF-OTHER",
                steps=(*plan.steps, _step("new-workflow")),
            ),
            PlanRevisionCode.WORKFLOW_KIND_MISMATCH,
        ),
    ],
)
def test_revision_engine_retains_replan_invariants(
    mutator,
    expected_code: PlanRevisionCode,
) -> None:
    current = _plan(1, _step("root"), workflow_kind="WF-7")
    run_state = _run_state(
        current,
        {"root": StepRuntimeStatus.FAILED},
        status=WorkflowStatus.REPLANNING,
    )
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=run_state,
        replacement=mutator(current),
    )
    assert not result.accepted
    assert expected_code in _revision_codes(result)


def test_revision_rejects_running_step_without_modifying_snapshot() -> None:
    current = _plan(1, _step("active"), workflow_kind="WF-7")
    run_state = _run_state(
        current,
        {"active": StepRuntimeStatus.RUNNING},
        status=WorkflowStatus.REPLANNING,
    )
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=run_state,
        replacement=replace(
            current,
            plan_version=2,
            steps=(*current.steps, _step("new-after-active")),
        ),
    )
    assert not result.accepted
    assert PlanRevisionCode.RUN_HAS_ACTIVE_STEP in _revision_codes(result)
    assert run_state.step_states["active"].status is StepRuntimeStatus.RUNNING


def test_revision_limit_six_and_structural_cycle_remain_enforced() -> None:
    first = _plan(1, _step("structure-v1"), workflow_kind="WF-7")
    history = PlanHistory(
        tuple(
            first
            if version == 1
            else replace(
                first,
                plan_version=version,
                steps=(_step(f"structure-v{version}"),),
            )
            for version in range(1, 7)
        )
    )
    current = history.latest
    version_seven = PlanRevisionEngine().revise(
        history=history,
        run_state=_run_state(
            current,
            {"structure-v6": StepRuntimeStatus.FAILED},
            status=WorkflowStatus.REPLANNING,
        ),
        replacement=replace(
            current,
            plan_version=7,
            steps=(_step("structure-v7"),),
        ),
    )
    assert PlanRevisionCode.MAX_PLAN_VERSIONS_EXCEEDED in _revision_codes(
        version_seven
    )

    second = replace(first, plan_version=2, steps=(_step("structure-v2"),))
    cycle = PlanRevisionEngine().revise(
        history=PlanHistory((first, second)),
        run_state=_run_state(
            second,
            {"structure-v2": StepRuntimeStatus.FAILED},
            status=WorkflowStatus.REPLANNING,
        ),
        replacement=replace(first, plan_version=3),
    )
    assert PlanRevisionCode.STRUCTURAL_CYCLE_DETECTED in _revision_codes(cycle)


def test_plan_history_rejects_workflow_kind_change_before_any_auto_reselect() -> None:
    first = _plan(1, _step("v1"), workflow_kind="WF-7")
    second = replace(
        first,
        plan_version=2,
        workflow_kind="WF-3",
        steps=(_step("v2"),),
    )
    with pytest.raises(ValueError, match="workflow_kind"):
        PlanHistory((first, second))


def test_test_fakes_are_protocol_compatible_and_side_effect_free() -> None:
    from backend.agent_runtime.orchestration import WorkflowCompletionEvaluator
    from backend.agent_runtime.runtime import PreLaunchGuard, StepRunner

    guard = FakePreLaunchGuard()
    runner = RecordingStepRunner()
    evaluator = FakeWorkflowCompletionEvaluator(
        WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "DONE")
    )
    assert isinstance(guard, PreLaunchGuard)
    assert isinstance(runner, StepRunner)
    assert isinstance(evaluator, WorkflowCompletionEvaluator)
    assert guard.calls == [] and runner.calls == [] and evaluator.calls == []
