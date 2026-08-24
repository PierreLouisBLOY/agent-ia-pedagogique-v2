from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    ExecutorKind,
    ExecutorRef,
    FailurePolicy,
    RecommendedAction,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    Plan,
    PlanExecutor,
    PlanHistory,
    PlanRevisionCode,
    PlanRevisionEngine,
    PreLaunchDecision,
    PreLaunchDisposition,
    RunState,
    StepExecutionResult,
    StepRuntimeStatus,
    StepState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 15, 0, tzinfo=UTC))
STARTED = Instant(datetime(2026, 8, 24, 14, 0, tzinfo=UTC))


def _step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    failure_policy: FailurePolicy = FailurePolicy.STOP,
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=StepKind.USE_CASE,
        capability_id=CapabilityId("CAP-R01"),
        executor=ExecutorRef(ExecutorKind.APPLICATION),
        objective=f"Execute {step_id}",
        depends_on=depends_on,
        permission_scope_ref="scope-1",
        failure_policy=failure_policy,
        output_contract={"type": "result"},
    )


def _plan(version: int, *steps: StepSpec) -> Plan:
    return Plan(
        plan_id="plan-1",
        run_id="run-1",
        plan_version=version,
        objective="Complete stable objective",
        success_criteria={"complete": True},
        workflow_kind="opaque-workflow",
        steps=steps,
        stop_conditions={"failure": "stop"},
    )


def _error(step_id: str) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="FAILED_FOR_REPLAN",
        category=ErrorCategory.DOMAIN,
        source=ErrorSource.APPLICATION,
        retryable=False,
        severity=ErrorSeverity.ERROR,
        message="Safe failure",
        step_id=step_id,
        attempt=1,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.REPLAN,
    )


class AllowGuard:
    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        del plan, step, run_state, now
        return PreLaunchDecision(PreLaunchDisposition.ALLOW)


class FailingRunner:
    def __init__(self, failing_step_id: str) -> None:
        self.failing_step_id = failing_step_id
        self.calls: list[str] = []

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        del plan, run_state, attempt, now
        self.calls.append(step.step_id)
        if step.step_id != self.failing_step_id:
            return StepExecutionResult(status=StepRuntimeStatus.SUCCEEDED)
        return StepExecutionResult(
            status=StepRuntimeStatus.FAILED,
            error=_error(step.step_id),
        )


def _executor(runner: FailingRunner) -> PlanExecutor:
    return PlanExecutor(
        scheduler=DeterministicScheduler(),
        prelaunch_guard=AllowGuard(),
        runner=runner,
    )


def _run_state(
    plan: Plan,
    step_states: dict[str, StepState],
    *,
    status: WorkflowStatus,
    started_at: Instant | None,
) -> RunState:
    return RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=status,
        step_states=step_states,
        started_at=started_at,
    )


def test_failure_replan_and_external_revision_returns_schedulable_state() -> None:
    current = _plan(1, _step("root", failure_policy=FailurePolicy.REPLAN))
    runner = FailingRunner("root")
    execution = _executor(runner).execute_cycle(
        plan=current,
        run_state=_run_state(
            current,
            {"root": StepState("root", StepRuntimeStatus.READY)},
            status=WorkflowStatus.PLANNED,
            started_at=None,
        ),
        now=NOW,
    )
    replacement = replace(
        current,
        plan_version=2,
        steps=(_step("replacement"),),
    )

    revision = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=execution.run_state,
        replacement=replacement,
    )

    assert execution.run_state.status is WorkflowStatus.REPLANNING
    assert revision.accepted and revision.run_state is not None
    assert revision.run_state.status is WorkflowStatus.RUNNING
    assert revision.run_state.step_states["replacement"].status is StepRuntimeStatus.PENDING
    assert revision.run_state.current_step_ids == ()


def test_success_is_reused_while_failed_step_is_replaced() -> None:
    step_a = _step("a")
    step_b = _step("b", depends_on=("a",), failure_policy=FailurePolicy.REPLAN)
    current = _plan(1, step_a, step_b)
    state_a = StepState(
        "a",
        StepRuntimeStatus.SUCCEEDED,
        started_at=STARTED,
        ended_at=NOW,
        attempt_count=1,
        result_refs=("result-a",),
        metrics={"quality": 1},
    )
    runner = FailingRunner("b")
    execution = _executor(runner).execute_cycle(
        plan=current,
        run_state=_run_state(
            current,
            {
                "a": state_a,
                "b": StepState("b", StepRuntimeStatus.READY),
            },
            status=WorkflowStatus.RUNNING,
            started_at=STARTED,
        ),
        now=NOW,
    )
    replacement = replace(
        current,
        plan_version=2,
        steps=(step_a, _step("b2", depends_on=("a",))),
    )

    revision = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=execution.run_state,
        replacement=replacement,
    )

    assert revision.accepted and revision.run_state is not None
    assert revision.run_state.step_states["a"] is state_a
    assert revision.run_state.step_states["b2"].status is StepRuntimeStatus.PENDING
    assert revision.reused_step_ids == ("a",)
    assert revision.added_step_ids == ("b2",)
    assert revision.removed_step_ids == ("b",)


def test_replan_without_structural_progress_is_rejected() -> None:
    current = _plan(1, _step("root", failure_policy=FailurePolicy.REPLAN))
    runner = FailingRunner("root")
    execution = _executor(runner).execute_cycle(
        plan=current,
        run_state=_run_state(
            current,
            {"root": StepState("root", StepRuntimeStatus.READY)},
            status=WorkflowStatus.PLANNED,
            started_at=None,
        ),
        now=NOW,
    )

    revision = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=execution.run_state,
        replacement=replace(current, plan_version=2),
    )

    assert not revision.accepted
    assert PlanRevisionCode.NO_STRUCTURAL_PROGRESS in {
        issue.code for issue in revision.issues
    }


def test_replan_history_rejects_return_to_earlier_structure() -> None:
    first = _plan(1, _step("structure-a"))
    second = replace(first, plan_version=2, steps=(_step("structure-b"),))
    run_state = _run_state(
        second,
        {"structure-b": StepState("structure-b", StepRuntimeStatus.PENDING)},
        status=WorkflowStatus.REPLANNING,
        started_at=STARTED,
    )

    revision = PlanRevisionEngine().revise(
        history=PlanHistory((first, second)),
        run_state=run_state,
        replacement=replace(first, plan_version=3),
    )

    assert PlanRevisionCode.STRUCTURAL_CYCLE_DETECTED in {
        issue.code for issue in revision.issues
    }


def test_replan_history_rejects_seventh_version() -> None:
    first = _plan(1, _step("step-v1"))
    history = PlanHistory(
        tuple(
            first
            if version == 1
            else replace(
                first,
                plan_version=version,
                steps=(_step(f"step-v{version}"),),
            )
            for version in range(1, 7)
        )
    )
    current = history.latest
    run_state = _run_state(
        current,
        {"step-v6": StepState("step-v6", StepRuntimeStatus.PENDING)},
        status=WorkflowStatus.REPLANNING,
        started_at=STARTED,
    )

    revision = PlanRevisionEngine().revise(
        history=history,
        run_state=run_state,
        replacement=replace(current, plan_version=7, steps=(_step("step-v7"),)),
    )

    assert PlanRevisionCode.MAX_PLAN_VERSIONS_EXCEEDED in {
        issue.code for issue in revision.issues
    }
