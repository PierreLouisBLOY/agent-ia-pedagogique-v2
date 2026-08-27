from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    EffectState,
    ExecutorKind,
    StepKind,
)
from backend.agent_runtime.orchestration.coordination import (
    CoordinationAction,
    CoordinationDecision,
)
from backend.agent_runtime.recovery import (
    BudgetState,
    CircuitBreakerEngine,
    EffectiveBudgetLimits,
    EffectLedgerLifecycle,
    EffectLedgerSnapshotRef,
    EffectReconciliationEngine,
    IdempotencyPolicy,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    RecoveryAction,
    RecoveryAwareStepRunner,
    RecoveryCoordinator,
    StateSnapshot,
    plan_fingerprint,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.runtime import ExecutionDirectiveCode, StepRuntimeStatus
from backend.shared_kernel.time import Instant
from tests.support.budget_state_fakes import InMemoryBudgetStatePort
from tests.support.circuit_breaker_fakes import (
    CONFIG,
    InMemoryCircuitBreakerStore,
)
from tests.support.effect_ledger_fakes import InMemoryEffectLedgerFake
from tests.support.reconciliation_fakes import (
    RecordingApplicationEffectProbe,
    RecordingToolEffectProbe,
)
from tests.support.runtime_recovery_fakes import (
    PortBackedRecoveryReferenceResolver,
    RecordingRecoveryRuntimeResolver,
)
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)
from tests.support.snapshot_store_fakes import InMemoryStateSnapshotStore


def _budget(run_id: str) -> BudgetState:
    created = Instant(NOW.value - timedelta(minutes=5))
    return BudgetState(
        run_id=run_id,
        version=1,
        limits=EffectiveBudgetLimits(
            max_retries_per_envelope=2,
            max_retries_per_step=2,
        ),
        created_at=created,
        updated_at=created,
    )


def _observation(record_id: str, version: int) -> ReconciliationObservation:
    return ReconciliationObservation(
        record_id=record_id,
        record_version=version,
        attempt=1,
        disposition=ReconciliationObservationDisposition.STILL_UNKNOWN,
        observed_result_refs=(),
        observed_at=NOW,
    )


def test_abandoned_before_effect_is_explicitly_reactivated_without_retry_count() -> None:
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
    assert context.identity is not None
    policy = IdempotencyPolicy()
    created = Instant(NOW.value - timedelta(minutes=3))
    expired = Instant(NOW.value - timedelta(minutes=2))
    reserved = policy.new_reservation(
        identity=context.identity,
        now=created,
        reservation_expires_at=expired,
    )
    abandoned = policy.prepare_abandon(
        record=reserved,
        now=Instant(NOW.value - timedelta(minutes=1)),
    )
    ledger = InMemoryEffectLedgerFake(initial_records=(abandoned,))
    budget = _budget(plan.run_id)
    budget_port = InMemoryBudgetStatePort(budget)
    snapshot_store = InMemoryStateSnapshotStore()
    snapshot_store.save(
        snapshot=StateSnapshot.capture(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            sequence=1,
            run_id=plan.run_id,
            plan_id=plan.plan_id,
            plan_version=plan.plan_version,
            plan_fingerprint=plan_fingerprint(plan),
            run_state=run_state,
            budget_state=budget,
            effect_ledger_refs=(
                EffectLedgerSnapshotRef(abandoned.record_id, abandoned.version),
            ),
            captured_at=NOW,
        ),
        expected_previous_sequence=None,
    )
    circuit_store = InMemoryCircuitBreakerStore()
    references = PortBackedRecoveryReferenceResolver(
        ledger=ledger,
        circuit_store=circuit_store,
        record_ids=(abandoned.record_id,),
    )
    observation = _observation(abandoned.record_id, abandoned.version)
    coordinator = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=references,
        ledger=ledger,
        budget_port=budget_port,
        snapshot_store=snapshot_store,
        reconciliation_engine=EffectReconciliationEngine(
            ledger,
            RecordingToolEffectProbe(observation),
            RecordingApplicationEffectProbe(observation),
        ),
        circuit_engine=CircuitBreakerEngine(circuit_store, CONFIG),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    coordination = CoordinationDecision(
        CoordinationAction.RECONCILIATION_REQUIRED,
        run_state,
        (ExecutionDirectiveCode.RECONCILIATION_REQUIRED,),
        (step.step_id,),
        ("CRASH_BEFORE_EFFECT",),
    )

    recovery = coordinator.recover(
        plan=plan,
        coordination_decision=coordination,
        now=NOW,
    )
    reactivated = ledger.get(record_id=abandoned.record_id)

    assert recovery.recovery_action is RecoveryAction.RESUME
    assert reactivated is not None
    assert reactivated.lifecycle is EffectLedgerLifecycle.RESERVED
    assert reactivated.record_id == abandoned.record_id
    assert reactivated.version == abandoned.version + 1
    assert reactivated.attempt == 0
    assert recovery.run_state.step_states[step.step_id].attempt_count == 0
    assert recovery.snapshot.recovery_checkpoint is None

    running = replace(
        recovery.run_state.step_states[step.step_id],
        status=StepRuntimeStatus.RUNNING,
        started_at=NOW,
        attempt_count=1,
    )
    resumed_state = replace(
        recovery.run_state,
        step_states={step.step_id: running},
    )
    result = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=budget_port,
        circuit_engine=CircuitBreakerEngine(circuit_store, CONFIG),
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    ).run(
        plan=plan,
        step=step,
        run_state=resumed_state,
        attempt=1,
        now=NOW,
    )
    finalized = ledger.get(record_id=abandoned.record_id)

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert finalized is not None
    assert finalized.effect_state is EffectState.COMMITTED
    assert finalized.attempt == 1
    assert budget_port.get(run_id=plan.run_id).retries_total == 0  # type: ignore[union-attr]


def test_committed_ledger_after_lost_result_never_becomes_step_success() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    running = replace(
        run_state.step_states[step.step_id],
        status=StepRuntimeStatus.RUNNING,
        started_at=NOW,
        attempt_count=1,
    )
    run_state = replace(run_state, step_states={step.step_id: running})
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
    policy = IdempotencyPolicy()
    started = policy.prepare_start(
        record=policy.new_reservation(identity=context.identity, now=NOW),
        attempt=1,
        now=NOW,
    )
    committed = policy.prepare_finalize(
        record=started,
        effect_state=EffectState.COMMITTED,
        now=NOW,
        result_refs=("trusted-result-ref",),
    )
    ledger = InMemoryEffectLedgerFake(initial_records=(committed,))
    budget_port = InMemoryBudgetStatePort(_budget(plan.run_id))
    snapshot_store = InMemoryStateSnapshotStore()
    circuit_store = InMemoryCircuitBreakerStore()
    observation = _observation(committed.record_id, committed.version)
    coordinator = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=PortBackedRecoveryReferenceResolver(
            ledger=ledger,
            circuit_store=circuit_store,
            record_ids=(committed.record_id,),
        ),
        ledger=ledger,
        budget_port=budget_port,
        snapshot_store=snapshot_store,
        reconciliation_engine=EffectReconciliationEngine(
            ledger,
            RecordingToolEffectProbe(observation),
            RecordingApplicationEffectProbe(observation),
        ),
        circuit_engine=CircuitBreakerEngine(circuit_store, CONFIG),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )

    recovery = coordinator.recover(
        plan=plan,
        coordination_decision=CoordinationDecision(
            CoordinationAction.RECONCILIATION_REQUIRED,
            run_state,
            (ExecutionDirectiveCode.RECONCILIATION_REQUIRED,),
            (step.step_id,),
            ("LOST_RESULT",),
        ),
        now=NOW,
    )

    assert recovery.recovery_action is RecoveryAction.RESULT_RECOVERY_REQUIRED
    assert recovery.run_state.step_states[step.step_id].status is StepRuntimeStatus.RUNNING
    assert harness.tool_executor.calls == []
