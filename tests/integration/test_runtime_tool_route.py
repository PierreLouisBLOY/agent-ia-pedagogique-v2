from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.contracts import ExecutorKind, StepKind
from backend.agent_runtime.policy import ConditionalResolution, PolicyFacts
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    ExecutionDirectiveCode,
    PlanExecutor,
    StepRuntimeStatus,
)
from backend.agent_runtime.runtime.routing import ResolvedToolInput
from backend.agent_runtime.sandbox import SandboxRootRef
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)


@pytest.mark.parametrize("capability", ["CAP-T02", "CAP-T03"])
def test_explicit_tool_plan_routes_through_policy_sandbox_and_exact_executor(
    capability: str,
) -> None:
    step = make_step(StepKind.TOOL, capability, ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(
        step,
        tool_facts=PolicyFacts(conditional_resolution=ConditionalResolution.ALLOW),
    )

    result = harness.runner.run(
        plan=plan,
        step=step,
        run_state=make_run_state(plan),
        attempt=1,
        now=NOW,
    )

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert result.result_refs == ("tool-artifact-ref",)
    assert len(harness.tool_executor.calls) == 1


def test_foreign_sandbox_root_is_rejected_before_tool_call() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(step)
    resolved = harness.resolver.tool_input
    assert type(resolved) is ResolvedToolInput
    harness.resolver.tool_input = replace(
        resolved,
        context=replace(
            resolved.context,
            root_ref=SandboxRootRef("run-foreign", "root-routing"),
        ),
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


def test_tool_executor_failure_reaches_plan_executor_as_unknown_effect() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(
        step,
        tool_executor_error=RuntimeError("post-call failure"),
    )
    executor = PlanExecutor(
        DeterministicScheduler(), harness.guard, harness.runner
    )

    cycle = executor.execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=NOW,
    )

    assert cycle.directives[-1].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert cycle.run_state.step_states[step.step_id].status is StepRuntimeStatus.RUNNING
    assert len(harness.tool_executor.calls) == 1
