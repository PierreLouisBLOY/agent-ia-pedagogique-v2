from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    LogLevel,
    ObservationCode,
    SamplingDecision,
    SpanId,
    SpanKind,
    SpanRecord,
    SpanStatus,
    StructuredLogRecord,
    TraceContext,
    TraceId,
)
from backend.agent_runtime.observability import (
    MetricCode,
    gauge_metric_point,
)
from backend.infrastructure.observability import (
    MAX_SERIALIZED_RECORD_BYTES,
    ObservabilitySerializationError,
    ObservabilitySerializationErrorCode,
    serialize_log_record,
    serialize_metric_point,
    serialize_span_record,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(seconds=2))
TRACE = TraceContext(
    TraceId("trace-01"),
    SpanId("span-01"),
    SpanId("parent-01"),
    SamplingDecision.RECORD_ONLY,
)


def _log(*, attributes: dict[str, object] | None = None) -> StructuredLogRecord:
    return StructuredLogRecord(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        record_id="record-01",
        occurred_at=NOW,
        level=LogLevel.INFO,
        code=ObservationCode("WORKFLOW.PLANNED"),
        correlation_id=CorrelationId("correlation-01"),
        run_id="run-01",
        step_id="step-01",
        trace_context=TRACE,
        refs=("workflow-01",),
        attributes=attributes or {"count": 2, "ordered": ("a", "b")},
    )


def _span() -> SpanRecord:
    return SpanRecord(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        trace_context=TRACE,
        code=ObservationCode("RUNTIME.STEP"),
        kind=SpanKind.RUNTIME,
        status=SpanStatus.OK,
        started_at=NOW,
        ended_at=LATER,
        correlation_id=CorrelationId("correlation-01"),
        run_id="run-01",
        step_id="step-01",
        refs=("result-01",),
        attributes={"attempt": 1},
    )


def test_log_serialization_is_deterministic_explicit_ndjson() -> None:
    first = serialize_log_record(_log())
    second = serialize_log_record(_log())
    decoded = json.loads(first.payload)

    assert first == second
    assert first.payload.endswith("\n")
    assert first.size_bytes == len(first.payload.encode("utf-8"))
    assert first.size_bytes <= MAX_SERIALIZED_RECORD_BYTES
    assert decoded == {
        "type": "log",
        "schema_version": "1.0",
        "record_id": "record-01",
        "occurred_at": "2026-08-27T12:00:00.000000Z",
        "level": "INFO",
        "code": "WORKFLOW.PLANNED",
        "correlation_id": "correlation-01",
        "run_id": "run-01",
        "step_id": "step-01",
        "trace_context": {
            "trace_id": "trace-01",
            "span_id": "span-01",
            "parent_span_id": "parent-01",
            "sampling_decision": "RECORD_ONLY",
        },
        "refs": ["workflow-01"],
        "attributes": {"count": 2, "ordered": ["a", "b"]},
    }


def test_span_and_metric_serialization_keep_channels_and_numeric_types_distinct() -> None:
    span = serialize_span_record(_span())
    metric = serialize_metric_point(
        gauge_metric_point(
            MetricCode.BUDGET_CONSUMED_COST,
            observed_at=NOW,
            value=Decimal("1.2500"),
            labels={"completeness": "COMPLETE"},
            trace_context=TRACE,
        )
    )
    span_data = json.loads(span.payload)
    metric_data = json.loads(metric.payload)

    assert span_data["type"] == "span"
    assert span_data["kind"] == "RUNTIME"
    assert span_data["status"] == "OK"
    assert metric_data["type"] == "metric"
    assert metric_data["name"] == "agent_runtime.budget.consumed_cost"
    assert metric_data["value"] == {"type": "decimal", "value": "1.2500"}
    assert metric_data["labels"] == {"completeness": "COMPLETE"}


def test_serializer_rejects_oversized_record_before_any_writer() -> None:
    attributes = {
        f"field_{index}": tuple("x" * 512 for _ in range(14))
        for index in range(32)
    }
    record = _log(attributes=attributes)

    with pytest.raises(ObservabilitySerializationError) as raised:
        serialize_log_record(record)

    assert raised.value.code is ObservabilitySerializationErrorCode.RECORD_TOO_LARGE
    assert "x" * 32 not in str(raised.value)


def test_serializer_revalidates_privacy_without_exposing_rejected_value() -> None:
    record = _log()
    private_value = "C:\\Users\\private-user\\secret.txt"
    object.__setattr__(record, "attributes", {"safe_field": private_value})

    with pytest.raises(ObservabilitySerializationError) as raised:
        serialize_log_record(record)

    assert raised.value.code is ObservabilitySerializationErrorCode.UNSUPPORTED_VALUE
    assert private_value not in str(raised.value)
    assert raised.value.__cause__ is None


def test_channel_serializer_rejects_wrong_record_type_with_closed_error() -> None:
    with pytest.raises(ObservabilitySerializationError) as raised:
        serialize_log_record(object())  # type: ignore[arg-type]

    assert raised.value.code is ObservabilitySerializationErrorCode.INVALID_RECORD
    assert raised.value.channel.value == "log"
