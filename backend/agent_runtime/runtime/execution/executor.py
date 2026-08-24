from __future__ import annotations

from dataclasses import dataclass, replace

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    FailurePolicy,
    RecommendedAction,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.runtime.execution.directives import (
    ExecutionDirective,
    ExecutionDirectiveCode,
)
from backend.agent_runtime.runtime.execution.prelaunch import (
    PreLaunchDecision,
    PreLaunchDisposition,
    PreLaunchGuard,
)
from backend.agent_runtime.runtime.execution.runner import (
    StepExecutionResult,
    StepRunner,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.scheduling import (
    DeterministicScheduler,
    SchedulingDecision,
    refresh_schedulable_state,
)
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus, StepState
from backend.agent_runtime.runtime.state._workflow_statuses import (
    TERMINAL_WORKFLOW_STATUSES,
)
from backend.shared_kernel.time import Instant

_RETRY_FORBIDDEN_CATEGORIES = frozenset(
    {
        ErrorCategory.DOMAIN,
        ErrorCategory.PERMISSION,
        ErrorCategory.GATE,
        ErrorCategory.BUDGET,
        ErrorCategory.CANCELLED,
        ErrorCategory.UNKNOWN,
    }
)

_STOP_CYCLE_CODES = frozenset(
    {
        ExecutionDirectiveCode.WAITING_GATE,
        ExecutionDirectiveCode.RETRY_REQUIRED,
        ExecutionDirectiveCode.REPLAN_REQUIRED,
        ExecutionDirectiveCode.ESCALATED,
        ExecutionDirectiveCode.STOPPED,
        ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
    }
)


@dataclass(frozen=True, slots=True)
class ExecutionCycleResult:
    run_state: RunState
    launched_step_ids: tuple[str, ...] = ()
    completed_step_ids: tuple[str, ...] = ()
    directives: tuple[ExecutionDirective, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.run_state, RunState):
            raise TypeError("run_state must be a RunState")
        for field_name in ("launched_step_ids", "completed_step_ids"):
            step_ids = getattr(self, field_name)
            if not isinstance(step_ids, tuple):
                raise TypeError(f"{field_name} must be a tuple")
            if len(set(step_ids)) != len(step_ids):
                raise ValueError(f"{field_name} must contain unique ids")
            if any(step_id not in self.run_state.step_states for step_id in step_ids):
                raise ValueError(f"{field_name} ids must belong to run_state")
        if not set(self.completed_step_ids).issubset(self.launched_step_ids):
            raise ValueError("completed_step_ids must be a subset of launched_step_ids")
        if any(
            self.run_state.step_states[step_id].attempt_count < 1
            for step_id in self.launched_step_ids
        ):
            raise ValueError("launched steps must have attempt_count >= 1")
        if not isinstance(self.directives, tuple):
            raise TypeError("directives must be a tuple")
        if any(not isinstance(item, ExecutionDirective) for item in self.directives):
            raise TypeError("directives must contain ExecutionDirective values")
        if any(
            item.step_id is not None and item.step_id not in self.run_state.step_states
            for item in self.directives
        ):
            raise ValueError("directive step ids must belong to run_state")


@dataclass(frozen=True, slots=True)
class PlanExecutor:
    scheduler: DeterministicScheduler
    prelaunch_guard: PreLaunchGuard
    runner: StepRunner

    def __post_init__(self) -> None:
        if not isinstance(self.scheduler, DeterministicScheduler):
            raise TypeError("scheduler must be a DeterministicScheduler")
        if not isinstance(self.prelaunch_guard, PreLaunchGuard):
            raise TypeError("prelaunch_guard must implement PreLaunchGuard")
        if not isinstance(self.runner, StepRunner):
            raise TypeError("runner must implement StepRunner")

    def execute_cycle(
        self,
        *,
        plan: Plan,
        run_state: RunState,
        now: Instant,
    ) -> ExecutionCycleResult:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run_state, RunState):
            raise TypeError("run_state must be a RunState")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")

        scheduling = self.scheduler.schedule(plan=plan, run_state=run_state, now=now)
        if run_state.status in TERMINAL_WORKFLOW_STATUSES:
            return ExecutionCycleResult(run_state=run_state)
        deadline_result = _consume_deadline_signals(plan, scheduling, now)
        if deadline_result is not None:
            return deadline_result

        current_state = scheduling.run_state
        launched: list[str] = []
        completed: list[str] = []
        directives: list[ExecutionDirective] = []
        steps_by_id = {step.step_id: step for step in plan.steps}

        for step_id in scheduling.launch_candidate_ids:
            step = steps_by_id[step_id]
            guard_decision = self.prelaunch_guard.check(
                plan=plan,
                step=step,
                run_state=current_state,
                now=now,
            )
            if not isinstance(guard_decision, PreLaunchDecision):
                raise TypeError("prelaunch_guard must return PreLaunchDecision")

            if guard_decision.disposition is PreLaunchDisposition.WAITING_GATE:
                current_state = replace(
                    current_state,
                    status=WorkflowStatus.WAITING_GATE,
                    ended_at=None,
                    stop_reason=None,
                )
                directives.append(
                    ExecutionDirective(
                        code=ExecutionDirectiveCode.WAITING_GATE,
                        step_id=step_id,
                        reason_code=guard_decision.reason_code,
                    )
                )
                break
            if guard_decision.disposition is PreLaunchDisposition.CONDITION_REQUIRED:
                directives.append(
                    ExecutionDirective(
                        code=ExecutionDirectiveCode.CONDITION_REQUIRED,
                        step_id=step_id,
                        reason_code=guard_decision.reason_code,
                    )
                )
                continue
            if guard_decision.disposition is PreLaunchDisposition.DENY:
                denied_state = replace(
                    current_state.step_states[step_id],
                    status=StepRuntimeStatus.BLOCKED,
                    block_reason=f"prelaunch denied: {guard_decision.reason_code}",
                )
                current_state = _replace_step_state(current_state, denied_state)
                directives.append(
                    ExecutionDirective(
                        code=ExecutionDirectiveCode.PRELAUNCH_DENIED,
                        step_id=step_id,
                        reason_code=guard_decision.reason_code,
                    )
                )
                current_state, policy_directive = _apply_failure_policy(
                    run_state=current_state,
                    step=step,
                    error=None,
                    now=now,
                    reason_code="PRELAUNCH_DENIED_NO_RETRY",
                )
                directives.append(policy_directive)
                if policy_directive.code in _STOP_CYCLE_CODES:
                    break
                continue

            running_step = replace(
                current_state.step_states[step_id],
                status=StepRuntimeStatus.RUNNING,
                started_at=now,
                ended_at=None,
                attempt_count=current_state.step_states[step_id].attempt_count + 1,
                block_reason=None,
                error_ref=None,
            )
            current_state = _replace_step_state(current_state, running_step)
            if current_state.status is WorkflowStatus.PLANNED:
                current_state = replace(
                    current_state,
                    status=WorkflowStatus.RUNNING,
                    started_at=now,
                    ended_at=None,
                    stop_reason=None,
                )
            launched.append(step_id)

            try:
                runner_result = self.runner.run(
                    plan=plan,
                    step=step,
                    run_state=current_state,
                    attempt=running_step.attempt_count,
                    now=now,
                )
            except Exception:
                directives.append(
                    ExecutionDirective(
                        code=ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
                        step_id=step_id,
                        reason_code="RUNNER_EXCEPTION_EFFECT_UNKNOWN",
                    )
                )
                break

            if not isinstance(runner_result, StepExecutionResult):
                directives.append(
                    ExecutionDirective(
                        code=ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
                        step_id=step_id,
                        reason_code="RUNNER_RESULT_CONTRACT_INVALID_EFFECT_UNKNOWN",
                    )
                )
                break
            if runner_result.error is not None and runner_result.error.step_id != step_id:
                directives.append(
                    ExecutionDirective(
                        code=ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
                        step_id=step_id,
                        reason_code="RUNNER_ERROR_STEP_MISMATCH_EFFECT_UNKNOWN",
                    )
                )
                break
            if (
                runner_result.error is not None
                and runner_result.error.attempt != running_step.attempt_count
            ):
                directives.append(
                    ExecutionDirective(
                        code=ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
                        step_id=step_id,
                        reason_code="RUNNER_ERROR_ATTEMPT_MISMATCH_EFFECT_UNKNOWN",
                    )
                )
                break

            current_state, result_directive = _apply_runner_result(
                run_state=current_state,
                step=step,
                result=runner_result,
                now=now,
            )
            completed.append(step_id)
            directives.append(result_directive)
            if result_directive.code in _STOP_CYCLE_CODES:
                break

        if current_state.status not in TERMINAL_WORKFLOW_STATUSES:
            current_state = refresh_schedulable_state(plan, current_state)
        return ExecutionCycleResult(
            run_state=current_state,
            launched_step_ids=tuple(launched),
            completed_step_ids=tuple(completed),
            directives=tuple(directives),
        )


def _consume_deadline_signals(
    plan: Plan,
    scheduling: SchedulingDecision,
    now: Instant,
) -> ExecutionCycleResult | None:
    current_state = scheduling.run_state
    directives: list[ExecutionDirective] = [
        ExecutionDirective(
            code=ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
            step_id=step_id,
            reason_code="RUNNING_STEP_TIMEOUT_EFFECT_UNKNOWN",
        )
        for step_id in scheduling.timed_out_running_step_ids
    ]
    reconciled_ids = set(scheduling.timed_out_running_step_ids)

    if scheduling.run_deadline_exceeded:
        directives.append(
            ExecutionDirective(
                code=ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED,
                reason_code="RUN_DEADLINE_EXCEEDED",
            )
        )
        running_ids = current_state.current_step_ids
        if running_ids:
            for step_id in running_ids:
                if step_id not in reconciled_ids:
                    directives.append(
                        ExecutionDirective(
                            code=ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
                            step_id=step_id,
                            reason_code="RUN_DEADLINE_RUNNING_EFFECT_UNKNOWN",
                        )
                    )
            return ExecutionCycleResult(run_state=current_state, directives=tuple(directives))
        current_state = replace(
            current_state,
            status=WorkflowStatus.FAILED,
            ended_at=now,
            stop_reason="run deadline exceeded",
        )
        return ExecutionCycleResult(run_state=current_state, directives=tuple(directives))

    if scheduling.timed_out_running_step_ids:
        return ExecutionCycleResult(run_state=current_state, directives=tuple(directives))

    if not scheduling.expired_ready_step_ids:
        return None

    steps_by_id = {step.step_id: step for step in plan.steps}
    expired_steps: list[StepSpec] = []
    for step_id in scheduling.expired_ready_step_ids:
        expired_step_state = replace(
            current_state.step_states[step_id],
            status=StepRuntimeStatus.FAILED,
            ended_at=now,
            error_ref=None,
            block_reason="deadline expired before launch",
        )
        current_state = _replace_step_state(current_state, expired_step_state)
        expired_steps.append(steps_by_id[step_id])
        directives.append(
            ExecutionDirective(
                code=ExecutionDirectiveCode.READY_DEADLINE_EXPIRED,
                step_id=step_id,
                reason_code="READY_DEADLINE_EXPIRED",
            )
        )

    for step in expired_steps:
        current_state, policy_directive = _apply_failure_policy(
            run_state=current_state,
            step=step,
            error=None,
            now=now,
            reason_code="DEADLINE_EXPIRED_NO_RETRY",
        )
        directives.append(policy_directive)
        if policy_directive.code in _STOP_CYCLE_CODES:
            break
    return ExecutionCycleResult(run_state=current_state, directives=tuple(directives))


def _apply_runner_result(
    *,
    run_state: RunState,
    step: StepSpec,
    result: StepExecutionResult,
    now: Instant,
) -> tuple[RunState, ExecutionDirective]:
    block_reason: str | None = None
    if result.status is StepRuntimeStatus.PARTIAL and result.error is not None:
        block_reason = f"partial result: {result.error.error_code}"
    elif result.status is StepRuntimeStatus.FAILED:
        if result.error is None:
            raise TypeError("FAILED runner result requires error")
        block_reason = f"execution failed: {result.error.error_code}"
    elif result.status is StepRuntimeStatus.CANCELLED:
        block_reason = (
            f"execution cancelled: {result.error.error_code}"
            if result.error is not None
            else "execution cancelled"
        )

    terminal_step = replace(
        run_state.step_states[step.step_id],
        status=result.status,
        ended_at=now,
        result_refs=result.result_refs,
        metrics=result.metrics,
        error_ref=None,
        block_reason=block_reason,
    )
    updated_state = _replace_step_state(run_state, terminal_step)

    if result.status is StepRuntimeStatus.SUCCEEDED:
        return updated_state, ExecutionDirective(
            code=ExecutionDirectiveCode.CONTINUE,
            step_id=step.step_id,
        )
    if result.status is StepRuntimeStatus.PARTIAL:
        return updated_state, ExecutionDirective(
            code=ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION,
            step_id=step.step_id,
            reason_code="PARTIAL_RESULT_REQUIRES_POLICY",
        )
    return _apply_failure_policy(
        run_state=updated_state,
        step=step,
        error=result.error,
        now=now,
        reason_code=(
            "EXECUTION_FAILED"
            if result.status is StepRuntimeStatus.FAILED
            else "EXECUTION_CANCELLED"
        ),
    )


def _apply_failure_policy(
    *,
    run_state: RunState,
    step: StepSpec,
    error: ErrorEnvelope | None,
    now: Instant,
    reason_code: str,
) -> tuple[RunState, ExecutionDirective]:
    if error is not None and error.effect_state is EffectState.UNKNOWN:
        return run_state, ExecutionDirective(
            code=ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
            step_id=step.step_id,
            reason_code="UNKNOWN_EFFECT_REQUIRES_RECONCILIATION",
        )

    if step.failure_policy is FailurePolicy.RETRY:
        retry_allowed = bool(
            error is not None
            and error.retryable
            and error.effect_state is EffectState.NONE
            and error.category not in _RETRY_FORBIDDEN_CATEGORIES
        )
        if retry_allowed:
            return run_state, ExecutionDirective(
                code=ExecutionDirectiveCode.RETRY_REQUIRED,
                step_id=step.step_id,
                reason_code="SAFE_RETRY_REQUIRES_COORDINATION",
            )
        if error is not None and error.recommended_action is RecommendedAction.REPLAN:
            return _replanning_state(run_state, now), ExecutionDirective(
                code=ExecutionDirectiveCode.REPLAN_REQUIRED,
                step_id=step.step_id,
                reason_code="RETRY_REFUSED_REPLAN_RECOMMENDED",
            )
        stop_code = (
            "DEADLINE_EXPIRED_NO_RETRY"
            if reason_code == "DEADLINE_EXPIRED_NO_RETRY"
            else reason_code
        )
        return _failed_state(run_state, step, now, stop_code), ExecutionDirective(
            code=ExecutionDirectiveCode.STOPPED,
            step_id=step.step_id,
            reason_code=stop_code,
        )

    if step.failure_policy is FailurePolicy.REPLAN:
        return _replanning_state(run_state, now), ExecutionDirective(
            code=ExecutionDirectiveCode.REPLAN_REQUIRED,
            step_id=step.step_id,
            reason_code=reason_code,
        )
    if step.failure_policy is FailurePolicy.ESCALATE:
        escalated = replace(
            run_state,
            status=WorkflowStatus.ESCALATED,
            ended_at=now,
            stop_reason=f"step {step.step_id} escalated: {reason_code}",
        )
        return escalated, ExecutionDirective(
            code=ExecutionDirectiveCode.ESCALATED,
            step_id=step.step_id,
            reason_code=reason_code,
        )
    failed = _failed_state(run_state, step, now, reason_code)
    return failed, ExecutionDirective(
        code=ExecutionDirectiveCode.STOPPED,
        step_id=step.step_id,
        reason_code=reason_code,
    )


def _replace_step_state(run_state: RunState, step_state: StepState) -> RunState:
    states = dict(run_state.step_states)
    states[step_state.step_id] = step_state
    return replace(run_state, step_states=states)


def _replanning_state(run_state: RunState, now: Instant) -> RunState:
    return replace(
        run_state,
        status=WorkflowStatus.REPLANNING,
        started_at=run_state.started_at,
        ended_at=None,
        stop_reason=None,
    )


def _failed_state(
    run_state: RunState,
    step: StepSpec,
    now: Instant,
    reason_code: str,
) -> RunState:
    return replace(
        run_state,
        status=WorkflowStatus.FAILED,
        ended_at=now,
        stop_reason=f"step {step.step_id} stopped: {reason_code}",
    )
