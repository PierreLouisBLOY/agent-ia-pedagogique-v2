from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.contracts import (
    ExecutorKind,
    GateDecisionValue,
    StepKind,
)
from backend.agent_runtime.policy import PolicyFacts
from backend.agent_runtime.runtime import PreLaunchDisposition
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)


@pytest.mark.parametrize(
    ("gate_value", "expected"),
    [
        (None, PreLaunchDisposition.WAITING_GATE),
        (GateDecisionValue.DEFERRED, PreLaunchDisposition.WAITING_GATE),
        (GateDecisionValue.REJECTED, PreLaunchDisposition.DENY),
        (GateDecisionValue.APPROVED, PreLaunchDisposition.ALLOW),
    ],
)
def test_gate_prelaunch_mapping_is_closed(
    gate_value: GateDecisionValue | None,
    expected: PreLaunchDisposition,
) -> None:
    step = make_step(StepKind.GATE, "CAP-O05", ExecutorKind.RUNTIME)
    plan = make_plan(step, gate_refs=("gate-ref-1",))
    harness = make_runtime_harness(step, gate_values=(gate_value,))

    decision = harness.guard.check(
        plan=plan, step=step, run_state=make_run_state(plan), now=NOW
    )

    assert decision.disposition is expected
    assert harness.gate_source.calls == 1


def test_a02_uses_the_same_external_gate_mapping() -> None:
    step = make_step(StepKind.USE_CASE, "CAP-A02", ExecutorKind.APPLICATION)
    plan = make_plan(step, gate_refs=("gate-ref-1",))
    harness = make_runtime_harness(step, gate_values=(None,))

    decision = harness.guard.check(
        plan=plan, step=step, run_state=make_run_state(plan), now=NOW
    )

    assert decision.disposition is PreLaunchDisposition.WAITING_GATE
    assert harness.inbound.calls == 0


def test_tool_condition_is_reported_without_sandbox_or_executor_call() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(step, tool_facts=PolicyFacts())

    decision = harness.guard.check(
        plan=plan, step=step, run_state=make_run_state(plan), now=NOW
    )

    assert decision.disposition is PreLaunchDisposition.CONDITION_REQUIRED
    assert harness.tool_executor.calls == []


def test_forged_kind_executor_is_denied_before_resolution() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    forged = replace(step, executor=replace(step.executor, kind=ExecutorKind.APPLICATION))
    plan = make_plan(forged)
    harness = make_runtime_harness(step)

    decision = harness.guard.check(
        plan=plan, step=forged, run_state=make_run_state(plan), now=NOW
    )

    assert decision.disposition is PreLaunchDisposition.DENY
    assert harness.resolver.calls == []
