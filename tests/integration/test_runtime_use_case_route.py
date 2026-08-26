from __future__ import annotations

from dataclasses import replace

from backend.agent_runtime.contracts import ExecutorKind, GateDecisionValue, StepKind
from backend.agent_runtime.policy import PolicyFacts
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


def test_wf0_use_case_routes_once_to_application_and_transfers_result_ref() -> None:
    step = make_step(StepKind.USE_CASE, "CAP-R01", ExecutorKind.APPLICATION)
    plan = make_plan(step, workflow_kind="WF-0")
    harness = make_runtime_harness(step)

    result = harness.runner.run(
        plan=plan,
        step=step,
        run_state=make_run_state(plan),
        attempt=1,
        now=NOW,
    )

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert result.result_refs == ("application-result-ref",)
    assert harness.inbound.calls == 1


def test_a02_ignores_forged_gate_fact_and_requires_engine_approval() -> None:
    step = make_step(StepKind.USE_CASE, "CAP-A02", ExecutorKind.APPLICATION)
    plan = make_plan(step, workflow_kind="WF-11", gate_refs=("gate-ref-1",))
    harness = make_runtime_harness(
        step,
        gate_values=(GateDecisionValue.REJECTED,),
        use_case_facts=PolicyFacts(matrix_gate_satisfied=True),
    )

    result = harness.runner.run(
        plan=plan,
        step=step,
        run_state=make_run_state(plan),
        attempt=1,
        now=NOW,
    )

    assert result.status is StepRuntimeStatus.FAILED
    assert harness.inbound.calls == 0


def test_a02_approved_gate_becomes_policy_fact_but_not_automatic_promotion() -> None:
    step = make_step(StepKind.USE_CASE, "CAP-A02", ExecutorKind.APPLICATION)
    plan = make_plan(step, workflow_kind="WF-11", gate_refs=("gate-ref-1",))
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
    assert harness.gate_source.calls == 1


def test_use_case_result_mismatch_after_inbound_requires_reconciliation() -> None:
    step = make_step(StepKind.USE_CASE, "CAP-R01", ExecutorKind.APPLICATION)
    plan = make_plan(step)
    harness = make_runtime_harness(step)
    result = harness.inbound.result
    harness.inbound.result = replace(
        result,
        meta=replace(result.meta, step_id="foreign-step"),
    )
    executor = PlanExecutor(DeterministicScheduler(), harness.guard, harness.runner)

    cycle = executor.execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=NOW,
    )

    assert cycle.directives[-1].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert harness.inbound.calls == 1
