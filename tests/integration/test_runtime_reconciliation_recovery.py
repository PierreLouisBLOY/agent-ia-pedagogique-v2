from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY
from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    ExecutorKind,
    RecommendedAction,
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
    EffectReconciliationEngine,
    EffectReconciliationPolicy,
    IdempotencyPolicy,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    RecoveryAction,
    RecoveryCoordinator,
    RetryFailureFacts,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.runtime import ExecutionDirectiveCode, StepRuntimeStatus
from tests.support.budget_state_fakes import InMemoryBudgetStatePort
from tests.support.circuit_breaker_fakes import CONFIG, InMemoryCircuitBreakerStore
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


def _error(effect_state: EffectState = EffectState.UNKNOWN) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="PROVIDER_TEMPORARY_FAILURE",
        category=ErrorCategory.TRANSIENT,
        source=ErrorSource.PROVIDER,
        retryable=True,
        severity=ErrorSeverity.ERROR,
        message="not persisted",
        step_id="step-routing",
        attempt=1,
        effect_state=effect_state,
        recommended_action=RecommendedAction.RETRY,
    )


def _budget(run_id: str) -> BudgetState:
    return BudgetState(
        run_id=run_id,
        version=1,
        limits=EffectiveBudgetLimits(
            max_retries_per_envelope=2,
            max_retries_per_step=2,
        ),
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize(
    ("observation_disposition", "expected_action"),
    [
        (
            ReconciliationObservationDisposition.NOT_COMMITTED,
            RecoveryAction.RETRY_SCHEDULED,
        ),
        (
            ReconciliationObservationDisposition.COMMITTED,
            RecoveryAction.RESULT_RECOVERY_REQUIRED,
        ),
        (
            ReconciliationObservationDisposition.STILL_UNKNOWN,
            RecoveryAction.RECONCILE,
        ),
        (
            ReconciliationObservationDisposition.MANUAL_REQUIRED,
            RecoveryAction.MANUAL_REQUIRED,
        ),
    ],
)
def test_reconciliation_outcome_controls_replay_without_inferred_success(
    observation_disposition: ReconciliationObservationDisposition,
    expected_action: RecoveryAction,
) -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    failed = replace(
        run_state.step_states[step.step_id],
        status=StepRuntimeStatus.FAILED,
        started_at=NOW,
        ended_at=NOW,
        attempt_count=1,
        block_reason="unknown effect",
    )
    run_state = replace(run_state, step_states={step.step_id: failed})
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
    in_progress = policy.prepare_start(
        record=policy.new_reservation(identity=context.identity, now=NOW),
        attempt=1,
        now=NOW,
    )
    unknown = policy.prepare_finalize(
        record=in_progress,
        effect_state=EffectState.UNKNOWN,
        now=NOW,
        retry_failure_facts=RetryFailureFacts.from_error(_error()),
    )
    reconciliation_policy = EffectReconciliationPolicy()
    ledger = InMemoryEffectLedgerFake(
        initial_records=(unknown,),
        cas_validator=reconciliation_policy.validate_compare_and_set,
    )
    observation = ReconciliationObservation(
        record_id=unknown.record_id,
        record_version=unknown.version,
        attempt=1,
        disposition=observation_disposition,
        observed_result_refs=(
            ("committed-result-ref",)
            if observation_disposition
            is ReconciliationObservationDisposition.COMMITTED
            else ()
        ),
        observed_at=NOW,
    )
    tool_probe = RecordingToolEffectProbe(observation)
    application_probe = RecordingApplicationEffectProbe(observation)
    circuit_store = InMemoryCircuitBreakerStore()
    snapshot_store = InMemoryStateSnapshotStore()
    coordinator = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=PortBackedRecoveryReferenceResolver(
            ledger=ledger,
            circuit_store=circuit_store,
            record_ids=(unknown.record_id,),
        ),
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(_budget(plan.run_id)),
        snapshot_store=snapshot_store,
        reconciliation_engine=EffectReconciliationEngine(
            ledger,
            tool_probe,
            application_probe,
            reconciliation_policy,
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
            ("UNKNOWN_EFFECT_REQUIRES_RECONCILIATION",),
        ),
        now=NOW,
    )

    assert recovery.recovery_action is expected_action
    assert len(tool_probe.calls) == 1
    assert application_probe.calls == []
    if observation_disposition is ReconciliationObservationDisposition.COMMITTED:
        assert recovery.run_state.step_states[step.step_id].status is StepRuntimeStatus.FAILED
        assert recovery.snapshot.recovery_checkpoint is None
    if observation_disposition is ReconciliationObservationDisposition.NOT_COMMITTED:
        assert recovery.run_state.step_states[step.step_id].status is StepRuntimeStatus.PENDING
        assert recovery.snapshot.recovery_checkpoint is not None
