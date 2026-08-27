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
    SamplingDecision,
    SpanId,
    StepKind,
    TraceId,
)
from backend.agent_runtime.observability import (
    ObservedRecoveryCoordinator,
    RuntimeObservabilityContext,
    RuntimeObservationEmitter,
    SpanCode,
    TraceContextPolicy,
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
from tests.support.runtime_observability_fakes import (
    AdvancingObservationClock,
    CollectingLogSink,
    CollectingMetricSink,
    CollectingTraceSink,
    DeterministicObservationProvider,
    RaisingLogSink,
    RaisingMetricSink,
    RaisingTraceSink,
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


def _emitter(log_sink, trace_sink, metric_sink) -> RuntimeObservationEmitter:
    return RuntimeObservationEmitter(
        log_sink,
        trace_sink,
        metric_sink,
        DeterministicObservationProvider(prefix="recovery"),
        AdvancingObservationClock(NOW),
    )


def _context() -> RuntimeObservabilityContext:
    return RuntimeObservabilityContext(
        TraceContextPolicy().root(
            trace_id=TraceId("recovery-logical-run"),
            span_id=SpanId("recovery-root"),
            sampling_decision=SamplingDecision.RECORD_AND_SAMPLE,
        )
    )


def _error() -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="PROVIDER_TEMPORARY_FAILURE",
        category=ErrorCategory.TRANSIENT,
        source=ErrorSource.PROVIDER,
        retryable=True,
        severity=ErrorSeverity.ERROR,
        message="not persisted",
        step_id="step-routing",
        attempt=1,
        effect_state=EffectState.UNKNOWN,
        recommended_action=RecommendedAction.RETRY,
    )


def _recover(log_sink, trace_sink, metric_sink):
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    initial = make_run_state(plan, ready_step_id=step.step_id)
    failed = replace(
        initial.step_states[step.step_id],
        status=StepRuntimeStatus.FAILED,
        started_at=NOW,
        ended_at=NOW,
        attempt_count=1,
        block_reason="unknown effect",
    )
    run_state = replace(initial, step_states={step.step_id: failed})
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    execution_context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert execution_context.identity is not None
    policy = IdempotencyPolicy()
    in_progress = policy.prepare_start(
        record=policy.new_reservation(identity=execution_context.identity, now=NOW),
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
        disposition=ReconciliationObservationDisposition.NOT_COMMITTED,
        observed_result_refs=(),
        observed_at=NOW,
    )
    tool_probe = RecordingToolEffectProbe(observation)
    circuit_store = InMemoryCircuitBreakerStore()
    canonical = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=PortBackedRecoveryReferenceResolver(
            ledger=ledger,
            circuit_store=circuit_store,
            record_ids=(unknown.record_id,),
        ),
        ledger=ledger,
        budget_port=InMemoryBudgetStatePort(
            BudgetState(
                run_id=plan.run_id,
                version=1,
                limits=EffectiveBudgetLimits(
                    max_retries_per_envelope=2,
                    max_retries_per_step=2,
                ),
                created_at=NOW,
                updated_at=NOW,
            )
        ),
        snapshot_store=InMemoryStateSnapshotStore(),
        reconciliation_engine=EffectReconciliationEngine(
            ledger,
            tool_probe,
            RecordingApplicationEffectProbe(observation),
            reconciliation_policy,
        ),
        circuit_engine=CircuitBreakerEngine(circuit_store, CONFIG),
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    observed = ObservedRecoveryCoordinator.from_coordinator(
        canonical,
        observability=_emitter(log_sink, trace_sink, metric_sink),
        context=_context(),
    )
    result = observed.recover(
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
    return result, tool_probe


def test_reconciliation_and_retry_are_observed_after_canonical_decisions() -> None:
    logs = CollectingLogSink()
    traces = CollectingTraceSink()
    metrics = CollectingMetricSink()

    result, probe = _recover(logs, traces, metrics)

    assert result.recovery_action is RecoveryAction.RETRY_SCHEDULED
    assert len(probe.calls) == 1
    codes = [record.code.value for record in traces.records]
    assert codes.count(SpanCode.RECOVERY_CYCLE.value) == 1
    assert codes.count(SpanCode.RECOVERY_RECONCILIATION.value) == 1
    assert codes.count(SpanCode.RECOVERY_RETRY.value) == 1
    assert len({record.trace_context.span_id for record in traces.records}) == 3
    metric_names = [point.descriptor.name.value for point in metrics.points]
    assert metric_names.count("agent_runtime.recovery.decisions") == 1
    assert metric_names.count("agent_runtime.recovery.reconciliations") == 1
    assert metric_names.count("agent_runtime.recovery.retry_decisions") == 1
    assert logs.records == []


def test_recovery_outcome_and_probe_count_are_identical_with_throwing_sinks() -> None:
    healthy, healthy_probe = _recover(
        CollectingLogSink(),
        CollectingTraceSink(),
        CollectingMetricSink(),
    )
    failing, failing_probe = _recover(
        RaisingLogSink(),
        RaisingTraceSink(),
        RaisingMetricSink(),
    )

    assert failing == healthy
    assert len(failing_probe.calls) == len(healthy_probe.calls) == 1
