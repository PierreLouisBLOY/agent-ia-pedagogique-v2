from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    LogLevel,
    SamplingDecision,
    SpanId,
    TraceContext,
    TraceId,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
)
from backend.agent_runtime.observability import structured_log_from_workflow_event
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.synthetic_secret_fixtures import fake_bearer_token

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


def _event() -> WorkflowEvent:
    return WorkflowEvent(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-01",
            step_id="step-01",
            parent_step_id=None,
            correlation_id=CorrelationId("correlation-01"),
            created_at=NOW,
            actor=ActorRef(ActorKind.SYSTEM, "runtime"),
            status=WorkflowStatus.RUNNING,
            trace_flags={"trace_id": "legacy-trace", "sampled": True},
        ),
        event_id="workflow-event:01",
        event_type=WorkflowEventType.ROUTED,
        summary=f"Synthetic summary {fake_bearer_token()}",
        refs=("route:application",),
        metrics={"payload": {"private_locator": "opaque-internal-value"}},
    )


def test_workflow_mapper_uses_canonical_lifecycle_time_and_minimal_facts() -> None:
    event = _event()

    record = structured_log_from_workflow_event(event, record_id="log:workflow:01")

    assert record.schema_version == event.meta.schema_version
    assert record.occurred_at == event.meta.created_at
    assert record.correlation_id == event.meta.correlation_id
    assert record.run_id == event.meta.run_id
    assert record.step_id == event.meta.step_id
    assert record.level is LogLevel.INFO
    assert record.code.value == "WORKFLOW.ROUTED"
    assert record.refs == ()
    assert record.attributes == {
        "event_type": "routed",
        "workflow_status": "running",
        "ref_count": 1,
    }
    assert isinstance(record.attributes, MappingProxyType)


def test_workflow_mapper_excludes_summary_metrics_and_legacy_trace_flags() -> None:
    record = structured_log_from_workflow_event(
        _event(), record_id="log:workflow:02"
    )
    serialized = repr(dict(record.attributes))

    assert "summary" not in record.attributes
    assert "metrics" not in record.attributes
    assert "payload" not in serialized
    assert fake_bearer_token() not in serialized
    assert "legacy-trace" not in serialized
    assert record.trace_context is None


def test_workflow_mapper_only_attaches_explicit_trace_context() -> None:
    trace_context = TraceContext(
        trace_id=TraceId("trace-01"),
        span_id=SpanId("span-01"),
        parent_span_id=None,
        sampling_decision=SamplingDecision.RECORD_ONLY,
    )

    record = structured_log_from_workflow_event(
        _event(),
        record_id="log:workflow:03",
        trace_context=trace_context,
    )

    assert record.trace_context is trace_context


def test_workflow_mapper_does_not_retain_mutable_metric_input() -> None:
    mutable_metrics: dict[str, object] = {"counters": {"attempt": 1}}
    event = _event()
    object.__setattr__(event, "metrics", mutable_metrics)
    record = structured_log_from_workflow_event(event, record_id="log:workflow:04")

    mutable_metrics["counters"] = {"attempt": 99}

    assert record.attributes["ref_count"] == 1
    assert "counters" not in record.attributes
