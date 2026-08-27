from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY
from backend.agent_runtime.contracts import ExecutorKind, StepKind
from backend.agent_runtime.recovery import (
    BudgetState,
    CircuitBreakerEngine,
    CircuitBreakerStatus,
    EffectiveBudgetLimits,
    RecoveryAwareStepRunner,
    RecoveryPreLaunchGuard,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.runtime import PreLaunchDisposition, StepRuntimeStatus
from backend.shared_kernel.time import Instant
from tests.support.budget_state_fakes import InMemoryBudgetStatePort
from tests.support.circuit_breaker_fakes import (
    CONFIG,
    InMemoryCircuitBreakerStore,
    make_open_state,
)
from tests.support.effect_ledger_fakes import InMemoryEffectLedgerFake
from tests.support.runtime_recovery_fakes import RecordingRecoveryRuntimeResolver
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)
from tests.support.snapshot_store_fakes import InMemoryStateSnapshotStore


def _budget(run_id: str) -> BudgetState:
    return BudgetState(
        run_id=run_id,
        version=1,
        limits=EffectiveBudgetLimits(max_retries_per_step=2),
        created_at=NOW,
        updated_at=NOW,
    )


def test_half_open_preflight_is_read_only_and_runner_owns_exact_lease() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    ready_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=ready_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    opened_at = Instant(NOW.value - timedelta(minutes=1))
    open_state = make_open_state(
        key=context.circuit_key,
        opened_at=opened_at,
        open_until=Instant(NOW.value - timedelta(seconds=1)),
    )
    circuit_store = InMemoryCircuitBreakerStore(initial_states=(open_state,))
    circuit_engine = CircuitBreakerEngine(circuit_store, CONFIG)
    snapshot_store = InMemoryStateSnapshotStore()
    guard = RecoveryPreLaunchGuard(
        inner=harness.guard,
        recovery_resolver=resolver,
        circuit_engine=circuit_engine,
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    decision = guard.check(
        plan=plan,
        step=step,
        run_state=ready_state,
        now=NOW,
    )

    assert decision.disposition is PreLaunchDisposition.ALLOW
    assert circuit_store.cas_calls == 0

    running = replace(
        ready_state.step_states[step.step_id],
        status=StepRuntimeStatus.RUNNING,
        started_at=NOW,
        attempt_count=1,
    )
    run_state = replace(ready_state, step_states={step.step_id: running})
    ledger = InMemoryEffectLedgerFake()
    result = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(_budget(plan.run_id)),
        circuit_engine=circuit_engine,
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    ).run(
        plan=plan,
        step=step,
        run_state=run_state,
        attempt=1,
        now=NOW,
    )
    current = circuit_store.get(circuit_id=context.circuit_key.circuit_id)

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert len(harness.tool_executor.calls) == 1
    assert circuit_store.cas_calls == 2
    assert current is not None
    assert current.status is CircuitBreakerStatus.HALF_OPEN
    assert current.half_open_lease is None
    assert current.half_open_successes == 1


def test_binding_change_creates_a_different_circuit_without_changing_intent_identity() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    first_resolver = RecordingRecoveryRuntimeResolver()
    second_resolver = RecordingRecoveryRuntimeResolver()
    second_resolver.binding_override = "binding.tool.v2"

    first = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=first_resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    second = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=second_resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    assert first.identity == second.identity
    assert first.circuit_key != second.circuit_key
    assert first.circuit_key.circuit_id != second.circuit_key.circuit_id
