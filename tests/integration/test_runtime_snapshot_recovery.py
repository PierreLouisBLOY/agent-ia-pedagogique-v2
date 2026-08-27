from __future__ import annotations

from datetime import timedelta

from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY
from backend.agent_runtime.contracts import AGENT_CONTRACT_SCHEMA_V1_0, ExecutorKind, StepKind
from backend.agent_runtime.recovery import (
    BudgetState,
    CircuitBreakerSnapshotRef,
    EffectiveBudgetLimits,
    EffectLedgerSnapshotRef,
    IdempotencyPolicy,
    RecoveryCheckpoint,
    RecoveryCheckpointAction,
    SnapshotFreshnessIssue,
    StateSnapshot,
    assess_snapshot_freshness,
    plan_fingerprint,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.shared_kernel.time import Instant
from tests.support.circuit_breaker_fakes import make_closed_state
from tests.support.runtime_recovery_fakes import RecordingRecoveryRuntimeResolver
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)
from tests.support.snapshot_store_fakes import InMemoryStateSnapshotStore


def test_checkpoint_survives_store_round_trip_with_exact_not_before() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=RecordingRecoveryRuntimeResolver(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None
    budget = BudgetState(
        run_id=plan.run_id,
        version=1,
        limits=EffectiveBudgetLimits(max_retries_per_step=2),
        created_at=NOW,
        updated_at=NOW,
    )
    not_before = Instant(NOW.value + timedelta(seconds=17))
    checkpoint = RecoveryCheckpoint(
        RecoveryCheckpointAction.RETRY_SCHEDULED,
        step.step_id,
        context.identity.record_id,
        3,
        2,
        1,
        not_before,
        ("SAFE_RETRY",),
    )
    snapshot = StateSnapshot.capture(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        sequence=1,
        run_id=plan.run_id,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        plan_fingerprint=plan_fingerprint(plan),
        run_state=run_state,
        budget_state=budget,
        effect_ledger_refs=(),
        recovery_checkpoint=checkpoint,
        captured_at=NOW,
    )
    store = InMemoryStateSnapshotStore()
    store.save(snapshot=snapshot, expected_previous_sequence=None)

    restored = store.load_latest(run_id=plan.run_id)

    assert restored is not None
    assert restored.recovery_checkpoint == checkpoint
    assert restored.recovery_checkpoint.not_before == not_before


def test_missing_known_ledger_and_circuit_membership_is_stale() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=RecordingRecoveryRuntimeResolver(),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None
    budget = BudgetState(
        run_id=plan.run_id,
        version=1,
        limits=EffectiveBudgetLimits(),
        created_at=NOW,
        updated_at=NOW,
    )
    snapshot = StateSnapshot.capture(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        sequence=1,
        run_id=plan.run_id,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        plan_fingerprint=plan_fingerprint(plan),
        run_state=run_state,
        budget_state=budget,
        effect_ledger_refs=(),
        circuit_breaker_refs=(),
        captured_at=NOW,
    )
    record = IdempotencyPolicy().new_reservation(
        identity=context.identity,
        now=NOW,
    )
    circuit = make_closed_state(key=context.circuit_key)

    assessment = assess_snapshot_freshness(
        snapshot=snapshot,
        current_budget=budget,
        current_ledger_records={record.record_id: record},
        current_plan_fingerprint=plan_fingerprint(plan),
        current_circuit_states={circuit.circuit_id: circuit},
    )

    assert assessment.issues == (
        SnapshotFreshnessIssue.STALE_LEDGER,
        SnapshotFreshnessIssue.STALE_CIRCUIT,
    )
    assert EffectLedgerSnapshotRef(record.record_id, record.version) not in (
        snapshot.effect_ledger_refs
    )
    assert CircuitBreakerSnapshotRef(circuit.circuit_id, circuit.version) not in (
        snapshot.circuit_breaker_refs
    )
