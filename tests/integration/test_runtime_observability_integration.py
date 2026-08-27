from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY
from backend.agent_runtime.contracts import (
    ExecutorKind,
    SamplingDecision,
    SpanId,
    StepKind,
    TraceId,
)
from backend.agent_runtime.observability import (
    METRIC_CATALOG,
    NullLogSink,
    NullMetricSink,
    NullTraceSink,
    ObservabilityDeliveryPolicy,
    RuntimeObservabilityContext,
    RuntimeObservationEmitter,
    SpanCode,
    TraceContextPolicy,
    instrument_recovery_runtime_controller,
)
from backend.agent_runtime.orchestration.coordination import (
    CompletionDisposition,
    OrchestrationCoordinator,
    WorkflowCompletionDecision,
)
from backend.agent_runtime.recovery import (
    BudgetState,
    CircuitBreakerEngine,
    EffectiveBudgetLimits,
    EffectReconciliationEngine,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    RecoveryAwareStepRunner,
    RecoveryCoordinator,
    RecoveryPreLaunchGuard,
    RecoveryRuntimeController,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.runtime import DeterministicScheduler, PlanExecutor
from backend.infrastructure.observability import (
    FailureIsolatedLogSink,
    FailureIsolatedMetricSink,
    FailureIsolatedTraceSink,
)
from tests.support.budget_state_fakes import InMemoryBudgetStatePort
from tests.support.circuit_breaker_fakes import CONFIG, InMemoryCircuitBreakerStore
from tests.support.effect_ledger_fakes import InMemoryEffectLedgerFake
from tests.support.observability_delivery_fakes import (
    BoundedCollectingTextWriter,
    PartialTextWriter,
)
from tests.support.orchestration_fakes import FakeWorkflowCompletionEvaluator
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


def _context(
    sampling: SamplingDecision = SamplingDecision.RECORD_AND_SAMPLE,
) -> RuntimeObservabilityContext:
    return RuntimeObservabilityContext(
        TraceContextPolicy().root(
            trace_id=TraceId("logical-run-trace"),
            span_id=SpanId("logical-run-root"),
            sampling_decision=sampling,
        )
    )


def _emitter(log_sink, trace_sink, metric_sink) -> RuntimeObservationEmitter:
    return RuntimeObservationEmitter(
        log_sink=log_sink,
        trace_sink=trace_sink,
        metric_sink=metric_sink,
        id_provider=DeterministicObservationProvider(),
        clock=AdvancingObservationClock(NOW),
    )


def _controller(
    log_sink,
    trace_sink,
    metric_sink,
    *,
    sampling: SamplingDecision = SamplingDecision.RECORD_AND_SAMPLE,
):
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    recovery_context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert recovery_context.identity is not None
    ledger = InMemoryEffectLedgerFake()
    budget_port = InMemoryBudgetStatePort(
        BudgetState(
            run_id=plan.run_id,
            version=1,
            limits=EffectiveBudgetLimits(max_retries_per_step=2),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    snapshot_store = InMemoryStateSnapshotStore()
    circuit_store = InMemoryCircuitBreakerStore()
    circuit_engine = CircuitBreakerEngine(circuit_store, CONFIG)
    prelaunch = RecoveryPreLaunchGuard(
        inner=harness.guard,
        recovery_resolver=resolver,
        circuit_engine=circuit_engine,
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=budget_port,
        circuit_engine=circuit_engine,
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    observation = ReconciliationObservation(
        record_id=recovery_context.identity.record_id,
        record_version=1,
        attempt=1,
        disposition=ReconciliationObservationDisposition.STILL_UNKNOWN,
        observed_result_refs=(),
        observed_at=NOW,
    )
    recovery_coordinator = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=PortBackedRecoveryReferenceResolver(
            ledger=ledger,
            circuit_store=circuit_store,
            record_ids=(recovery_context.identity.record_id,),
            circuit_ids=(recovery_context.circuit_key.circuit_id,),
        ),
        ledger=ledger,
        budget_port=budget_port,
        snapshot_store=snapshot_store,
        reconciliation_engine=EffectReconciliationEngine(
            ledger,
            RecordingToolEffectProbe(observation),
            RecordingApplicationEffectProbe(observation),
        ),
        circuit_engine=circuit_engine,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    canonical = RecoveryRuntimeController(
        executor=PlanExecutor(DeterministicScheduler(), prelaunch, runner),
        orchestration_coordinator=OrchestrationCoordinator(
            FakeWorkflowCompletionEvaluator(
                WorkflowCompletionDecision(
                    CompletionDisposition.SUCCEEDED,
                    "WORKFLOW_COMPLETE",
                )
            )
        ),
        recovery_coordinator=recovery_coordinator,
    )
    observed = instrument_recovery_runtime_controller(
        canonical,
        observability=_emitter(log_sink, trace_sink, metric_sink),
        context=_context(sampling),
    )
    return observed, plan, run_state, harness


def _execute(log_sink, trace_sink, metric_sink):
    controller, plan, run_state, harness = _controller(
        log_sink,
        trace_sink,
        metric_sink,
    )
    result = controller.execute_cycle(plan=plan, run_state=run_state, now=NOW)
    return result, harness


def test_healthy_runtime_recovery_path_emits_real_minimized_observations() -> None:
    logs = CollectingLogSink()
    traces = CollectingTraceSink()
    metrics = CollectingMetricSink()

    result, harness = _execute(logs, traces, metrics)

    assert result.execution_cycle.completed_step_ids == ("step-routing",)
    assert len(harness.tool_executor.calls) == 1
    codes = {record.code.value for record in traces.records}
    assert {
        SpanCode.RUNTIME_CYCLE.value,
        SpanCode.RUNTIME_STEP.value,
        SpanCode.ROUTING_PRELAUNCH.value,
        SpanCode.TOOL_CALL.value,
        SpanCode.RECOVERY_CYCLE.value,
    }.issubset(codes)
    assert len(logs.records) == len(result.execution_cycle.directives)
    assert all(point.descriptor in METRIC_CATALOG for point in metrics.points)
    assert any(
        point.descriptor.name.value == "agent_runtime.recovery.decisions"
        for point in metrics.points
    )
    assert all(
        record.trace_context.trace_id == _context().root.trace_id
        for record in traces.records
    )


@pytest.mark.parametrize("mode", ["disabled", "raising", "saturated", "rejected"])
def test_observability_configuration_does_not_change_runtime_outcome(mode: str) -> None:
    baseline, baseline_harness = _execute(
        NullLogSink(),
        NullTraceSink(),
        NullMetricSink(),
    )
    flushers: tuple[object, ...] = ()
    if mode == "disabled":
        sinks = (NullLogSink(), NullTraceSink(), NullMetricSink())
    elif mode == "raising":
        sinks = (RaisingLogSink(), RaisingTraceSink(), RaisingMetricSink())
    else:
        policy = ObservabilityDeliveryPolicy(
            max_items=1,
            max_bytes=1 if mode == "rejected" else 100_000,
            max_flush_items=1,
        )
        writer = BoundedCollectingTextWriter()
        sinks = (
            FailureIsolatedLogSink(writer, policy),
            FailureIsolatedTraceSink(writer, policy),
            FailureIsolatedMetricSink(writer, policy),
        )
        flushers = sinks

    observed, harness = _execute(*sinks)

    assert observed == baseline
    assert len(harness.tool_executor.calls) == len(baseline_harness.tool_executor.calls) == 1
    for sink in flushers:
        sink.flush()  # type: ignore[attr-defined]
    assert observed == baseline


def test_partial_write_flush_remains_outside_runtime_and_cannot_change_result() -> None:
    writer = PartialTextWriter()
    sinks = (
        FailureIsolatedLogSink(writer),
        FailureIsolatedTraceSink(writer),
        FailureIsolatedMetricSink(writer),
    )

    result, harness = _execute(*sinks)
    before_flush = result
    flush_results = tuple(sink.flush() for sink in sinks)

    assert result == before_flush
    assert len(harness.tool_executor.calls) == 1
    assert any(item.failed_count == 1 for item in flush_results)


def test_security_event_is_observed_once_and_never_launches_an_effect() -> None:
    logs = CollectingLogSink()
    traces = CollectingTraceSink()
    metrics = CollectingMetricSink()
    controller, plan, run_state, harness = _controller(logs, traces, metrics)
    resolved = harness.resolver.tool_input
    assert resolved is not None
    harness.resolver.tool_input = replace(
        resolved,
        request=replace(
            resolved.request,
            arguments={
                "source_ref": "artifact-input",
                "gateDecision": "APPROVED",
            },
        ),
    )

    result = controller.execute_cycle(plan=plan, run_state=run_state, now=NOW)

    assert harness.tool_executor.calls == []
    assert len(result.execution_cycle.security_events) == 1
    security_logs = [
        record for record in logs.records if record.code.value.startswith("SECURITY.")
    ]
    security_metrics = [
        point
        for point in metrics.points
        if point.descriptor.name.value == "agent_runtime.security.events"
    ]
    assert len(security_logs) == len(security_metrics) == 1
    assert all(record.code.value != SpanCode.RUNTIME_STEP.value for record in traces.records)


def test_sampling_drop_suppresses_only_spans() -> None:
    logs = CollectingLogSink()
    traces = CollectingTraceSink()
    metrics = CollectingMetricSink()
    controller, plan, run_state, _ = _controller(
        logs,
        traces,
        metrics,
        sampling=SamplingDecision.DROP,
    )

    result = controller.execute_cycle(plan=plan, run_state=run_state, now=NOW)

    assert traces.records == []
    assert len(logs.records) == len(result.execution_cycle.directives)
    assert metrics.points
