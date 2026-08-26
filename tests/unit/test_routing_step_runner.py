from __future__ import annotations

from backend.agent_runtime.contracts import ExecutorKind, GateDecisionValue, StepKind
from backend.agent_runtime.runtime import StepRuntimeStatus
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)


def test_join_and_decision_use_only_runtime_control_delegate() -> None:
    for kind, capability in (
        (StepKind.JOIN, "CAP-O03"),
        (StepKind.DECISION, "CAP-O04"),
    ):
        step = make_step(kind, capability, ExecutorKind.RUNTIME)
        plan = make_plan(step)
        harness = make_runtime_harness(step)

        result = harness.runner.run(
            plan=plan,
            step=step,
            run_state=make_run_state(plan),
            attempt=1,
            now=NOW,
        )

        assert result.status is StepRuntimeStatus.SUCCEEDED
        assert harness.runtime_control.calls == [kind]
        assert harness.resolver.calls == []


def test_gate_change_between_prelaunch_and_runner_fails_closed() -> None:
    step = make_step(StepKind.GATE, "CAP-O05", ExecutorKind.RUNTIME)
    plan = make_plan(step, gate_refs=("gate-ref-1",))
    harness = make_runtime_harness(
        step,
        gate_values=(GateDecisionValue.APPROVED, GateDecisionValue.REJECTED),
    )
    state = make_run_state(plan)

    assert harness.guard.check(
        plan=plan, step=step, run_state=state, now=NOW
    ).disposition.value == "ALLOW"
    result = harness.runner.run(
        plan=plan, step=step, run_state=state, attempt=1, now=NOW
    )

    assert result.status is StepRuntimeStatus.FAILED
    assert result.error is not None
    assert result.error.effect_state.value == "none"


def test_direct_runner_rejects_malformed_shape_without_boundary_call() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.APPLICATION)
    plan = make_plan(step)
    harness = make_runtime_harness(
        make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    )

    result = harness.runner.run(
        plan=plan,
        step=step,
        run_state=make_run_state(plan),
        attempt=1,
        now=NOW,
    )

    assert result.status is StepRuntimeStatus.FAILED
    assert harness.tool_executor.calls == []
