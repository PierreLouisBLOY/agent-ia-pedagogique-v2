from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from backend.agent_runtime.contracts import StepSpec, WorkflowStatus
from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.scheduling.deadlines import effective_step_deadline
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus
from backend.shared_kernel.time import Instant


class DependencyDisposition(StrEnum):
    SATISFIED = "SATISFIED"
    WAITING = "WAITING"
    BLOCKING = "BLOCKING"
    UNRESOLVED = "UNRESOLVED"


_DEPENDENCY_DISPOSITIONS = {
    StepRuntimeStatus.SUCCEEDED: DependencyDisposition.SATISFIED,
    StepRuntimeStatus.FAILED: DependencyDisposition.BLOCKING,
    StepRuntimeStatus.CANCELLED: DependencyDisposition.BLOCKING,
    StepRuntimeStatus.BLOCKED: DependencyDisposition.BLOCKING,
    StepRuntimeStatus.PENDING: DependencyDisposition.WAITING,
    StepRuntimeStatus.READY: DependencyDisposition.WAITING,
    StepRuntimeStatus.RUNNING: DependencyDisposition.WAITING,
    StepRuntimeStatus.PARTIAL: DependencyDisposition.UNRESOLVED,
    StepRuntimeStatus.SKIPPED: DependencyDisposition.UNRESOLVED,
}

_LAUNCHABLE_RUN_STATUSES = frozenset(
    {WorkflowStatus.PLANNED, WorkflowStatus.RUNNING}
)


class SchedulerStateError(RuntimeError):
    """Raised when a Plan and RunState do not describe the same technical run."""


def dependency_disposition(status: StepRuntimeStatus) -> DependencyDisposition:
    if not isinstance(status, StepRuntimeStatus):
        raise TypeError("status must be a StepRuntimeStatus")
    return _DEPENDENCY_DISPOSITIONS[status]


@dataclass(frozen=True, slots=True)
class SchedulingDecision:
    run_state: RunState
    launch_candidate_ids: tuple[str, ...]
    timed_out_running_step_ids: tuple[str, ...] = ()
    expired_ready_step_ids: tuple[str, ...] = ()
    run_deadline_exceeded: bool = False
    available_slots: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.run_state, RunState):
            raise TypeError("run_state must be a RunState")
        for field_name in (
            "launch_candidate_ids",
            "timed_out_running_step_ids",
            "expired_ready_step_ids",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise TypeError(f"{field_name} must be a tuple")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique ids")
            if any(step_id not in self.run_state.step_states for step_id in values):
                raise ValueError(f"{field_name} ids must belong to run_state")
        self._require_status(
            self.launch_candidate_ids,
            StepRuntimeStatus.READY,
            "launch candidates",
        )
        self._require_status(
            self.timed_out_running_step_ids,
            StepRuntimeStatus.RUNNING,
            "timed out steps",
        )
        self._require_status(
            self.expired_ready_step_ids,
            StepRuntimeStatus.READY,
            "expired ready steps",
        )
        if set(self.launch_candidate_ids).intersection(self.expired_ready_step_ids):
            raise ValueError("launch candidates and expired ready steps must be disjoint")
        if type(self.run_deadline_exceeded) is not bool:
            raise TypeError("run_deadline_exceeded must be a bool")
        if type(self.available_slots) is not int:
            raise TypeError("available_slots must be an integer")
        if self.available_slots < 0:
            raise ValueError("available_slots must be >= 0")
        if len(self.launch_candidate_ids) > self.available_slots:
            raise ValueError("launch candidates must not exceed available_slots")

    def _require_status(
        self,
        step_ids: tuple[str, ...],
        expected_status: StepRuntimeStatus,
        label: str,
    ) -> None:
        if any(
            self.run_state.step_states[step_id].status is not expected_status
            for step_id in step_ids
        ):
            raise ValueError(f"{label} must have status {expected_status.value}")


def refresh_schedulable_state(plan: Plan, run_state: RunState) -> RunState:
    """Derive only PENDING -> READY/BLOCKED transitions to a fixed point."""
    if not isinstance(plan, Plan):
        raise TypeError("plan must be a Plan")
    if not isinstance(run_state, RunState):
        raise TypeError("run_state must be a RunState")
    _require_plan_state_coherence(plan, run_state)

    states = dict(run_state.step_states)
    changed_any = False
    while True:
        changed_this_pass = False
        for step in plan.steps:
            state = states[step.step_id]
            if state.status is not StepRuntimeStatus.PENDING:
                continue
            try:
                dependency_states = tuple(states[item] for item in step.depends_on)
            except KeyError as error:
                raise SchedulerStateError(
                    f"step {step.step_id} has an unknown dependency"
                ) from error
            blocking_ids = tuple(
                dependency.step_id
                for dependency in dependency_states
                if dependency_disposition(dependency.status)
                is DependencyDisposition.BLOCKING
            )
            if blocking_ids:
                states[step.step_id] = replace(
                    state,
                    status=StepRuntimeStatus.BLOCKED,
                    block_reason="blocking dependencies: " + ",".join(blocking_ids),
                )
                changed_this_pass = True
                changed_any = True
                continue
            if all(
                dependency_disposition(dependency.status)
                is DependencyDisposition.SATISFIED
                for dependency in dependency_states
            ):
                states[step.step_id] = replace(
                    state,
                    status=StepRuntimeStatus.READY,
                )
                changed_this_pass = True
                changed_any = True
        if not changed_this_pass:
            break

    if not changed_any:
        return run_state
    return replace(run_state, step_states=states)


@dataclass(frozen=True, slots=True)
class DeterministicScheduler:
    runtime_policy: AgentRuntimePolicy = BASELINE_AGENT_RUNTIME_POLICY

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_policy, AgentRuntimePolicy):
            raise TypeError("runtime_policy must be an AgentRuntimePolicy")

    def schedule(
        self,
        *,
        plan: Plan,
        run_state: RunState,
        now: Instant,
    ) -> SchedulingDecision:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run_state, RunState):
            raise TypeError("run_state must be a RunState")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")
        _require_plan_state_coherence(plan, run_state)
        refreshed_state = refresh_schedulable_state(plan, run_state)

        running_count = sum(
            state.status is StepRuntimeStatus.RUNNING
            for state in refreshed_state.step_states.values()
        )
        if running_count > self.runtime_policy.max_parallel_steps:
            raise SchedulerStateError(
                f"run_state has {running_count} RUNNING steps; max_parallel_steps is "
                f"{self.runtime_policy.max_parallel_steps}"
            )
        available_slots = self.runtime_policy.max_parallel_steps - running_count
        timed_out_running_step_ids = tuple(
            step.step_id
            for step in plan.steps
            if refreshed_state.step_states[step.step_id].status
            is StepRuntimeStatus.RUNNING
            and now.value
            >= effective_step_deadline(
                step,
                refreshed_state.step_states[step.step_id],
                self.runtime_policy,
            ).value
        )
        expired_ready_step_ids = tuple(
            step.step_id
            for step in plan.steps
            if refreshed_state.step_states[step.step_id].status is StepRuntimeStatus.READY
            and _ready_deadline_expired(step, now)
        )
        run_deadline_exceeded = _absolute_run_deadline_exceeded(plan, now)

        launch_candidate_ids: tuple[str, ...] = ()
        if (
            refreshed_state.status in _LAUNCHABLE_RUN_STATUSES
            and not run_deadline_exceeded
            and available_slots > 0
        ):
            expired_ids = set(expired_ready_step_ids)
            launch_candidate_ids = tuple(
                step.step_id
                for step in plan.steps
                if refreshed_state.step_states[step.step_id].status
                is StepRuntimeStatus.READY
                and step.step_id not in expired_ids
            )[:available_slots]

        return SchedulingDecision(
            run_state=refreshed_state,
            launch_candidate_ids=launch_candidate_ids,
            timed_out_running_step_ids=timed_out_running_step_ids,
            expired_ready_step_ids=expired_ready_step_ids,
            run_deadline_exceeded=run_deadline_exceeded,
            available_slots=available_slots,
        )


def _require_plan_state_coherence(plan: Plan, run_state: RunState) -> None:
    comparisons = (
        (plan.run_id, run_state.run_id, "run_id"),
        (plan.plan_id, run_state.plan_id, "plan_id"),
        (plan.plan_version, run_state.plan_version, "plan_version"),
        (plan.workflow_kind, run_state.workflow_kind, "workflow_kind"),
    )
    for plan_value, state_value, field_name in comparisons:
        if plan_value != state_value:
            raise SchedulerStateError(f"plan and run_state {field_name} mismatch")
    plan_step_ids = tuple(step.step_id for step in plan.steps)
    state_step_ids = tuple(run_state.step_states)
    if len(plan_step_ids) != len(state_step_ids) or set(plan_step_ids) != set(
        state_step_ids
    ):
        raise SchedulerStateError("plan and run_state step ids mismatch")


def _ready_deadline_expired(step: StepSpec, now: Instant) -> bool:
    if step.budget is None:
        return False
    if step.budget.max_runtime_seconds == 0:
        return True
    return step.budget.deadline is not None and now.value >= step.budget.deadline.value


def _absolute_run_deadline_exceeded(plan: Plan, now: Instant) -> bool:
    return bool(
        plan.budget_envelope is not None
        and plan.budget_envelope.deadline is not None
        and now.value >= plan.budget_envelope.deadline.value
    )
