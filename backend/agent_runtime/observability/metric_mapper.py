from __future__ import annotations

from backend.agent_runtime.agents.evidence.retrieval_model import (
    RetrievalSearchResult,
)
from backend.agent_runtime.contracts import (
    ErrorEnvelope,
    EvidenceSet,
    MetricPoint,
    SecurityEvent,
    TraceContext,
)
from backend.agent_runtime.observability.metric_catalog import MetricCode
from backend.agent_runtime.observability.metric_policy import (
    counter_metric_point,
    gauge_metric_point,
    histogram_metric_point,
)
from backend.agent_runtime.recovery.budget import BudgetState
from backend.agent_runtime.recovery.coordinator import RecoveryDecisionResult
from backend.agent_runtime.recovery.reconciliation import EffectReconciliationResult
from backend.agent_runtime.recovery.retry import RetryDecision
from backend.agent_runtime.runtime.execution.directives import ExecutionDirective
from backend.shared_kernel.time import Instant


def metric_points_from_budget_state(
    source: BudgetState,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if not isinstance(source, BudgetState):
        raise TypeError("source must be a BudgetState")
    return (
        gauge_metric_point(
            MetricCode.BUDGET_CONSUMED_TOKENS,
            observed_at=observed_at,
            value=source.consumed_tokens,
            labels={"completeness": source.token_completeness.value},
            trace_context=trace_context,
        ),
        gauge_metric_point(
            MetricCode.BUDGET_CONSUMED_COST,
            observed_at=observed_at,
            value=source.consumed_cost,
            labels={"completeness": source.cost_completeness.value},
            trace_context=trace_context,
        ),
        gauge_metric_point(
            MetricCode.BUDGET_ACTIVE_RUNTIME,
            observed_at=observed_at,
            value=source.active_runtime_seconds,
            labels={},
            trace_context=trace_context,
        ),
        gauge_metric_point(
            MetricCode.BUDGET_STEPS_STARTED,
            observed_at=observed_at,
            value=source.steps_started,
            labels={},
            trace_context=trace_context,
        ),
        gauge_metric_point(
            MetricCode.BUDGET_RETRIES,
            observed_at=observed_at,
            value=source.retries_total,
            labels={},
            trace_context=trace_context,
        ),
        gauge_metric_point(
            MetricCode.BUDGET_TOOL_CALLS,
            observed_at=observed_at,
            value=source.tool_calls_total,
            labels={},
            trace_context=trace_context,
        ),
    )


def metric_points_from_security_event(
    source: SecurityEvent,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not SecurityEvent:
        raise TypeError("source must be a SecurityEvent")
    return (
        counter_metric_point(
            MetricCode.SECURITY_EVENTS,
            observed_at=observed_at,
            value=1,
            labels={
                "event_type": source.event_type.value,
                "severity": source.severity.value,
            },
            trace_context=trace_context,
        ),
    )


def metric_points_from_error_envelope(
    source: ErrorEnvelope,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not ErrorEnvelope:
        raise TypeError("source must be an ErrorEnvelope")
    return (
        counter_metric_point(
            MetricCode.ERRORS,
            observed_at=observed_at,
            value=1,
            labels={
                "category": source.category.value,
                "source": source.source.value,
                "severity": source.severity.value,
            },
            trace_context=trace_context,
        ),
    )


def metric_points_from_execution_directive(
    source: ExecutionDirective,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not ExecutionDirective:
        raise TypeError("source must be an ExecutionDirective")
    return (
        counter_metric_point(
            MetricCode.RUNTIME_DIRECTIVES,
            observed_at=observed_at,
            value=1,
            labels={"directive": source.code.value},
            trace_context=trace_context,
        ),
    )


def metric_points_from_retrieval_result(
    source: RetrievalSearchResult,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not RetrievalSearchResult:
        raise TypeError("source must be a RetrievalSearchResult")
    return (
        histogram_metric_point(
            MetricCode.RETRIEVAL_RESULT_CANDIDATES,
            observed_at=observed_at,
            value=len(source.candidates),
            labels={"channel": source.channel.value},
            trace_context=trace_context,
        ),
    )


def metric_points_from_evidence_set(
    source: EvidenceSet,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not EvidenceSet:
        raise TypeError("source must be an EvidenceSet")
    return (
        histogram_metric_point(
            MetricCode.EVIDENCE_MATERIALIZED_ITEMS,
            observed_at=observed_at,
            value=len(source.evidence_items),
            labels={},
            trace_context=trace_context,
        ),
    )


def metric_points_from_recovery_decision(
    source: RecoveryDecisionResult,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not RecoveryDecisionResult:
        raise TypeError("source must be a RecoveryDecisionResult")
    return (
        counter_metric_point(
            MetricCode.RECOVERY_DECISIONS,
            observed_at=observed_at,
            value=1,
            labels={"action": source.recovery_action.value},
            trace_context=trace_context,
        ),
    )


def metric_points_from_retry_decision(
    source: RetryDecision,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not RetryDecision:
        raise TypeError("source must be a RetryDecision")
    return (
        counter_metric_point(
            MetricCode.RETRY_DECISIONS,
            observed_at=observed_at,
            value=1,
            labels={"disposition": source.disposition.value},
            trace_context=trace_context,
        ),
    )


def metric_points_from_reconciliation_result(
    source: EffectReconciliationResult,
    *,
    observed_at: Instant,
    trace_context: TraceContext | None = None,
) -> tuple[MetricPoint, ...]:
    if type(source) is not EffectReconciliationResult:
        raise TypeError("source must be an EffectReconciliationResult")
    return (
        counter_metric_point(
            MetricCode.RECONCILIATIONS,
            observed_at=observed_at,
            value=1,
            labels={"disposition": source.disposition.value},
            trace_context=trace_context,
        ),
    )
