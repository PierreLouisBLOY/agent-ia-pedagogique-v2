from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from backend.agent_runtime.agents.evidence import (
    RetrievalChannel,
    RetrievalSearchResult,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    EvidenceSet,
    RecommendedAction,
    SamplingDecision,
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
    SpanId,
    TraceContext,
    TraceId,
)
from backend.agent_runtime.observability import (
    MetricCode,
    metric_points_from_budget_state,
    metric_points_from_error_envelope,
    metric_points_from_evidence_set,
    metric_points_from_execution_directive,
    metric_points_from_retrieval_result,
    metric_points_from_retry_decision,
    metric_points_from_security_event,
)
from backend.agent_runtime.recovery import (
    BudgetMetricCompleteness,
    BudgetState,
    EffectiveBudgetLimits,
    RetryDecision,
    RetryDisposition,
    RetryReasonCode,
)
from backend.agent_runtime.runtime.execution import (
    ExecutionDirective,
    ExecutionDirectiveCode,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
TRACE = TraceContext(
    TraceId("trace-01"),
    SpanId("span-01"),
    None,
    SamplingDecision.DROP,
)


def _meta() -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id="private-run-id",
        step_id="private-step-id",
        parent_step_id=None,
        correlation_id=CorrelationId("private-correlation-id"),
        created_at=NOW,
        actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
        status=AgentResultStatus.SUCCEEDED,
    )


def test_budget_mapper_projects_owner_totals_without_run_or_step_ids() -> None:
    source = BudgetState(
        run_id="private-run-id",
        version=3,
        limits=EffectiveBudgetLimits(),
        created_at=NOW,
        updated_at=NOW,
        consumed_tokens=42,
        consumed_cost=Decimal("1.25"),
        active_runtime_seconds=Decimal("3.5"),
        steps_started=4,
        retries_by_step={"private-step-id": 2},
        tool_calls_by_step={"private-step-id": 5},
        token_completeness=BudgetMetricCompleteness.PARTIAL,
    )

    points = metric_points_from_budget_state(
        source, observed_at=NOW, trace_context=TRACE
    )

    assert tuple(point.descriptor.name.value for point in points) == tuple(
        code.value
        for code in (
            MetricCode.BUDGET_CONSUMED_TOKENS,
            MetricCode.BUDGET_CONSUMED_COST,
            MetricCode.BUDGET_ACTIVE_RUNTIME,
            MetricCode.BUDGET_STEPS_STARTED,
            MetricCode.BUDGET_RETRIES,
            MetricCode.BUDGET_TOOL_CALLS,
        )
    )
    assert tuple(point.value for point in points) == (
        42,
        Decimal("1.25"),
        Decimal("3.5"),
        4,
        2,
        5,
    )
    assert points[0].labels == {"completeness": "PARTIAL"}
    assert all(point.trace_context is TRACE for point in points)
    assert "private-run-id" not in repr(points)
    assert "private-step-id" not in repr(points)


def test_security_mapper_minimizes_metadata_and_drop_sampling_keeps_point() -> None:
    source = SecurityEvent(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        event_id="private-event-id",
        event_type=SecurityEventType.TOOL_INJECTION,
        severity=SecuritySeverity.HIGH,
        boundary=SecurityBoundary.TOOL,
        reason_code=SecurityReasonCode("PRIVATE.REASON"),
        occurred_at=NOW,
        run_id="private-run-id",
        correlation_id=CorrelationId("private-correlation-id"),
        step_id="private-step-id",
        refs=("private-ref",),
        metadata={"detector": "private-detector"},
    )

    points = metric_points_from_security_event(
        source, observed_at=NOW, trace_context=TRACE
    )

    assert len(points) == 1
    assert points[0].value == 1
    assert points[0].labels == {
        "event_type": "tool_injection",
        "severity": "high",
    }
    assert points[0].trace_context is TRACE
    serialized = repr(points)
    assert "private" not in serialized
    assert "boundary" not in points[0].labels


def test_error_and_directive_mappers_exclude_free_codes_and_identifiers() -> None:
    error = ErrorEnvelope(
        error_code="PRIVATE_ERROR_CODE",
        category=ErrorCategory.TOOL,
        source=ErrorSource.TOOL,
        retryable=True,
        severity=ErrorSeverity.WARNING,
        message="private message",
        step_id="private-step-id",
        attempt=2,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.RETRY,
        details={"provider": "private-provider"},
    )
    directive = ExecutionDirective(
        ExecutionDirectiveCode.RETRY_REQUIRED,
        step_id="private-step-id",
        reason_code="PRIVATE_REASON",
    )

    error_point = metric_points_from_error_envelope(error, observed_at=NOW)[0]
    directive_point = metric_points_from_execution_directive(
        directive, observed_at=NOW
    )[0]

    assert error_point.labels == {
        "category": "tool",
        "source": "tool",
        "severity": "warning",
    }
    assert directive_point.labels == {"directive": "RETRY_REQUIRED"}
    assert "private" not in repr((error_point, directive_point)).casefold()


def test_retrieval_and_evidence_mappers_ignore_opaque_metric_mappings() -> None:
    retrieval = RetrievalSearchResult(
        channel=RetrievalChannel.SEMANTIC,
        candidates=(),
        metrics={"private.dynamic.name": 999, "provider_latency": 12},
    )
    evidence = EvidenceSet(
        meta=_meta(),
        retrieval_metrics={
            "ranked_candidate_count": 999,
            "private.dynamic.name": 888,
        },
    )

    retrieval_point = metric_points_from_retrieval_result(
        retrieval, observed_at=NOW
    )[0]
    evidence_point = metric_points_from_evidence_set(evidence, observed_at=NOW)[0]

    assert retrieval_point.value == 0
    assert retrieval_point.labels == {"channel": "SEMANTIC"}
    assert evidence_point.value == 0
    assert evidence_point.labels == {}
    assert "999" not in repr((retrieval_point, evidence_point))
    assert "888" not in repr((retrieval_point, evidence_point))


def test_retry_mapper_observes_disposition_without_reason_or_attempt() -> None:
    source = RetryDecision(
        RetryDisposition.STOP,
        (RetryReasonCode.ERROR_NOT_RETRYABLE,),
    )

    point = metric_points_from_retry_decision(source, observed_at=NOW)[0]

    assert point.value == 1
    assert point.labels == {"disposition": "STOP"}
    assert "ERROR_NOT_RETRYABLE" not in repr(point)
