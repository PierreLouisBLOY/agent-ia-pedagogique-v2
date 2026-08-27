from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ObservationCode,
    SamplingDecision,
    SpanId,
    SpanKind,
    SpanRecord,
    SpanStatus,
    TraceContext,
    TraceId,
    WorkflowStatus,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

START = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
END = Instant(datetime(2026, 8, 27, 12, 0, 1, tzinfo=UTC))


def _span(**changes: object) -> SpanRecord:
    values: dict[str, object] = {
        "schema_version": AGENT_CONTRACT_SCHEMA_V1_0,
        "trace_context": TraceContext(
            TraceId("trace-01"),
            SpanId("span-01"),
            None,
            SamplingDecision.RECORD_AND_SAMPLE,
        ),
        "code": ObservationCode("TOOL.CALL"),
        "kind": SpanKind.TOOL,
        "status": SpanStatus.OK,
        "started_at": START,
        "ended_at": END,
        "correlation_id": CorrelationId("correlation-01"),
        "run_id": "run-01",
        "step_id": "step-01",
        "refs": ("tool-result:01",),
        "attributes": {"route": "UTILITY"},
    }
    values.update(changes)
    return SpanRecord(**values)  # type: ignore[arg-type]


def test_span_record_is_completed_immutable_and_provider_neutral() -> None:
    span = _span()

    assert [item.value for item in SpanKind] == [
        "INTERNAL",
        "RUNTIME",
        "AGENT",
        "TOOL",
        "APPLICATION",
        "GATE",
        "RECOVERY",
    ]
    assert [item.value for item in SpanStatus] == [
        "UNSET",
        "OK",
        "ERROR",
        "CANCELLED",
    ]
    assert isinstance(span.attributes, MappingProxyType)
    assert not hasattr(span, "__dict__")
    with pytest.raises(FrozenInstanceError):
        span.status = SpanStatus.ERROR  # type: ignore[misc]


def test_span_status_is_not_workflow_validation() -> None:
    assert SpanStatus.OK != WorkflowStatus.SUCCEEDED
    assert SpanStatus.ERROR != WorkflowStatus.FAILED


def test_span_rejects_negative_duration_non_utc_or_unsafe_attributes() -> None:
    with pytest.raises(ValueError, match="ended_at"):
        _span(ended_at=Instant(START.value - timedelta(microseconds=1)))
    with pytest.raises(ValueError, match="UTC"):
        _span(
            ended_at=Instant(
                datetime(2026, 8, 27, 13, 0, tzinfo=timezone(timedelta(hours=1)))
            )
        )
    with pytest.raises(ValueError):
        _span(attributes={"payload": {"raw": "content"}})


def test_span_requires_typed_trace_context_and_closed_status() -> None:
    with pytest.raises(TypeError, match="trace_context"):
        _span(trace_context={"trace_id": "trace-01"})
    with pytest.raises(TypeError, match="status"):
        _span(status="OK")
