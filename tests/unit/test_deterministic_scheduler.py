from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    BudgetSpec,
    ExecutorKind,
    ExecutorRef,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.policy import BASELINE_AGENT_RUNTIME_POLICY
from backend.agent_runtime.runtime import (
    DependencyDisposition,
    DeterministicScheduler,
    Plan,
    RunState,
    SchedulerStateError,
    SchedulingDecision,
    StepRuntimeStatus,
    StepState,
    dependency_disposition,
    effective_step_deadline,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))
RUN_STARTED = Instant(NOW.value - timedelta(seconds=30))


def _step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    kind: StepKind = StepKind.USE_CASE,
    executor: ExecutorKind = ExecutorKind.APPLICATION,
    capability: str | None = "CAP-R01",
    budget: BudgetSpec | None = None,
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=kind,
        capability_id=CapabilityId(capability) if capability is not None else None,
        executor=ExecutorRef(executor),
        objective=f"Execute {step_id}",
        depends_on=depends_on,
        permission_scope_ref=(
            "scope-1"
            if kind in {StepKind.AGENT, StepKind.USE_CASE, StepKind.TOOL}
            else None
        ),
        budget=budget,
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
        objective="Schedule deterministic work",
        success_criteria={"complete": True},
        workflow_kind="opaque-workflow",
        steps=steps,
        budget_envelope=budget_envelope,
        stop_conditions={"failure": "stop"},
    )


def _state(step_id: str, status: StepRuntimeStatus) -> StepState:
    if status is StepRuntimeStatus.RUNNING:
        return StepState(step_id=step_id, status=status, started_at=RUN_STARTED)
    if status in {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.CANCELLED,
        StepRuntimeStatus.SKIPPED,
    }:
        return StepState(step_id=step_id, status=status, ended_at=NOW)
    if status is StepRuntimeStatus.FAILED:
        return StepState(
            step_id=step_id,
            status=status,
            ended_at=NOW,
            error_ref="error-1",
        )
    if status is StepRuntimeStatus.BLOCKED:
        return StepState(step_id=step_id, status=status, block_reason="blocked upstream")
    return StepState(step_id=step_id, status=status)


def _run_state(
    plan: Plan,
    states: Mapping[str, StepState],
    *,
    status: WorkflowStatus = WorkflowStatus.PLANNED,
    run_id: str | None = None,
    plan_id: str | None = None,
    plan_version: int | None = None,
    workflow_kind: str | None = None,
    started_at: Instant | None = None,
) -> RunState:
    active = status in {
        WorkflowStatus.RUNNING,
        WorkflowStatus.WAITING_GATE,
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
        run_id=run_id or plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=workflow_kind or plan.workflow_kind,
        plan_id=plan_id or plan.plan_id,
        plan_version=plan_version or plan.plan_version,
        status=status,
        step_states=states,
        started_at=(started_at or RUN_STARTED) if active else None,
        ended_at=NOW if terminal else None,
        stop_reason="stopped" if stop_required else None,
    )


def _schedule(
    plan: Plan,
    states: Mapping[str, StepState],
    *,
    status: WorkflowStatus = WorkflowStatus.PLANNED,
    now: Instant = NOW,
    scheduler: DeterministicScheduler | None = None,
    started_at: Instant | None = None,
) -> SchedulingDecision:
    run_state = _run_state(plan, states, status=status, started_at=started_at)
    return (scheduler or DeterministicScheduler()).schedule(
        plan=plan,
        run_state=run_state,
        now=now,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (StepRuntimeStatus.SUCCEEDED, DependencyDisposition.SATISFIED),
        (StepRuntimeStatus.FAILED, DependencyDisposition.BLOCKING),
        (StepRuntimeStatus.CANCELLED, DependencyDisposition.BLOCKING),
        (StepRuntimeStatus.BLOCKED, DependencyDisposition.BLOCKING),
        (StepRuntimeStatus.PENDING, DependencyDisposition.WAITING),
        (StepRuntimeStatus.READY, DependencyDisposition.WAITING),
        (StepRuntimeStatus.RUNNING, DependencyDisposition.WAITING),
        (StepRuntimeStatus.PARTIAL, DependencyDisposition.UNRESOLVED),
        (StepRuntimeStatus.SKIPPED, DependencyDisposition.UNRESOLVED),
    ],
)
def test_dependency_disposition_mapping_is_exact(
    status: StepRuntimeStatus,
    expected: DependencyDisposition,
) -> None:
    assert dependency_disposition(status) is expected


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"run_id": "other-run"}, "run_id"),
        ({"plan_id": "other-plan"}, "plan_id"),
        ({"plan_version": 2}, "plan_version"),
        ({"workflow_kind": "other-workflow"}, "workflow_kind"),
    ],
)
def test_scheduler_rejects_plan_state_identity_mismatch(
    override: dict[str, object],
    message: str,
) -> None:
    plan = _plan(_step("root"))
    run_state = _run_state(
        plan,
        {"root": _state("root", StepRuntimeStatus.PENDING)},
        **override,  # type: ignore[arg-type]
    )

    with pytest.raises(SchedulerStateError, match=message):
        DeterministicScheduler().schedule(plan=plan, run_state=run_state, now=NOW)


def test_scheduler_rejects_step_set_mismatch() -> None:
    plan = _plan(_step("first"), _step("second"))
    run_state = _run_state(
        plan,
        {"first": _state("first", StepRuntimeStatus.PENDING)},
    )

    with pytest.raises(SchedulerStateError, match="step ids"):
        DeterministicScheduler().schedule(plan=plan, run_state=run_state, now=NOW)


def test_root_pending_becomes_ready() -> None:
    plan = _plan(_step("root"))
    decision = _schedule(
        plan,
        {"root": _state("root", StepRuntimeStatus.PENDING)},
    )

    assert decision.run_state.step_states["root"].status is StepRuntimeStatus.READY


def test_succeeded_dependency_makes_dependent_ready() -> None:
    plan = _plan(_step("root"), _step("child", depends_on=("root",)))
    decision = _schedule(
        plan,
        {
            "root": _state("root", StepRuntimeStatus.SUCCEEDED),
            "child": _state("child", StepRuntimeStatus.PENDING),
        },
    )

    assert decision.run_state.step_states["child"].status is StepRuntimeStatus.READY


@pytest.mark.parametrize(
    "dependency_status",
    [
        StepRuntimeStatus.PENDING,
        StepRuntimeStatus.READY,
        StepRuntimeStatus.RUNNING,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.SKIPPED,
    ],
)
def test_waiting_or_unresolved_dependency_keeps_dependent_pending(
    dependency_status: StepRuntimeStatus,
) -> None:
    plan = _plan(_step("root"), _step("child", depends_on=("root",)))
    decision = _schedule(
        plan,
        {
            "root": _state("root", dependency_status),
            "child": _state("child", StepRuntimeStatus.PENDING),
        },
    )

    assert decision.run_state.step_states["child"].status is StepRuntimeStatus.PENDING


@pytest.mark.parametrize(
    "dependency_status",
    [
        StepRuntimeStatus.FAILED,
        StepRuntimeStatus.CANCELLED,
        StepRuntimeStatus.BLOCKED,
    ],
)
def test_blocking_dependency_blocks_pending_dependent(
    dependency_status: StepRuntimeStatus,
) -> None:
    plan = _plan(_step("root"), _step("child", depends_on=("root",)))
    decision = _schedule(
        plan,
        {
            "root": _state("root", dependency_status),
            "child": _state("child", StepRuntimeStatus.PENDING),
        },
    )

    child = decision.run_state.step_states["child"]
    assert child.status is StepRuntimeStatus.BLOCKED
    assert child.block_reason == "blocking dependencies: root"
    assert child.started_at is None
    assert child.ended_at is None


def test_blocking_propagates_to_fixed_point_in_reverse_plan_order() -> None:
    plan = _plan(
        _step("c", depends_on=("b",)),
        _step("b", depends_on=("a",)),
        _step("a"),
    )
    decision = _schedule(
        plan,
        {
            "c": _state("c", StepRuntimeStatus.PENDING),
            "b": _state("b", StepRuntimeStatus.PENDING),
            "a": _state("a", StepRuntimeStatus.FAILED),
        },
    )

    assert decision.run_state.step_states["b"].status is StepRuntimeStatus.BLOCKED
    assert decision.run_state.step_states["c"].status is StepRuntimeStatus.BLOCKED
    assert decision.run_state.step_states["b"].block_reason == "blocking dependencies: a"
    assert decision.run_state.step_states["c"].block_reason == "blocking dependencies: b"


def test_block_reason_preserves_dependency_order() -> None:
    plan = _plan(
        _step("a"),
        _step("b"),
        _step("child", depends_on=("b", "a")),
    )
    decision = _schedule(
        plan,
        {
            "a": _state("a", StepRuntimeStatus.FAILED),
            "b": _state("b", StepRuntimeStatus.CANCELLED),
            "child": _state("child", StepRuntimeStatus.PENDING),
        },
    )

    assert (
        decision.run_state.step_states["child"].block_reason
        == "blocking dependencies: b,a"
    )


@pytest.mark.parametrize(
    "status",
    [
        StepRuntimeStatus.READY,
        StepRuntimeStatus.RUNNING,
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.FAILED,
        StepRuntimeStatus.CANCELLED,
        StepRuntimeStatus.BLOCKED,
        StepRuntimeStatus.SKIPPED,
    ],
)
def test_scheduler_does_not_change_non_pending_step_state(
    status: StepRuntimeStatus,
) -> None:
    plan = _plan(_step("step"))
    original = _state("step", status)
    decision = _schedule(plan, {"step": original})

    assert decision.run_state.step_states["step"] == original


def test_scheduler_does_not_mutate_step_spec() -> None:
    step = _step("root")
    plan = _plan(step)

    _schedule(plan, {"root": _state("root", StepRuntimeStatus.PENDING)})

    assert plan.steps[0] is step
    with pytest.raises(FrozenInstanceError):
        step.objective = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "status",
    [WorkflowStatus.PLANNED, WorkflowStatus.RUNNING],
)
def test_launchable_run_status_selects_ready_candidate(status: WorkflowStatus) -> None:
    plan = _plan(_step("root"))
    decision = _schedule(
        plan,
        {"root": _state("root", StepRuntimeStatus.READY)},
        status=status,
    )

    assert decision.launch_candidate_ids == ("root",)
    assert decision.run_state.step_states["root"].status is StepRuntimeStatus.READY


@pytest.mark.parametrize(
    "status",
    [WorkflowStatus.WAITING_GATE, WorkflowStatus.REPLANNING],
)
def test_suspended_run_status_selects_no_candidate(status: WorkflowStatus) -> None:
    plan = _plan(_step("root"))
    decision = _schedule(
        plan,
        {"root": _state("root", StepRuntimeStatus.READY)},
        status=status,
    )

    assert decision.launch_candidate_ids == ()


@pytest.mark.parametrize(
    "status",
    [
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    ],
)
def test_terminal_run_status_selects_no_candidate(status: WorkflowStatus) -> None:
    plan = _plan(_step("root"))
    decision = _schedule(
        plan,
        {"root": _state("root", StepRuntimeStatus.READY)},
        status=status,
    )

    assert decision.launch_candidate_ids == ()


def test_baseline_parallel_limit_selects_at_most_four_candidates() -> None:
    steps = tuple(_step(f"step-{index}") for index in range(5))
    plan = _plan(*steps)
    decision = _schedule(
        plan,
        {
            step.step_id: _state(step.step_id, StepRuntimeStatus.READY)
            for step in steps
        },
    )

    assert decision.available_slots == 4
    assert decision.launch_candidate_ids == ("step-0", "step-1", "step-2", "step-3")


def test_two_running_steps_leave_two_launch_slots() -> None:
    steps = tuple(_step(f"step-{index}") for index in range(5))
    plan = _plan(*steps)
    decision = _schedule(
        plan,
        {
            "step-0": _state("step-0", StepRuntimeStatus.RUNNING),
            "step-1": _state("step-1", StepRuntimeStatus.RUNNING),
            "step-2": _state("step-2", StepRuntimeStatus.READY),
            "step-3": _state("step-3", StepRuntimeStatus.READY),
            "step-4": _state("step-4", StepRuntimeStatus.READY),
        },
        status=WorkflowStatus.RUNNING,
    )

    assert decision.available_slots == 2
    assert decision.launch_candidate_ids == ("step-2", "step-3")


def test_four_running_steps_leave_no_launch_slot() -> None:
    steps = tuple(_step(f"step-{index}") for index in range(5))
    plan = _plan(*steps)
    states = {
        step.step_id: _state(
            step.step_id,
            StepRuntimeStatus.RUNNING if index < 4 else StepRuntimeStatus.READY,
        )
        for index, step in enumerate(steps)
    }
    decision = _schedule(plan, states, status=WorkflowStatus.RUNNING)

    assert decision.available_slots == 0
    assert decision.launch_candidate_ids == ()


def test_baseline_parallel_overflow_fails_closed_with_limit_in_message() -> None:
    steps = tuple(_step(f"step-{index}") for index in range(5))
    plan = _plan(*steps)
    states = {
        step.step_id: _state(step.step_id, StepRuntimeStatus.RUNNING)
        for step in steps
    }

    with pytest.raises(SchedulerStateError, match=r"5 RUNNING steps.*4"):
        _schedule(plan, states, status=WorkflowStatus.RUNNING)


def test_custom_parallel_overflow_fails_closed() -> None:
    steps = (_step("first"), _step("second"))
    plan = _plan(*steps)
    policy = replace(BASELINE_AGENT_RUNTIME_POLICY, max_parallel_steps=1)
    states = {
        step.step_id: _state(step.step_id, StepRuntimeStatus.RUNNING)
        for step in steps
    }

    with pytest.raises(SchedulerStateError, match=r"2 RUNNING steps.*1"):
        _schedule(
            plan,
            states,
            status=WorkflowStatus.RUNNING,
            scheduler=DeterministicScheduler(policy),
        )


def test_custom_parallel_limit_is_applied() -> None:
    steps = (_step("first"), _step("second"))
    plan = _plan(*steps)
    policy = replace(BASELINE_AGENT_RUNTIME_POLICY, max_parallel_steps=1)
    decision = _schedule(
        plan,
        {step.step_id: _state(step.step_id, StepRuntimeStatus.READY) for step in steps},
        scheduler=DeterministicScheduler(policy),
    )

    assert decision.available_slots == 1
    assert decision.launch_candidate_ids == ("first",)


def test_zero_parallel_limit_selects_no_candidate() -> None:
    plan = _plan(_step("root"))
    policy = replace(BASELINE_AGENT_RUNTIME_POLICY, max_parallel_steps=0)
    decision = _schedule(
        plan,
        {"root": _state("root", StepRuntimeStatus.READY)},
        scheduler=DeterministicScheduler(policy),
    )

    assert decision.available_slots == 0
    assert decision.launch_candidate_ids == ()


def test_candidate_order_follows_plan_not_state_mapping() -> None:
    plan = _plan(_step("first"), _step("second"), _step("third"))
    decision = _schedule(
        plan,
        {
            "third": _state("third", StepRuntimeStatus.READY),
            "first": _state("first", StepRuntimeStatus.READY),
            "second": _state("second", StepRuntimeStatus.READY),
        },
    )

    assert decision.launch_candidate_ids == ("first", "second", "third")


def test_running_default_deadline_is_not_timed_out_before_120_seconds() -> None:
    step = _step("running")
    plan = _plan(step)
    started = Instant(NOW.value - timedelta(seconds=119))
    state = StepState(
        step_id="running",
        status=StepRuntimeStatus.RUNNING,
        started_at=started,
    )
    decision = _schedule(
        plan,
        {"running": state},
        status=WorkflowStatus.RUNNING,
    )

    assert effective_step_deadline(step, state).value == started.value + timedelta(seconds=120)
    assert decision.timed_out_running_step_ids == ()


def test_running_step_times_out_at_default_deadline() -> None:
    step = _step("running")
    plan = _plan(step)
    state = StepState(
        step_id="running",
        status=StepRuntimeStatus.RUNNING,
        started_at=Instant(NOW.value - timedelta(seconds=120)),
    )
    decision = _schedule(
        plan,
        {"running": state},
        status=WorkflowStatus.RUNNING,
    )

    assert decision.timed_out_running_step_ids == ("running",)
    assert decision.run_state.step_states["running"].status is StepRuntimeStatus.RUNNING


def test_step_max_runtime_deadline_precedes_default() -> None:
    step = _step("running", budget=BudgetSpec(max_runtime_seconds=30))
    plan = _plan(step)
    state = StepState(
        step_id="running",
        status=StepRuntimeStatus.RUNNING,
        started_at=Instant(NOW.value - timedelta(seconds=30)),
    )
    decision = _schedule(
        plan,
        {"running": state},
        status=WorkflowStatus.RUNNING,
    )

    assert effective_step_deadline(step, state).value == NOW.value
    assert decision.timed_out_running_step_ids == ("running",)


def test_absolute_step_deadline_can_precede_runtime_deadlines() -> None:
    absolute = Instant(NOW.value - timedelta(seconds=1))
    step = _step(
        "running",
        budget=BudgetSpec(max_runtime_seconds=90, deadline=absolute),
    )
    plan = _plan(step)
    state = StepState(
        step_id="running",
        status=StepRuntimeStatus.RUNNING,
        started_at=RUN_STARTED,
    )
    decision = _schedule(
        plan,
        {"running": state},
        status=WorkflowStatus.RUNNING,
    )

    assert effective_step_deadline(step, state) is absolute
    assert decision.timed_out_running_step_ids == ("running",)


def test_expired_ready_absolute_deadline_is_signalled_and_excluded() -> None:
    step = _step("ready", budget=BudgetSpec(deadline=NOW))
    plan = _plan(step)
    decision = _schedule(
        plan,
        {"ready": _state("ready", StepRuntimeStatus.READY)},
    )

    assert decision.expired_ready_step_ids == ("ready",)
    assert decision.launch_candidate_ids == ()
    assert decision.run_state.step_states["ready"].status is StepRuntimeStatus.READY


def test_zero_runtime_ready_step_is_signalled_and_excluded() -> None:
    step = _step("ready", budget=BudgetSpec(max_runtime_seconds=0))
    plan = _plan(step)
    decision = _schedule(
        plan,
        {"ready": _state("ready", StepRuntimeStatus.READY)},
    )

    assert decision.expired_ready_step_ids == ("ready",)
    assert decision.launch_candidate_ids == ()


def test_expired_absolute_plan_deadline_blocks_all_candidates() -> None:
    plan = _plan(
        _step("ready"),
        budget_envelope=BudgetSpec(deadline=NOW),
    )
    decision = _schedule(
        plan,
        {"ready": _state("ready", StepRuntimeStatus.READY)},
    )

    assert decision.run_deadline_exceeded is True
    assert decision.launch_candidate_ids == ()


def test_default_run_deadline_is_not_derived_from_wall_clock_when_gate_pause_enabled() -> None:
    plan = _plan(_step("ready"))
    old_start = Instant(
        NOW.value
        - timedelta(seconds=BASELINE_AGENT_RUNTIME_POLICY.run_deadline_default_seconds + 1)
    )
    decision = _schedule(
        plan,
        {"ready": _state("ready", StepRuntimeStatus.READY)},
        status=WorkflowStatus.RUNNING,
        started_at=old_start,
    )

    assert BASELINE_AGENT_RUNTIME_POLICY.gate_wait_pauses_run_deadline is True
    assert decision.run_deadline_exceeded is False
    assert decision.launch_candidate_ids == ("ready",)


@pytest.mark.parametrize(
    ("dependency_status", "expected_status"),
    [
        (StepRuntimeStatus.SUCCEEDED, StepRuntimeStatus.READY),
        (StepRuntimeStatus.FAILED, StepRuntimeStatus.BLOCKED),
        (StepRuntimeStatus.PARTIAL, StepRuntimeStatus.PENDING),
    ],
)
def test_join_uses_generic_dependency_semantics(
    dependency_status: StepRuntimeStatus,
    expected_status: StepRuntimeStatus,
) -> None:
    plan = _plan(
        _step("branch"),
        _step(
            "join",
            depends_on=("branch",),
            kind=StepKind.JOIN,
            executor=ExecutorKind.RUNTIME,
            capability="CAP-O04",
        ),
    )
    decision = _schedule(
        plan,
        {
            "branch": _state("branch", dependency_status),
            "join": _state("join", StepRuntimeStatus.PENDING),
        },
    )

    assert decision.run_state.step_states["join"].status is expected_status


def test_decision_collections_are_consistent_with_returned_state() -> None:
    plan = _plan(
        _step("candidate"),
        _step("expired", budget=BudgetSpec(max_runtime_seconds=0)),
        _step("running"),
    )
    running = StepState(
        step_id="running",
        status=StepRuntimeStatus.RUNNING,
        started_at=Instant(NOW.value - timedelta(seconds=120)),
    )
    decision = _schedule(
        plan,
        {
            "candidate": _state("candidate", StepRuntimeStatus.READY),
            "expired": _state("expired", StepRuntimeStatus.READY),
            "running": running,
        },
        status=WorkflowStatus.RUNNING,
    )

    assert decision.launch_candidate_ids == ("candidate",)
    assert decision.expired_ready_step_ids == ("expired",)
    assert decision.timed_out_running_step_ids == ("running",)
    assert set(decision.launch_candidate_ids).isdisjoint(decision.expired_ready_step_ids)


def test_scheduling_decision_rejects_candidate_with_non_ready_status() -> None:
    plan = _plan(_step("step"))
    run_state = _run_state(
        plan,
        {"step": _state("step", StepRuntimeStatus.PENDING)},
    )

    with pytest.raises(ValueError, match="launch candidates"):
        SchedulingDecision(
            run_state=run_state,
            launch_candidate_ids=("step",),
            available_slots=1,
        )
