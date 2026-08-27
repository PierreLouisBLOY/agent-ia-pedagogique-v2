from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts import (
    ErrorEnvelope,
    MetricPoint,
    SamplingDecision,
    SecurityEvent,
    SpanKind,
    SpanStatus,
    TraceContext,
)
from backend.agent_runtime.observability.log_mapper import (
    structured_log_from_error_envelope,
    structured_log_from_execution_directive,
    structured_log_from_security_event,
)
from backend.agent_runtime.observability.metric_mapper import (
    metric_points_from_budget_state,
    metric_points_from_error_envelope,
    metric_points_from_execution_directive,
    metric_points_from_reconciliation_result,
    metric_points_from_recovery_decision,
    metric_points_from_retry_decision,
    metric_points_from_security_event,
)
from backend.agent_runtime.observability.ports import (
    LogSinkPort,
    MetricSinkPort,
    TraceSinkPort,
)
from backend.agent_runtime.observability.runtime_context import (
    ObservationClockPort,
    ObservationIdSourcePort,
    PendingObservationSpan,
)
from backend.agent_runtime.observability.span_catalog import SpanCode
from backend.agent_runtime.observability.span_factory import completed_span
from backend.agent_runtime.observability.trace_policy import TraceContextPolicy
from backend.agent_runtime.recovery.coordinator import RecoveryDecisionResult
from backend.agent_runtime.runtime.execution.directives import ExecutionDirective
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class RuntimeObservationEmitter:
    """Failure-neutral construction and delivery of runtime observations."""

    log_sink: LogSinkPort
    trace_sink: TraceSinkPort
    metric_sink: MetricSinkPort
    id_provider: ObservationIdSourcePort
    clock: ObservationClockPort
    trace_policy: TraceContextPolicy = field(default_factory=TraceContextPolicy)

    def __post_init__(self) -> None:
        if not isinstance(self.log_sink, LogSinkPort):
            raise TypeError("log_sink must implement LogSinkPort")
        if not isinstance(self.trace_sink, TraceSinkPort):
            raise TypeError("trace_sink must implement TraceSinkPort")
        if not isinstance(self.metric_sink, MetricSinkPort):
            raise TypeError("metric_sink must implement MetricSinkPort")
        if not isinstance(self.id_provider, ObservationIdSourcePort):
            raise TypeError("id_provider must implement ObservationIdSourcePort")
        if not isinstance(self.clock, ObservationClockPort):
            raise TypeError("clock must implement ObservationClockPort")
        if not isinstance(self.trace_policy, TraceContextPolicy):
            raise TypeError("trace_policy must be a TraceContextPolicy")

    def begin_span(self, parent: TraceContext) -> PendingObservationSpan | None:
        """Reserve a child span without ever allowing telemetry failure to escape."""

        try:
            if parent.sampling_decision is SamplingDecision.DROP:
                return None
            context = self.trace_policy.child(
                parent=parent,
                child_span_id=self.id_provider.new_span_id(),
            )
            return PendingObservationSpan(context, self.clock.now())
        except Exception:
            return None

    def finish_span(
        self,
        pending: PendingObservationSpan | None,
        *,
        code: SpanCode,
        kind: SpanKind,
        status: SpanStatus,
        correlation_id: CorrelationId,
        run_id: str,
        step_id: str | None = None,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        if pending is None:
            return
        try:
            record = completed_span(
                trace_context=pending.trace_context,
                code=code,
                kind=kind,
                status=status,
                started_at=pending.started_at,
                ended_at=self.clock.now(),
                correlation_id=correlation_id,
                run_id=run_id,
                step_id=step_id,
                attributes=attributes,
            )
            self.trace_sink.emit(record)
        except Exception:
            return

    def observe_security_event(
        self,
        source: SecurityEvent,
        *,
        trace_context: TraceContext,
    ) -> None:
        try:
            record = structured_log_from_security_event(
                source,
                record_id=self.id_provider.new_record_id(),
                trace_context=trace_context,
            )
            self.log_sink.emit(record)
        except Exception:
            pass
        observed_at = self._now()
        if observed_at is None:
            return
        try:
            self._record_metrics(
                metric_points_from_security_event(
                    source,
                    observed_at=observed_at,
                    trace_context=trace_context,
                )
            )
        except Exception:
            return

    def observe_directive(
        self,
        source: ExecutionDirective,
        *,
        correlation_id: CorrelationId,
        run_id: str,
        trace_context: TraceContext,
    ) -> None:
        occurred_at = self._now()
        if occurred_at is not None:
            try:
                record = structured_log_from_execution_directive(
                    source,
                    correlation_id=correlation_id,
                    run_id=run_id,
                    occurred_at=occurred_at,
                    record_id=self.id_provider.new_record_id(),
                    trace_context=trace_context,
                )
                self.log_sink.emit(record)
            except Exception:
                pass
        observed_at = self._now()
        if observed_at is None:
            return
        try:
            self._record_metrics(
                metric_points_from_execution_directive(
                    source,
                    observed_at=observed_at,
                    trace_context=trace_context,
                )
            )
        except Exception:
            return

    def observe_error(
        self,
        source: ErrorEnvelope,
        *,
        correlation_id: CorrelationId,
        run_id: str,
        trace_context: TraceContext,
    ) -> None:
        occurred_at = self._now()
        if occurred_at is not None:
            try:
                record = structured_log_from_error_envelope(
                    source,
                    correlation_id=correlation_id,
                    run_id=run_id,
                    occurred_at=occurred_at,
                    record_id=self.id_provider.new_record_id(),
                    trace_context=trace_context,
                )
                self.log_sink.emit(record)
            except Exception:
                pass
        observed_at = self._now()
        if observed_at is None:
            return
        try:
            self._record_metrics(
                metric_points_from_error_envelope(
                    source,
                    observed_at=observed_at,
                    trace_context=trace_context,
                )
            )
        except Exception:
            return

    def observe_recovery_decision(
        self,
        source: RecoveryDecisionResult,
        *,
        trace_context: TraceContext,
    ) -> None:
        observed_at = self._now()
        if observed_at is None:
            return
        self._map_and_record(
            metric_points_from_recovery_decision,
            source,
            observed_at,
            trace_context,
        )
        self._map_and_record(
            metric_points_from_budget_state,
            source.budget_state,
            observed_at,
            trace_context,
        )
        if source.retry_decision is not None:
            self._map_and_record(
                metric_points_from_retry_decision,
                source.retry_decision,
                observed_at,
                trace_context,
            )
        if source.reconciliation_result is not None:
            self._map_and_record(
                metric_points_from_reconciliation_result,
                source.reconciliation_result,
                observed_at,
                trace_context,
            )

    def _now(self) -> Instant | None:
        try:
            return self.clock.now()
        except Exception:
            return None

    def _record_metrics(self, points: tuple[MetricPoint, ...]) -> None:
        for point in points:
            try:
                self.metric_sink.record(point)
            except Exception:
                continue

    def _map_and_record(
        self,
        mapper: Callable[..., tuple[MetricPoint, ...]],
        source: object,
        observed_at: Instant,
        trace_context: TraceContext,
    ) -> None:
        try:
            points = mapper(
                source,
                observed_at=observed_at,
                trace_context=trace_context,
            )
            self._record_metrics(points)
        except Exception:
            return
