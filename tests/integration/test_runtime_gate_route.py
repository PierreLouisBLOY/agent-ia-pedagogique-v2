from __future__ import annotations

from dataclasses import replace

from backend.agent_runtime.contracts import (
    ExecutorKind,
    GateDecisionValue,
    StepKind,
    WorkflowStatus,
)
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    ExecutionDirectiveCode,
    PlanExecutor,
    StepRuntimeStatus,
)
from backend.agent_runtime.runtime.routing import ResolvedGateInput
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)


def test_waiting_gate_stops_before_attempt_and_runner() -> None:
    step = make_step(StepKind.GATE, "CAP-O05", ExecutorKind.RUNTIME)
    plan = make_plan(step, workflow_kind="WF-10", gate_refs=("gate-ref-1",))
    harness = make_runtime_harness(step, gate_values=(None,))
    executor = PlanExecutor(DeterministicScheduler(), harness.guard, harness.runner)

    cycle = executor.execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=NOW,
    )

    state = cycle.run_state.step_states[step.step_id]
    assert cycle.run_state.status is WorkflowStatus.WAITING_GATE
    assert state.attempt_count == 0
    assert state.status is StepRuntimeStatus.READY
    assert cycle.directives[-1].code is ExecutionDirectiveCode.WAITING_GATE
    assert harness.gate_source.calls == 1


def test_approved_gate_is_revalidated_and_decision_ref_reaches_step_state() -> None:
    step = make_step(StepKind.GATE, "CAP-O05", ExecutorKind.RUNTIME)
    plan = make_plan(step, workflow_kind="WF-10", gate_refs=("gate-ref-1",))
    harness = make_runtime_harness(
        step,
        gate_values=(GateDecisionValue.APPROVED, GateDecisionValue.APPROVED),
    )
    executor = PlanExecutor(DeterministicScheduler(), harness.guard, harness.runner)

    cycle = executor.execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=NOW,
    )

    state = cycle.run_state.step_states[step.step_id]
    assert state.status is StepRuntimeStatus.SUCCEEDED
    assert state.result_refs == ("gate-decision-ref",)
    assert state.attempt_count == 1
    assert harness.gate_source.calls == 2


def test_gate_ref_outside_plan_is_denied_without_source_call() -> None:
    step = make_step(StepKind.GATE, "CAP-O05", ExecutorKind.RUNTIME)
    plan = make_plan(step, gate_refs=("gate-ref-1",))
    harness = make_runtime_harness(step)
    resolved = harness.resolver.gate_input
    assert type(resolved) is ResolvedGateInput
    harness.resolver.gate_input = replace(resolved, gate_ref="foreign-gate-ref")

    decision = harness.guard.check(
        plan=plan, step=step, run_state=make_run_state(plan), now=NOW
    )

    assert decision.disposition.value == "DENY"
    assert harness.gate_source.calls == 0
