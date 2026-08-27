from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from threading import Thread

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
    DeliveryDisposition,
    DeliveryDropReason,
    DeliveryHealthStatus,
    LogSinkPort,
    MetricCode,
    MetricSinkPort,
    ObservabilityDeliveryPolicy,
    TraceSinkPort,
    gauge_metric_point,
)
from backend.infrastructure.observability import (
    FailureIsolatedLogSink,
    FailureIsolatedMetricSink,
    FailureIsolatedTraceSink,
    StreamTextRecordWriter,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.observability_delivery_fakes import (
    BoundedCollectingTextWriter,
    CoordinatedTextWriter,
    FailAfterTextWriter,
    FailingTextWriter,
    PartialTextWriter,
)

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(seconds=1))
TRACE = TraceContext(
    TraceId("trace-01"),
    SpanId("span-01"),
    None,
    SamplingDecision.RECORD_AND_SAMPLE,
)


def _log(index: int = 1, *, attributes: dict[str, object] | None = None) -> StructuredLogRecord:
    return StructuredLogRecord(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        record_id=f"record-{index}",
        occurred_at=NOW,
        level=LogLevel.INFO,
        code=ObservationCode("WORKFLOW.PLANNED"),
        correlation_id=CorrelationId("correlation-01"),
        trace_context=TRACE,
        attributes=attributes or {"ordinal": index},
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
    )


def _metric():
    return gauge_metric_point(
        MetricCode.BUDGET_CONSUMED_COST,
        observed_at=NOW,
        value=Decimal("1.25"),
        labels={"completeness": "COMPLETE"},
        trace_context=TRACE,
    )


def test_successful_sink_buffers_then_flushes_exactly_once() -> None:
    writer = BoundedCollectingTextWriter()
    sink = FailureIsolatedLogSink(writer)
    source = _log()

    attempt = sink.submit(source)
    result = sink.flush()
    health = sink.health_snapshot()

    assert attempt.disposition is DeliveryDisposition.BUFFERED
    assert result.attempted_count == 1
    assert result.delivered_count == 1
    assert result.failed_count == 0
    assert len(writer.records) == 1
    assert health.status is DeliveryHealthStatus.HEALTHY
    assert health.stats.buffered_count == 1
    assert health.stats.delivered_count == 1
    assert health.buffer.occupancy_items == 0


def test_stream_writer_uses_only_the_injected_stream() -> None:
    stream = StringIO()
    sink = FailureIsolatedLogSink(StreamTextRecordWriter(stream))
    sink.emit(_log())

    result = sink.flush()

    assert result.delivered_count == 1
    assert stream.getvalue().endswith("\n")
    assert '"type":"log"' in stream.getvalue()


def test_writer_exception_is_contained_and_source_outcome_is_unchanged() -> None:
    secret_exception = "writer failed with sk-" + "A" * 40
    writer = FailingTextWriter(secret_exception)
    sink = FailureIsolatedLogSink(writer)
    source = _log()
    original = source
    sink.emit(source)

    result = sink.flush()
    health = sink.health_snapshot()

    assert source == original
    assert result.failed_count == 1
    assert result.stopped_reason is DeliveryDropReason.SINK_FAILURE
    assert health.status is DeliveryHealthStatus.DEGRADED
    assert health.stats.failed_count == 1
    assert secret_exception not in repr(health)
    assert writer.calls == 1


def test_partial_writer_is_a_contained_sink_failure() -> None:
    writer = PartialTextWriter()
    sink = FailureIsolatedLogSink(writer)
    sink.emit(_log())

    result = sink.flush()

    assert result.failed_count == 1
    assert result.delivered_count == 0
    assert writer.calls == 1


def test_full_buffer_drops_newest_without_escaping() -> None:
    writer = BoundedCollectingTextWriter()
    sink = FailureIsolatedLogSink(
        writer,
        ObservabilityDeliveryPolicy(max_items=1, max_bytes=65_536),
    )

    first = sink.submit(_log(1))
    newest = sink.submit(_log(2))

    assert first.disposition is DeliveryDisposition.BUFFERED
    assert newest.disposition is DeliveryDisposition.DROPPED
    assert newest.reason is DeliveryDropReason.BUFFER_FULL
    assert sink.health_snapshot().stats.dropped_count == 1
    assert sink.flush().delivered_count == 1
    assert '"record_id":"record-1"' in writer.records[0]


def test_oversized_and_invalid_records_are_rejected_before_write() -> None:
    writer = BoundedCollectingTextWriter()
    sink = FailureIsolatedLogSink(writer)
    oversized = _log(
        attributes={
            f"field_{index}": tuple("x" * 512 for _ in range(14))
            for index in range(32)
        }
    )

    oversized_attempt = sink.submit(oversized)
    sink.emit(object())  # type: ignore[arg-type]
    health = sink.health_snapshot()

    assert oversized_attempt.disposition is DeliveryDisposition.REJECTED
    assert oversized_attempt.reason is DeliveryDropReason.RECORD_TOO_LARGE
    assert health.stats.rejected_count == 2
    assert health.buffer.occupancy_items == 0
    assert writer.records == ()


def test_flush_preserves_partial_progress_and_unattempted_fifo_tail() -> None:
    writer = FailAfterTextWriter(successful_writes=1)
    sink = FailureIsolatedLogSink(writer)
    for index in range(1, 4):
        sink.emit(_log(index))

    result = sink.flush(max_items=3)

    assert result.attempted_count == 2
    assert result.delivered_count == 1
    assert result.failed_count == 1
    assert result.remaining_items == 1
    assert '"record_id":"record-1"' in writer.records[0]


def test_repeated_failure_never_retries_the_same_buffer_item() -> None:
    writer = FailingTextWriter()
    sink = FailureIsolatedLogSink(writer)
    sink.emit(_log(1))
    sink.emit(_log(2))

    first = sink.flush()
    second = sink.flush()
    third = sink.flush()

    assert first.failed_count == 1
    assert second.failed_count == 1
    assert third.attempted_count == 0
    assert writer.calls == 2
    assert sink.health_snapshot().stats.failed_count == 2


def test_disabled_channel_drops_without_serialization_or_write() -> None:
    writer = BoundedCollectingTextWriter()
    sink = FailureIsolatedLogSink(
        writer,
        ObservabilityDeliveryPolicy(enabled=False),
    )

    attempt = sink.submit(_log())
    result = sink.flush()
    health = sink.health_snapshot()

    assert attempt.disposition is DeliveryDisposition.DROPPED
    assert attempt.reason is DeliveryDropReason.CHANNEL_DISABLED
    assert result.attempted_count == 0
    assert health.status is DeliveryHealthStatus.DISABLED
    assert writer.records == ()


def test_concurrent_submits_are_bounded_and_counted_atomically() -> None:
    writer = BoundedCollectingTextWriter()
    sink = FailureIsolatedLogSink(
        writer,
        ObservabilityDeliveryPolicy(
            max_items=64,
            max_bytes=64 * 65_536,
            max_flush_items=64,
        ),
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        attempts = tuple(executor.map(lambda index: sink.submit(_log(index)), range(1, 33)))

    assert all(item.disposition is DeliveryDisposition.BUFFERED for item in attempts)
    assert sink.health_snapshot().buffer.occupancy_items == 32
    assert sink.health_snapshot().stats.buffered_count == 32
    assert sink.flush(max_items=32).delivered_count == 32


def test_concurrent_flush_returns_busy_without_waiting_or_reordering() -> None:
    writer = CoordinatedTextWriter()
    sink = FailureIsolatedLogSink(writer)
    sink.emit(_log())
    completed = []

    worker = Thread(target=lambda: completed.append(sink.flush()), daemon=False)
    worker.start()
    assert writer.entered.wait(timeout=2)

    busy = sink.flush()
    writer.release.set()
    worker.join(timeout=2)

    assert busy.busy is True
    assert busy.attempted_count == 0
    assert len(completed) == 1
    assert completed[0].delivered_count == 1


def test_channel_adapters_preserve_distinct_b_ports_and_buffers() -> None:
    writer = BoundedCollectingTextWriter()
    log_sink = FailureIsolatedLogSink(writer)
    trace_sink = FailureIsolatedTraceSink(writer)
    metric_sink = FailureIsolatedMetricSink(writer)

    assert isinstance(log_sink, LogSinkPort)
    assert isinstance(trace_sink, TraceSinkPort)
    assert isinstance(metric_sink, MetricSinkPort)
    log_sink.emit(_log())
    trace_sink.emit(_span())
    metric_sink.record(_metric())

    assert log_sink.health_snapshot().buffer.occupancy_items == 1
    assert trace_sink.health_snapshot().buffer.occupancy_items == 1
    assert metric_sink.health_snapshot().buffer.occupancy_items == 1
    assert log_sink.flush().delivered_count == 1
    assert trace_sink.flush().delivered_count == 1
    assert metric_sink.flush().delivered_count == 1
    assert tuple(record.split('"type":"')[1].split('"')[0] for record in writer.records) == (
        "log",
        "span",
        "metric",
    )


def test_flush_batch_limit_is_explicit_and_leaves_tail_buffered() -> None:
    writer = BoundedCollectingTextWriter()
    sink = FailureIsolatedLogSink(
        writer,
        ObservabilityDeliveryPolicy(max_flush_items=2),
    )
    for index in range(1, 4):
        sink.emit(_log(index))

    result = sink.flush()

    assert result.delivered_count == 2
    assert result.limit_reached is True
    assert result.remaining_items == 1
