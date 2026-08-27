from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    EffectState,
    ExecutorKind,
    StepKind,
)
from backend.agent_runtime.recovery import (
    BudgetState,
    CircuitBreakerEngine,
    EffectiveBudgetLimits,
    EffectLedgerError,
    EffectLedgerErrorCode,
    EffectLedgerLifecycle,
    IdempotencyPolicy,
    RecoveryAwareStepRunner,
    RecoveryCheckpoint,
    RecoveryCheckpointAction,
    RecoveryPreLaunchGuard,
    RecoveryRuntimeError,
    RecoveryRuntimeErrorCode,
    StateSnapshot,
    plan_fingerprint,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.runtime import (
    PreLaunchDisposition,
    StepRuntimeStatus,
)
from backend.agent_runtime.tools import ToolRoutingError
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


def _budget(run_id: str, now: Instant = NOW) -> BudgetState:
    return BudgetState(
        run_id=run_id,
        version=1,
        limits=EffectiveBudgetLimits(
            max_retries_per_envelope=3,
            max_retries_per_step=2,
        ),
        created_at=now,
        updated_at=now,
    )


def _running_state(plan: object, run_state: object) -> object:
    from backend.agent_runtime.runtime import Plan, RunState

    assert isinstance(plan, Plan)
    assert isinstance(run_state, RunState)
    step_id = plan.steps[0].step_id
    state = replace(
        run_state.step_states[step_id],
        status=StepRuntimeStatus.RUNNING,
        started_at=NOW,
        attempt_count=1,
    )
    return replace(run_state, step_states={step_id: state})


def test_tool_context_builds_stable_identity_without_raw_key() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    recovery_resolver = RecordingRecoveryRuntimeResolver()

    first = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=recovery_resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    second = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=recovery_resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    assert first.identity == second.identity
    assert first.identity is not None
    assert first.identity.target_id == "tool.render_document"
    assert "idem-tool" not in repr(first)


def test_prelaunch_enforces_backoff_before_attempt_increment() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    retry_state = replace(
        run_state.step_states[step.step_id],
        attempt_count=1,
    )
    run_state = replace(run_state, step_states={step.step_id: retry_state})
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None
    snapshot_store = InMemoryStateSnapshotStore()
    not_before = Instant(NOW.value + timedelta(seconds=30))
    snapshot_store.save(
        snapshot=StateSnapshot.capture(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            sequence=1,
            run_id=plan.run_id,
            plan_id=plan.plan_id,
            plan_version=plan.plan_version,
            plan_fingerprint=plan_fingerprint(plan),
            run_state=run_state,
            budget_state=_budget(plan.run_id),
            effect_ledger_refs=(),
            captured_at=NOW,
            recovery_checkpoint=RecoveryCheckpoint(
                RecoveryCheckpointAction.RETRY_SCHEDULED,
                step.step_id,
                context.identity.record_id,
                3,
                2,
                1,
                not_before,
            ),
        ),
        expected_previous_sequence=None,
    )
    guard = RecoveryPreLaunchGuard(
        inner=harness.guard,
        recovery_resolver=resolver,
        circuit_engine=CircuitBreakerEngine(
            InMemoryCircuitBreakerStore(), CONFIG
        ),
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    decision = guard.check(plan=plan, step=step, run_state=run_state, now=NOW)

    assert decision.disposition is PreLaunchDisposition.CONDITION_REQUIRED
    assert decision.reason_code == "RECOVERY_BACKOFF_PENDING"
    assert run_state.step_states[step.step_id].attempt_count == 1


def test_prelaunch_open_circuit_blocks_without_call() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    open_state = make_open_state(
        key=context.circuit_key,
        opened_at=NOW,
        open_until=Instant(NOW.value + timedelta(minutes=1)),
    )
    guard = RecoveryPreLaunchGuard(
        inner=harness.guard,
        recovery_resolver=resolver,
        circuit_engine=CircuitBreakerEngine(
            InMemoryCircuitBreakerStore(initial_states=(open_state,)), CONFIG
        ),
        snapshot_store=InMemoryStateSnapshotStore(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    decision = guard.check(plan=plan, step=step, run_state=run_state, now=NOW)

    assert decision.disposition is PreLaunchDisposition.CONDITION_REQUIRED
    assert harness.tool_executor.calls == []


def test_initial_tool_call_is_reserved_started_and_committed_once() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    ready = make_run_state(plan, ready_step_id=step.step_id)
    run_state = _running_state(plan, ready)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    ledger = InMemoryEffectLedgerFake()
    budget_port = InMemoryBudgetStatePort(_budget(plan.run_id))
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=budget_port,
        circuit_engine=CircuitBreakerEngine(
            InMemoryCircuitBreakerStore(), CONFIG
        ),
        snapshot_store=InMemoryStateSnapshotStore(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    result = runner.run(
        plan=plan,
        step=step,
        run_state=run_state,
        attempt=1,
        now=NOW,
    )
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None
    record = ledger.get(record_id=context.identity.record_id)

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert harness.tool_executor.calls != []
    assert len(harness.tool_executor.calls) == 1
    assert record is not None
    assert record.lifecycle is EffectLedgerLifecycle.FINALIZED
    assert record.effect_state is EffectState.COMMITTED
    assert record.attempt == 1


def test_non_idempotent_application_route_does_not_create_ledger_identity() -> None:
    step = make_step(StepKind.USE_CASE, "CAP-R01", ExecutorKind.APPLICATION)
    plan = make_plan(step)
    ready = make_run_state(plan, ready_step_id=step.step_id)
    run_state = _running_state(plan, ready)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    ledger = InMemoryEffectLedgerFake()
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(_budget(plan.run_id)),
        circuit_engine=CircuitBreakerEngine(
            InMemoryCircuitBreakerStore(), CONFIG
        ),
        snapshot_store=InMemoryStateSnapshotStore(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    result = runner.run(
        plan=plan,
        step=step,
        run_state=run_state,
        attempt=1,
        now=NOW,
    )
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert context.identity is None
    assert harness.inbound.calls == 1


@pytest.mark.parametrize("capability", ["CAP-A02", "CAP-A03"])
def test_idempotent_application_actions_finalize_committed(capability: str) -> None:
    step = make_step(StepKind.USE_CASE, capability, ExecutorKind.APPLICATION)
    plan = make_plan(
        step,
        gate_refs=(("gate-ref-1",) if capability == "CAP-A02" else ()),
    )
    ready = make_run_state(plan, ready_step_id=step.step_id)
    run_state = _running_state(plan, ready)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    ledger = InMemoryEffectLedgerFake()
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(_budget(plan.run_id)),
        circuit_engine=CircuitBreakerEngine(
            InMemoryCircuitBreakerStore(), CONFIG
        ),
        snapshot_store=InMemoryStateSnapshotStore(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    result = runner.run(
        plan=plan,
        step=step,
        run_state=run_state,
        attempt=1,
        now=NOW,
    )
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None
    record = ledger.get(record_id=context.identity.record_id)

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert harness.inbound.calls == 1
    assert record is not None
    assert record.effect_state is EffectState.COMMITTED


def test_protected_runner_exception_finalizes_unknown_before_reraise() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    ready = make_run_state(plan, ready_step_id=step.step_id)
    run_state = _running_state(plan, ready)
    harness = make_runtime_harness(step, tool_executor_error=RuntimeError("boom"))
    resolver = RecordingRecoveryRuntimeResolver()
    ledger = InMemoryEffectLedgerFake()
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(_budget(plan.run_id)),
        circuit_engine=CircuitBreakerEngine(
            InMemoryCircuitBreakerStore(), CONFIG
        ),
        snapshot_store=InMemoryStateSnapshotStore(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None

    with pytest.raises(ToolRoutingError):
        runner.run(
            plan=plan,
            step=step,
            run_state=run_state,
            attempt=1,
            now=NOW,
        )
    record = ledger.get(record_id=context.identity.record_id)

    assert record is not None
    assert record.lifecycle is EffectLedgerLifecycle.FINALIZED
    assert record.effect_state is EffectState.UNKNOWN
    assert record.retry_failure_facts is not None
    assert record.retry_failure_facts.error_code == "PROTECTED_CALL_EXCEPTION"


def test_post_call_ledger_conflict_never_replays_or_converts_effect_to_none() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    ready = make_run_state(plan, ready_step_id=step.step_id)
    run_state = _running_state(plan, ready)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    policy = IdempotencyPolicy()

    def validate_cas(*, current: object, expected_version: int, replacement: object) -> None:
        from backend.agent_runtime.recovery import EffectLedgerRecord

        assert isinstance(current, EffectLedgerRecord)
        assert isinstance(replacement, EffectLedgerRecord)
        if replacement.lifecycle is EffectLedgerLifecycle.FINALIZED:
            raise EffectLedgerError(EffectLedgerErrorCode.VERSION_CONFLICT)
        policy.validate_compare_and_set(
            current=current,
            expected_version=expected_version,
            replacement=replacement,
        )

    ledger = InMemoryEffectLedgerFake(cas_validator=validate_cas)
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(_budget(plan.run_id)),
        circuit_engine=CircuitBreakerEngine(
            InMemoryCircuitBreakerStore(), CONFIG
        ),
        snapshot_store=InMemoryStateSnapshotStore(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None

    with pytest.raises(RecoveryRuntimeError) as raised:
        runner.run(
            plan=plan,
            step=step,
            run_state=run_state,
            attempt=1,
            now=NOW,
        )
    record = ledger.get(record_id=context.identity.record_id)

    assert raised.value.code is RecoveryRuntimeErrorCode.LEDGER_FINALIZATION_CONFLICT
    assert len(harness.tool_executor.calls) == 1
    assert record is not None
    assert record.lifecycle is EffectLedgerLifecycle.IN_PROGRESS
    assert record.effect_state is EffectState.UNKNOWN
