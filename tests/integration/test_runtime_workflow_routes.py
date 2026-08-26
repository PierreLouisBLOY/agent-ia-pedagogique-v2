from __future__ import annotations

import pytest

from backend.agent_runtime.contracts import ExecutorKind, StepKind
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    ExecutionDirectiveCode,
    PlanExecutor,
    StepRuntimeStatus,
)
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)


@pytest.mark.parametrize(
    ("workflow", "capability", "executor", "port_index"),
    [
        ("WF-6", "CAP-E01", ExecutorKind.AG_02, 0),
        ("WF-6", "CAP-G01", ExecutorKind.AG_03, 1),
        ("WF-6", "CAP-V01", ExecutorKind.AG_04, 2),
        ("WF-7", "CAP-G03", ExecutorKind.AG_03, 1),
    ],
)
def test_agent_workflow_stages_keep_exact_opaque_bindings(
    workflow: str,
    capability: str,
    executor: ExecutorKind,
    port_index: int,
) -> None:
    step = make_step(StepKind.AGENT, capability, executor)
    plan = make_plan(step, workflow_kind=workflow)
    harness = make_runtime_harness(step)

    result = harness.runner.run(
        plan=plan,
        step=step,
        run_state=make_run_state(plan),
        attempt=1,
        now=NOW,
    )

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert harness.agent_ports[port_index].calls == [step.step_id]
    assert sum(len(port.calls) for port in harness.agent_ports) == 1


@pytest.mark.parametrize("workflow", ["WF-2", "WF-4", "WF-5", "WF-6", "WF-11"])
def test_validation_stage_uses_real_application_route(workflow: str) -> None:
    step = make_step(StepKind.USE_CASE, "CAP-A01", ExecutorKind.APPLICATION)
    plan = make_plan(step, workflow_kind=workflow)
    harness = make_runtime_harness(step)

    result = harness.runner.run(
        plan=plan,
        step=step,
        run_state=make_run_state(plan),
        attempt=1,
        now=NOW,
    )

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert harness.inbound.calls == 1


def test_agent_port_exception_is_not_downgraded_to_no_effect() -> None:
    step = make_step(StepKind.AGENT, "CAP-G01", ExecutorKind.AG_03)
    plan = make_plan(step, workflow_kind="WF-6")
    harness = make_runtime_harness(
        step,
        agent_error=RuntimeError("agent effect is unknown"),
    )
    executor = PlanExecutor(DeterministicScheduler(), harness.guard, harness.runner)

    cycle = executor.execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=NOW,
    )

    assert cycle.directives[-1].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert harness.agent_ports[1].calls == [step.step_id]
