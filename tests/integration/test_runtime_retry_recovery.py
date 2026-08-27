from __future__ import annotations

from dataclasses import replace

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
    EffectLedgerLifecycle,
    EffectReconciliationEngine,
    IdempotencyPolicy,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    RecoveryAction,
    RecoveryAwareStepRunner,
    RecoveryCoordinator,
    RetryDisposition,
    RetryFailureFacts,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.runtime import (
    ExecutionDirectiveCode,
    StepRuntimeStatus,
)
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


def _budget(run_id: str, *, max_retries: int = 2) -> BudgetState:
    return BudgetState(
        run_id=run_id,
        version=1,
        limits=EffectiveBudgetLimits(
            max_retries_per_envelope=max_retries,
            max_retries_per_step=max_retries,
        ),
        created_at=NOW,
        updated_at=NOW,
    )


def _retry_error(attempt: int = 1) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="PROVIDER_TEMPORARY_FAILURE",
        category=ErrorCategory.TRANSIENT,
        source=ErrorSource.PROVIDER,
        retryable=True,
        severity=ErrorSeverity.ERROR,
        message="not persisted",
        step_id="step-routing",
        attempt=attempt,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.RETRY,
    )


def _failed_run_state(plan: object) -> object:
    from backend.agent_runtime.runtime import Plan, RunState

    assert isinstance(plan, Plan)
    state = make_run_state(plan, ready_step_id=plan.steps[0].step_id)
    assert isinstance(state, RunState)
    failed = replace(
        state.step_states[plan.steps[0].step_id],
        status=StepRuntimeStatus.FAILED,
        started_at=NOW,
        ended_at=NOW,
        attempt_count=1,
        block_reason="execution failed",
    )
    return replace(state, step_states={failed.step_id: failed})


def _observation(record: object) -> ReconciliationObservation:
    from backend.agent_runtime.recovery import EffectLedgerRecord

    assert isinstance(record, EffectLedgerRecord)
    return ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        disposition=ReconciliationObservationDisposition.STILL_UNKNOWN,
        observed_result_refs=(),
        observed_at=NOW,
    )


def test_retry_none_is_scheduled_then_launched_once_with_same_identity() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = _failed_run_state(plan)
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
    reserved = policy.new_reservation(identity=context.identity, now=NOW)
    started = policy.prepare_start(record=reserved, attempt=1, now=NOW)
    first_record = policy.prepare_finalize(
        record=started,
        effect_state=EffectState.NONE,
        now=NOW,
        retry_failure_facts=RetryFailureFacts.from_error(_retry_error()),
    )
    ledger = InMemoryEffectLedgerFake(initial_records=(first_record,))
    budget_port = InMemoryBudgetStatePort(_budget(plan.run_id))
    snapshot_store = InMemoryStateSnapshotStore()
    circuit_store = InMemoryCircuitBreakerStore()
    references = PortBackedRecoveryReferenceResolver(
        ledger=ledger,
        circuit_store=circuit_store,
        record_ids=(first_record.record_id,),
        circuit_ids=(context.circuit_key.circuit_id,),
    )
    observation = _observation(first_record)
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
        action=CoordinationAction.RETRY_REQUIRED,
        run_state=run_state,
        directive_codes=(ExecutionDirectiveCode.RETRY_REQUIRED,),
        affected_step_ids=(step.step_id,),
        reason_codes=("SAFE_RETRY_REQUIRES_COORDINATION",),
    )

    recovery = coordinator.recover(
        plan=plan,
        coordination_decision=coordination,
        now=NOW,
    )

    assert recovery.recovery_action is RecoveryAction.RETRY_SCHEDULED
    assert recovery.retry_decision is not None
    assert recovery.retry_decision.disposition is RetryDisposition.RETRY
    assert recovery.run_state.step_states[step.step_id].status is StepRuntimeStatus.PENDING
    assert recovery.run_state.step_states[step.step_id].attempt_count == 1
    assert recovery.snapshot.recovery_checkpoint is not None
    not_before = recovery.retry_decision.not_before
    assert not_before is not None

    ready = replace(
        recovery.run_state.step_states[step.step_id],
        status=StepRuntimeStatus.READY,
    )
    running = replace(
        ready,
        status=StepRuntimeStatus.RUNNING,
        started_at=not_before,
        attempt_count=2,
    )
    retry_run_state = replace(
        recovery.run_state,
        step_states={step.step_id: running},
    )
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=budget_port,
        circuit_engine=CircuitBreakerEngine(circuit_store, CONFIG),
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    result = runner.run(
        plan=plan,
        step=step,
        run_state=retry_run_state,
        attempt=2,
        now=not_before,
    )
    final_record = ledger.get(record_id=first_record.record_id)
    budget = budget_port.get(run_id=plan.run_id)

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert len(harness.tool_executor.calls) == 1
    assert final_record is not None
    assert final_record.identity == first_record.identity
    assert final_record.attempt == 2
    assert final_record.effect_state is EffectState.COMMITTED
    assert final_record.lifecycle is EffectLedgerLifecycle.FINALIZED
    assert budget is not None
    assert budget.retries_by_step[step.step_id] == 1


def test_retry_limit_blocks_pending_transition() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = _failed_run_state(plan)
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
    record = policy.prepare_finalize(
        record=started,
        effect_state=EffectState.NONE,
        now=NOW,
        retry_failure_facts=RetryFailureFacts.from_error(_retry_error()),
    )
    ledger = InMemoryEffectLedgerFake(initial_records=(record,))
    budget_port = InMemoryBudgetStatePort(_budget(plan.run_id, max_retries=0))
    circuit_store = InMemoryCircuitBreakerStore()
    observation = _observation(record)
    coordinator = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=PortBackedRecoveryReferenceResolver(
            ledger=ledger,
            circuit_store=circuit_store,
            record_ids=(record.record_id,),
        ),
        ledger=ledger,
        budget_port=budget_port,
        snapshot_store=InMemoryStateSnapshotStore(),
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
            CoordinationAction.RETRY_REQUIRED,
            run_state,
            (ExecutionDirectiveCode.RETRY_REQUIRED,),
            (step.step_id,),
            ("SAFE_RETRY_REQUIRES_COORDINATION",),
        ),
        now=NOW,
    )

    assert recovery.recovery_action is RecoveryAction.STOP
    assert recovery.run_state.step_states[step.step_id].status is StepRuntimeStatus.FAILED
    assert recovery.snapshot.recovery_checkpoint is None


def test_revoked_permission_is_revalidated_and_blocks_retry() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = _failed_run_state(plan)
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
    record = policy.prepare_finalize(
        record=started,
        effect_state=EffectState.NONE,
        now=NOW,
        retry_failure_facts=RetryFailureFacts.from_error(_retry_error()),
    )
    from backend.agent_runtime.runtime.routing import ResolvedToolInput

    resolved = harness.resolver.tool_input
    assert isinstance(resolved, ResolvedToolInput)
    harness.resolver.tool_input = replace(resolved, scope_revoked=True)
    ledger = InMemoryEffectLedgerFake(initial_records=(record,))
    circuit_store = InMemoryCircuitBreakerStore()
    observation = _observation(record)
    coordinator = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=PortBackedRecoveryReferenceResolver(
            ledger=ledger,
            circuit_store=circuit_store,
            record_ids=(record.record_id,),
        ),
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(_budget(plan.run_id)),
        snapshot_store=InMemoryStateSnapshotStore(),
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
            CoordinationAction.RETRY_REQUIRED,
            run_state,
            (ExecutionDirectiveCode.RETRY_REQUIRED,),
            (step.step_id,),
            ("SAFE_RETRY_REQUIRES_COORDINATION",),
        ),
        now=NOW,
    )

    assert recovery.recovery_action is RecoveryAction.STOP
    assert recovery.run_state.step_states[step.step_id].status is StepRuntimeStatus.FAILED
    assert recovery.snapshot.recovery_checkpoint is None
