from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from backend.agent_runtime.contracts import (
    BudgetSpec,
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
    ExecutionDirective,
    ExecutionDirectiveCode,
    Plan,
    PlanExecutor,
    PreLaunchDecision,
    PreLaunchDisposition,
    PreLaunchGuard,
    RunState,
    SchedulerStateError,
    StepExecutionResult,
    StepRunner,
    StepRuntimeStatus,
    StepState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))
STARTED = Instant(NOW.value - timedelta(seconds=30))


def _step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    failure_policy: FailurePolicy = FailurePolicy.STOP,
    budget: BudgetSpec | None = None,
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=StepKind.USE_CASE,
        capability_id=CapabilityId("CAP-R01"),
        executor=ExecutorRef(ExecutorKind.APPLICATION),
        objective=f"Execute {step_id}",
        depends_on=depends_on,
        permission_scope_ref="scope-1",
        budget=budget,
        failure_policy=failure_policy,
        output_contract={"type": "result"},
    )


def _plan(
    *steps: StepSpec,
    budget_envelope: BudgetSpec | None = None,
) -> Plan:
    return Plan(
        plan_id="plan-1",
        run_id="run-1",
        plan_version=1,
        objective="Execute deterministic plan",
        success_criteria={"complete": True},
        workflow_kind="opaque-workflow",
        steps=steps,
        budget_envelope=budget_envelope,
        stop_conditions={"failure": "stop"},
    )


def _state(
    step_id: str,
    status: StepRuntimeStatus = StepRuntimeStatus.READY,
    *,
    attempt_count: int = 0,
    started_at: Instant | None = None,
) -> StepState:
    if status is StepRuntimeStatus.RUNNING:
        return StepState(
            step_id=step_id,
            status=status,
            started_at=started_at or STARTED,
            attempt_count=attempt_count,
        )
    if status in {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.CANCELLED,
        StepRuntimeStatus.SKIPPED,
    }:
        return StepState(
            step_id=step_id,
            status=status,
            ended_at=NOW,
            attempt_count=attempt_count,
        )
    if status is StepRuntimeStatus.FAILED:
        return StepState(
            step_id=step_id,
            status=status,
            ended_at=NOW,
            attempt_count=attempt_count,
            error_ref="error-1",
        )
    if status is StepRuntimeStatus.BLOCKED:
        return StepState(
            step_id=step_id,
            status=status,
            attempt_count=attempt_count,
            block_reason="blocked",
        )
    return StepState(step_id=step_id, status=status, attempt_count=attempt_count)


def _run_state(
    plan: Plan,
    states: Mapping[str, StepState],
    *,
    status: WorkflowStatus = WorkflowStatus.PLANNED,
    started_at: Instant | None = None,
) -> RunState:
    active = status in {
        WorkflowStatus.RUNNING,
        WorkflowStatus.REPLANNING,
    }
    terminal = status in {
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    }
    stop_required = status in {
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    }
    return RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=status,
        step_states=states,
        started_at=(started_at or STARTED) if active else started_at,
        ended_at=NOW if terminal else None,
        stop_reason="terminal" if stop_required else None,
    )


def _error(
    step_id: str,
    *,
    attempt: int = 1,
    category: ErrorCategory = ErrorCategory.TRANSIENT,
    retryable: bool = True,
    effect_state: EffectState = EffectState.NONE,
    recommended_action: RecommendedAction = RecommendedAction.STOP,
    error_code: str = "EXECUTION_ERROR",
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code=error_code,
        category=category,
        source=ErrorSource.APPLICATION,
        retryable=retryable,
        severity=ErrorSeverity.ERROR,
        message="Safe execution error",
        step_id=step_id,
        attempt=attempt,
        effect_state=effect_state,
        recommended_action=recommended_action,
    )


class FakeGuard:
    def __init__(
        self,
        decisions: Mapping[str, PreLaunchDecision] | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.decisions = dict(decisions or {})
        self.calls: list[str] = []
        self.events = events

    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        del plan, run_state, now
        self.calls.append(step.step_id)
        if self.events is not None:
            self.events.append(f"guard:{step.step_id}")
        return self.decisions.get(
            step.step_id,
            PreLaunchDecision(PreLaunchDisposition.ALLOW),
        )


class FakeRunner:
    def __init__(
        self,
        results: Mapping[str, object] | None = None,
        *,
        raise_for: str | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.results = dict(results or {})
        self.raise_for = raise_for
        self.calls: list[str] = []
        self.attempts: list[int] = []
        self.seen_states: list[RunState] = []
        self.events = events

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        del plan, now
        self.calls.append(step.step_id)
        self.attempts.append(attempt)
        self.seen_states.append(run_state)
        if self.events is not None:
            self.events.append(f"runner:{step.step_id}")
        if self.raise_for == step.step_id:
            raise RuntimeError("raw sensitive runner exception")
        return cast(
            StepExecutionResult,
            self.results.get(
                step.step_id,
                StepExecutionResult(status=StepRuntimeStatus.SUCCEEDED),
            ),
        )


def _executor(guard: FakeGuard, runner: FakeRunner) -> PlanExecutor:
    return PlanExecutor(
        scheduler=DeterministicScheduler(),
        prelaunch_guard=guard,
        runner=runner,
    )


def _execute(
    plan: Plan,
    states: Mapping[str, StepState],
    *,
    guard: FakeGuard | None = None,
    runner: FakeRunner | None = None,
    status: WorkflowStatus = WorkflowStatus.PLANNED,
) -> tuple[FakeGuard, FakeRunner, object]:
    effective_guard = guard or FakeGuard()
    effective_runner = runner or FakeRunner()
    result = _executor(effective_guard, effective_runner).execute_cycle(
        plan=plan,
        run_state=_run_state(plan, states, status=status),
        now=NOW,
    )
    return effective_guard, effective_runner, result


def test_prelaunch_dispositions_are_exact() -> None:
    assert [item.value for item in PreLaunchDisposition] == [
        "ALLOW",
        "WAITING_GATE",
        "DENY",
        "CONDITION_REQUIRED",
    ]


def test_execution_directive_codes_are_exact() -> None:
    assert [item.value for item in ExecutionDirectiveCode] == [
        "CONTINUE",
        "WAITING_GATE",
        "CONDITION_REQUIRED",
        "PRELAUNCH_DENIED",
        "RETRY_REQUIRED",
        "REPLAN_REQUIRED",
        "ESCALATED",
        "STOPPED",
        "PARTIAL_REQUIRES_DECISION",
        "RECONCILIATION_REQUIRED",
        "READY_DEADLINE_EXPIRED",
        "RUN_DEADLINE_EXCEEDED",
    ]


def test_continue_directive_forbids_reason_code() -> None:
    with pytest.raises(ValueError, match="CONTINUE"):
        ExecutionDirective(
            ExecutionDirectiveCode.CONTINUE,
            step_id="step",
            reason_code="UNEXPECTED",
        )


def test_non_continue_directive_requires_reason_code() -> None:
    with pytest.raises(ValueError, match="reason_code"):
        ExecutionDirective(ExecutionDirectiveCode.STOPPED, step_id="step")


def test_step_scoped_directive_requires_step_id() -> None:
    with pytest.raises(ValueError, match="step_id"):
        ExecutionDirective(
            ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
            reason_code="SAFE_REASON",
        )


def test_run_deadline_directive_may_omit_step_id() -> None:
    directive = ExecutionDirective(
        ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED,
        reason_code="RUN_DEADLINE_EXCEEDED",
    )

    assert directive.step_id is None


def test_allow_prelaunch_decision_forbids_reason_code() -> None:
    with pytest.raises(ValueError):
        PreLaunchDecision(PreLaunchDisposition.ALLOW, "UNEXPECTED")


@pytest.mark.parametrize(
    "disposition",
    [
        PreLaunchDisposition.WAITING_GATE,
        PreLaunchDisposition.DENY,
        PreLaunchDisposition.CONDITION_REQUIRED,
    ],
)
def test_non_allow_prelaunch_decision_requires_reason(
    disposition: PreLaunchDisposition,
) -> None:
    with pytest.raises(ValueError):
        PreLaunchDecision(disposition)


def test_runtime_checkable_protocols_accept_conforming_fakes() -> None:
    assert isinstance(FakeGuard(), PreLaunchGuard)
    assert isinstance(FakeRunner(), StepRunner)


@pytest.mark.parametrize(
    "status",
    [
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.FAILED,
        StepRuntimeStatus.CANCELLED,
    ],
)
def test_step_execution_result_accepts_exact_terminal_statuses(
    status: StepRuntimeStatus,
) -> None:
    error = _error("step") if status is StepRuntimeStatus.FAILED else None
    assert StepExecutionResult(status=status, error=error).status is status


@pytest.mark.parametrize(
    "status",
    [
        StepRuntimeStatus.PENDING,
        StepRuntimeStatus.READY,
        StepRuntimeStatus.RUNNING,
        StepRuntimeStatus.BLOCKED,
        StepRuntimeStatus.SKIPPED,
    ],
)
def test_step_execution_result_rejects_other_statuses(status: StepRuntimeStatus) -> None:
    with pytest.raises(ValueError):
        StepExecutionResult(status=status)


def test_succeeded_execution_result_rejects_error() -> None:
    with pytest.raises(ValueError):
        StepExecutionResult(
            status=StepRuntimeStatus.SUCCEEDED,
            error=_error("step"),
        )


def test_failed_execution_result_requires_error() -> None:
    with pytest.raises(ValueError):
        StepExecutionResult(status=StepRuntimeStatus.FAILED)


def test_execution_result_refs_and_metrics_are_deeply_immutable() -> None:
    result = StepExecutionResult(
        status=StepRuntimeStatus.SUCCEEDED,
        result_refs=["result-1"],  # type: ignore[arg-type]
        metrics={"counts": {"items": 1}},
    )

    assert result.result_refs == ("result-1",)
    with pytest.raises(TypeError):
        result.metrics["other"] = 2  # type: ignore[index]
    counts = result.metrics["counts"]
    assert isinstance(counts, Mapping)
    with pytest.raises(TypeError):
        counts["items"] = 2  # type: ignore[index]


def test_allow_launches_once_and_increments_attempt() -> None:
    step = _step("root")
    plan = _plan(step)
    guard, runner, result = _execute(plan, {"root": _state("root")})

    assert guard.calls == ["root"]
    assert runner.calls == ["root"]
    assert runner.attempts == [1]
    assert result.launched_step_ids == ("root",)
    assert result.run_state.step_states["root"].attempt_count == 1


def test_first_launch_starts_run_and_step_at_now() -> None:
    plan = _plan(_step("root"))
    _, runner, result = _execute(plan, {"root": _state("root")})

    assert result.run_state.status is WorkflowStatus.RUNNING
    assert result.run_state.started_at == NOW
    assert result.run_state.step_states["root"].started_at == NOW
    seen = runner.seen_states[0]
    assert seen.status is WorkflowStatus.RUNNING
    assert seen.step_states["root"].status is StepRuntimeStatus.RUNNING


def test_executor_does_not_mutate_step_spec() -> None:
    step = _step("root")
    plan = _plan(step)

    _execute(plan, {"root": _state("root")})

    assert plan.steps[0] is step
    with pytest.raises(FrozenInstanceError):
        step.objective = "changed"  # type: ignore[misc]


def test_prelaunch_guard_is_called_before_runner() -> None:
    events: list[str] = []
    plan = _plan(_step("root"))
    _execute(
        plan,
        {"root": _state("root")},
        guard=FakeGuard(events=events),
        runner=FakeRunner(events=events),
    )

    assert events == ["guard:root", "runner:root"]


def test_condition_required_keeps_step_ready_without_runner() -> None:
    plan = _plan(_step("root"))
    guard = FakeGuard(
        {
            "root": PreLaunchDecision(
                PreLaunchDisposition.CONDITION_REQUIRED,
                "TRUSTED_FACT_REQUIRED",
            )
        }
    )
    guard, runner, result = _execute(
        plan,
        {"root": _state("root")},
        guard=guard,
    )

    assert runner.calls == []
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.READY
    assert result.directives[0].code is ExecutionDirectiveCode.CONDITION_REQUIRED


def test_waiting_gate_stops_cycle_without_starting_run() -> None:
    plan = _plan(_step("first"), _step("second"))
    guard = FakeGuard(
        {
            "first": PreLaunchDecision(
                PreLaunchDisposition.WAITING_GATE,
                "GATE_DECISION_REQUIRED",
            )
        }
    )
    _, runner, result = _execute(
        plan,
        {"first": _state("first"), "second": _state("second")},
        guard=guard,
    )

    assert runner.calls == []
    assert guard.calls == ["first"]
    assert result.run_state.status is WorkflowStatus.WAITING_GATE
    assert result.run_state.started_at is None
    assert result.run_state.step_states["first"].status is StepRuntimeStatus.READY


def test_prelaunch_deny_blocks_without_attempt_or_runner() -> None:
    step = _step("root")
    plan = _plan(step)
    guard = FakeGuard(
        {
            "root": PreLaunchDecision(
                PreLaunchDisposition.DENY,
                "PERMISSION_DENIED",
            )
        }
    )
    _, runner, result = _execute(plan, {"root": _state("root")}, guard=guard)

    state = result.run_state.step_states["root"]
    assert runner.calls == []
    assert state.status is StepRuntimeStatus.BLOCKED
    assert state.attempt_count == 0
    assert state.block_reason == "prelaunch denied: PERMISSION_DENIED"
    assert result.directives[0].code is ExecutionDirectiveCode.PRELAUNCH_DENIED


def test_succeeded_result_applies_refs_and_metrics() -> None:
    plan = _plan(_step("root"))
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.SUCCEEDED,
                result_refs=("result-1",),
                metrics={"items": 2},
            )
        }
    )
    _, _, result = _execute(plan, {"root": _state("root")}, runner=runner)

    state = result.run_state.step_states["root"]
    assert state.status is StepRuntimeStatus.SUCCEEDED
    assert state.ended_at == NOW
    assert state.result_refs == ("result-1",)
    assert state.metrics == {"items": 2}
    assert result.directives[0].code is ExecutionDirectiveCode.CONTINUE


def test_partial_result_requires_decision() -> None:
    plan = _plan(_step("root"))
    runner = FakeRunner(
        {"root": StepExecutionResult(status=StepRuntimeStatus.PARTIAL)}
    )
    _, _, result = _execute(plan, {"root": _state("root")}, runner=runner)

    assert result.run_state.step_states["root"].status is StepRuntimeStatus.PARTIAL
    assert result.directives[0].code is ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION


@pytest.mark.parametrize(
    "status",
    [StepRuntimeStatus.FAILED, StepRuntimeStatus.CANCELLED],
)
def test_failed_and_cancelled_results_apply_terminal_step_state(
    status: StepRuntimeStatus,
) -> None:
    step = _step("root")
    plan = _plan(step)
    error = _error("root", retryable=False)
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=status,
                error=error if status is StepRuntimeStatus.FAILED else None,
            )
        }
    )
    _, _, result = _execute(plan, {"root": _state("root")}, runner=runner)

    assert result.run_state.step_states["root"].status is status
    assert result.completed_step_ids == ("root",)


@pytest.mark.parametrize(
    "runner_result",
    [
        StepExecutionResult(status=StepRuntimeStatus.SUCCEEDED),
        StepExecutionResult(status=StepRuntimeStatus.PARTIAL),
        StepExecutionResult(status=StepRuntimeStatus.FAILED, error=_error("root")),
        StepExecutionResult(status=StepRuntimeStatus.CANCELLED),
    ],
)
def test_all_normal_runner_terminal_results_are_completed(
    runner_result: StepExecutionResult,
) -> None:
    plan = _plan(_step("root"))
    runner = FakeRunner({"root": runner_result})
    _, _, result = _execute(plan, {"root": _state("root")}, runner=runner)

    assert result.completed_step_ids == ("root",)


def test_invalid_runner_result_requires_reconciliation_without_leakage() -> None:
    sensitive_text = "raw-provider-secret-payload"
    plan = _plan(_step("root"), _step("second"))
    runner = FakeRunner({"root": {"raw": sensitive_text}})

    guard, runner, result = _execute(
        plan,
        {"root": _state("root"), "second": _state("second")},
        runner=runner,
    )

    state = result.run_state.step_states["root"]
    assert guard.calls == ["root"]
    assert runner.calls == ["root"]
    assert state.status is StepRuntimeStatus.RUNNING
    assert state.attempt_count == 1
    assert result.launched_step_ids == ("root",)
    assert result.completed_step_ids == ()
    assert result.directives[0].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert (
        result.directives[0].reason_code
        == "RUNNER_RESULT_CONTRACT_INVALID_EFFECT_UNKNOWN"
    )
    assert sensitive_text not in repr(result)
    assert result.run_state.stop_reason is None


def test_runner_error_step_mismatch_requires_reconciliation_before_policy() -> None:
    plan = _plan(
        _step("root", failure_policy=FailurePolicy.STOP),
        _step("second"),
    )
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("other-step"),
            )
        }
    )

    guard, runner, result = _execute(
        plan,
        {"root": _state("root"), "second": _state("second")},
        runner=runner,
    )

    assert guard.calls == ["root"]
    assert runner.calls == ["root"]
    assert result.run_state.status is WorkflowStatus.RUNNING
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.RUNNING
    assert result.completed_step_ids == ()
    assert result.directives == (
        ExecutionDirective(
            ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
            step_id="root",
            reason_code="RUNNER_ERROR_STEP_MISMATCH_EFFECT_UNKNOWN",
        ),
    )


def test_runner_error_attempt_mismatch_requires_reconciliation() -> None:
    plan = _plan(
        _step("root", failure_policy=FailurePolicy.RETRY),
        _step("second"),
    )
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("root", attempt=1),
            )
        }
    )

    guard, runner, result = _execute(
        plan,
        {
            "root": _state("root", attempt_count=1),
            "second": _state("second"),
        },
        runner=runner,
    )

    state = result.run_state.step_states["root"]
    assert guard.calls == ["root"]
    assert runner.calls == ["root"]
    assert runner.attempts == [2]
    assert state.status is StepRuntimeStatus.RUNNING
    assert state.attempt_count == 2
    assert result.completed_step_ids == ()
    assert result.directives[0].reason_code == (
        "RUNNER_ERROR_ATTEMPT_MISMATCH_EFFECT_UNKNOWN"
    )
    assert all(
        directive.code
        not in {
            ExecutionDirectiveCode.RETRY_REQUIRED,
            ExecutionDirectiveCode.REPLAN_REQUIRED,
            ExecutionDirectiveCode.STOPPED,
        }
        for directive in result.directives
    )


def test_runner_error_attempt_two_applies_failure_policy_normally() -> None:
    plan = _plan(_step("root", failure_policy=FailurePolicy.RETRY))
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("root", attempt=2),
            )
        }
    )

    _, runner, result = _execute(
        plan,
        {"root": _state("root", attempt_count=1)},
        runner=runner,
    )

    assert runner.attempts == [2]
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.FAILED
    assert result.completed_step_ids == ("root",)
    assert result.directives[0].code is ExecutionDirectiveCode.RETRY_REQUIRED


@pytest.mark.parametrize(
    "status",
    [StepRuntimeStatus.PARTIAL, StepRuntimeStatus.CANCELLED],
)
def test_non_failed_error_attempt_mismatch_requires_reconciliation(
    status: StepRuntimeStatus,
) -> None:
    plan = _plan(_step("root", failure_policy=FailurePolicy.STOP))
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=status,
                error=_error("root", attempt=1),
            )
        }
    )

    _, _, result = _execute(
        plan,
        {"root": _state("root", attempt_count=1)},
        runner=runner,
    )

    assert result.run_state.status is WorkflowStatus.RUNNING
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.RUNNING
    assert result.completed_step_ids == ()
    assert result.directives[0].reason_code == (
        "RUNNER_ERROR_ATTEMPT_MISMATCH_EFFECT_UNKNOWN"
    )


@pytest.mark.parametrize(
    ("failure_policy", "expected_run_status", "expected_directive"),
    [
        (FailurePolicy.STOP, WorkflowStatus.FAILED, ExecutionDirectiveCode.STOPPED),
        (
            FailurePolicy.REPLAN,
            WorkflowStatus.REPLANNING,
            ExecutionDirectiveCode.REPLAN_REQUIRED,
        ),
        (
            FailurePolicy.ESCALATE,
            WorkflowStatus.ESCALATED,
            ExecutionDirectiveCode.ESCALATED,
        ),
    ],
)
def test_failed_result_applies_failure_policy_directive(
    failure_policy: FailurePolicy,
    expected_run_status: WorkflowStatus,
    expected_directive: ExecutionDirectiveCode,
) -> None:
    step = _step("root", failure_policy=failure_policy)
    plan = _plan(step)
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("root", retryable=False),
            )
        }
    )
    _, _, result = _execute(plan, {"root": _state("root")}, runner=runner)

    assert result.run_state.status is expected_run_status
    assert result.directives[0].code is expected_directive


def test_safe_retry_returns_directive_without_second_runner_call() -> None:
    step = _step("root", failure_policy=FailurePolicy.RETRY)
    plan = _plan(step)
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("root"),
            )
        }
    )
    _, runner, result = _execute(plan, {"root": _state("root")}, runner=runner)

    assert runner.calls == ["root"]
    assert result.directives[0].code is ExecutionDirectiveCode.RETRY_REQUIRED


def test_unknown_effect_requires_reconciliation_instead_of_retry() -> None:
    step = _step("root", failure_policy=FailurePolicy.RETRY)
    plan = _plan(step)
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("root", effect_state=EffectState.UNKNOWN),
            )
        }
    )
    _, _, result = _execute(plan, {"root": _state("root")}, runner=runner)

    assert result.directives[0].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert result.directives[0].reason_code == "UNKNOWN_EFFECT_REQUIRES_RECONCILIATION"


def test_permission_error_is_never_retry_required() -> None:
    step = _step("root", failure_policy=FailurePolicy.RETRY)
    plan = _plan(step)
    runner = FakeRunner(
        {
            "root": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("root", category=ErrorCategory.PERMISSION),
            )
        }
    )
    _, _, result = _execute(plan, {"root": _state("root")}, runner=runner)

    assert all(
        directive.code is not ExecutionDirectiveCode.RETRY_REQUIRED
        for directive in result.directives
    )


def test_prelaunch_deny_with_retry_policy_never_requests_retry() -> None:
    step = _step("root", failure_policy=FailurePolicy.RETRY)
    plan = _plan(step)
    guard = FakeGuard(
        {
            "root": PreLaunchDecision(
                PreLaunchDisposition.DENY,
                "PERMISSION_DENIED",
            )
        }
    )
    _, _, result = _execute(plan, {"root": _state("root")}, guard=guard)

    assert all(
        directive.code is not ExecutionDirectiveCode.RETRY_REQUIRED
        for directive in result.directives
    )


def test_expired_ready_step_fails_without_attempt_or_runner() -> None:
    step = _step("root", budget=BudgetSpec(deadline=NOW))
    plan = _plan(step)
    guard, runner, result = _execute(plan, {"root": _state("root")})

    state = result.run_state.step_states["root"]
    assert guard.calls == []
    assert runner.calls == []
    assert state.status is StepRuntimeStatus.FAILED
    assert state.attempt_count == 0
    assert state.block_reason == "deadline expired before launch"
    assert result.directives[0].code is ExecutionDirectiveCode.READY_DEADLINE_EXPIRED


def test_expired_ready_replan_preserves_not_started_run_timestamp() -> None:
    step = _step(
        "root",
        failure_policy=FailurePolicy.REPLAN,
        budget=BudgetSpec(deadline=NOW),
    )
    plan = _plan(step)

    _, runner, result = _execute(plan, {"root": _state("root")})

    assert runner.calls == []
    assert result.run_state.status is WorkflowStatus.REPLANNING
    assert result.run_state.started_at is None


def test_expired_run_deadline_without_running_step_fails_run() -> None:
    plan = _plan(
        _step("root"),
        budget_envelope=BudgetSpec(deadline=NOW),
    )
    _, runner, result = _execute(plan, {"root": _state("root")})

    assert runner.calls == []
    assert result.run_state.status is WorkflowStatus.FAILED
    assert result.run_state.ended_at == NOW
    assert result.run_state.stop_reason == "run deadline exceeded"
    assert result.directives[0].code is ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED


def test_timed_out_running_step_prevents_new_launch_and_requires_reconciliation() -> None:
    plan = _plan(_step("running"), _step("ready"))
    states = {
        "running": _state(
            "running",
            StepRuntimeStatus.RUNNING,
            attempt_count=1,
            started_at=Instant(NOW.value - timedelta(seconds=120)),
        ),
        "ready": _state("ready"),
    }
    _, runner, result = _execute(
        plan,
        states,
        status=WorkflowStatus.RUNNING,
    )

    assert runner.calls == []
    assert result.run_state.step_states["running"].status is StepRuntimeStatus.RUNNING
    assert result.directives[0].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert result.directives[0].reason_code == "RUNNING_STEP_TIMEOUT_EFFECT_UNKNOWN"


def test_expired_run_deadline_with_running_step_does_not_terminalize_blindly() -> None:
    plan = _plan(
        _step("running"),
        budget_envelope=BudgetSpec(deadline=NOW),
    )
    states = {
        "running": _state(
            "running",
            StepRuntimeStatus.RUNNING,
            attempt_count=1,
        )
    }
    _, runner, result = _execute(
        plan,
        states,
        status=WorkflowStatus.RUNNING,
    )

    assert runner.calls == []
    assert result.run_state.status is WorkflowStatus.RUNNING
    assert {directive.code for directive in result.directives} == {
        ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED,
        ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
    }


def test_runner_exception_keeps_running_and_does_not_expose_raw_text() -> None:
    plan = _plan(_step("root"), _step("second"))
    runner = FakeRunner(raise_for="root")
    _, runner, result = _execute(
        plan,
        {"root": _state("root"), "second": _state("second")},
        runner=runner,
    )

    assert runner.calls == ["root"]
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.RUNNING
    assert result.directives[0].reason_code == "RUNNER_EXCEPTION_EFFECT_UNKNOWN"
    assert "sensitive" not in repr(result)


def test_multiple_success_candidates_follow_scheduler_order() -> None:
    plan = _plan(_step("first"), _step("second"), _step("third"))
    _, runner, result = _execute(
        plan,
        {
            "third": _state("third"),
            "first": _state("first"),
            "second": _state("second"),
        },
    )

    assert runner.calls == ["first", "second", "third"]
    assert result.launched_step_ids == ("first", "second", "third")
    assert result.completed_step_ids == ("first", "second", "third")
    assert result.run_state.status is WorkflowStatus.RUNNING


@pytest.mark.parametrize(
    ("failure_policy", "expected_code"),
    [
        (FailurePolicy.STOP, ExecutionDirectiveCode.STOPPED),
        (FailurePolicy.REPLAN, ExecutionDirectiveCode.REPLAN_REQUIRED),
    ],
)
def test_stopping_failure_directive_prevents_later_candidate(
    failure_policy: FailurePolicy,
    expected_code: ExecutionDirectiveCode,
) -> None:
    first = _step("first", failure_policy=failure_policy)
    plan = _plan(first, _step("second"))
    runner = FakeRunner(
        {
            "first": StepExecutionResult(
                status=StepRuntimeStatus.FAILED,
                error=_error("first", retryable=False),
            )
        }
    )
    _, runner, result = _execute(
        plan,
        {"first": _state("first"), "second": _state("second")},
        runner=runner,
    )

    assert runner.calls == ["first"]
    assert result.directives[0].code is expected_code


def test_condition_required_allows_independent_candidate_to_run() -> None:
    plan = _plan(_step("first"), _step("second"))
    guard = FakeGuard(
        {
            "first": PreLaunchDecision(
                PreLaunchDisposition.CONDITION_REQUIRED,
                "TRUSTED_FACT_REQUIRED",
            )
        }
    )
    _, runner, result = _execute(
        plan,
        {"first": _state("first"), "second": _state("second")},
        guard=guard,
    )

    assert runner.calls == ["second"]
    assert result.launched_step_ids == ("second",)


def test_final_refresh_releases_dependent_without_second_wave_launch() -> None:
    plan = _plan(_step("first"), _step("second", depends_on=("first",)))
    _, runner, result = _execute(
        plan,
        {
            "first": _state("first"),
            "second": _state("second", StepRuntimeStatus.PENDING),
        },
    )

    assert runner.calls == ["first"]
    assert result.run_state.step_states["second"].status is StepRuntimeStatus.READY
    assert "second" not in result.launched_step_ids


def test_terminal_run_input_is_noop_without_runner() -> None:
    plan = _plan(_step("root"))
    initial_state = _run_state(
        plan,
        {"root": _state("root", StepRuntimeStatus.PENDING)},
        status=WorkflowStatus.FAILED,
    )
    guard, runner, result = _execute(
        plan,
        initial_state.step_states,
        status=initial_state.status,
    )

    assert guard.calls == []
    assert runner.calls == []
    assert result.run_state == initial_state
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.PENDING
    assert result.launched_step_ids == ()


def test_scheduler_parallel_overflow_error_is_propagated() -> None:
    steps = tuple(_step(f"step-{index}") for index in range(5))
    plan = _plan(*steps)
    states = {
        step.step_id: _state(
            step.step_id,
            StepRuntimeStatus.RUNNING,
            attempt_count=1,
        )
        for step in steps
    }

    with pytest.raises(SchedulerStateError, match="RUNNING steps"):
        _execute(plan, states, status=WorkflowStatus.RUNNING)
