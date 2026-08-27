from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from backend.agent_runtime.contracts import (
    MetricPoint,
    SpanRecord,
    StructuredLogRecord,
)
from backend.agent_runtime.observability.delivery_model import (
    DeliveryAttempt,
    DeliveryDisposition,
    DeliveryDropReason,
    DeliveryFlushResult,
    DeliveryHealthSnapshot,
    DeliveryHealthStatus,
    DeliveryStatsSnapshot,
    ObservationChannel,
)
from backend.agent_runtime.observability.delivery_policy import (
    BASELINE_OBSERVABILITY_DELIVERY_POLICY,
    ObservabilityDeliveryPolicy,
)
from backend.infrastructure.observability.buffering import BoundedDeliveryBuffer
from backend.infrastructure.observability.serialization import (
    ObservabilitySerializationError,
    ObservabilitySerializationErrorCode,
    SerializedObservation,
    serialize_log_record,
    serialize_metric_point,
    serialize_span_record,
)
from backend.infrastructure.observability.writers import TextRecordWriter


class _DeliveryStats:
    def __init__(self) -> None:
        self._delivered = 0
        self._buffered = 0
        self._dropped = 0
        self._failed = 0
        self._rejected = 0
        self._last_failure: DeliveryDropReason | None = None
        self._lock = Lock()

    def buffered(self, displaced_count: int) -> None:
        with self._lock:
            self._buffered += 1
            self._dropped += displaced_count
            if displaced_count:
                self._last_failure = DeliveryDropReason.BUFFER_FULL

    def dropped(self, reason: DeliveryDropReason) -> None:
        with self._lock:
            self._dropped += 1
            self._last_failure = reason

    def rejected(self, reason: DeliveryDropReason) -> None:
        with self._lock:
            self._rejected += 1
            self._last_failure = reason

    def delivered(self) -> None:
        with self._lock:
            self._delivered += 1
            self._last_failure = None

    def failed(self) -> None:
        with self._lock:
            self._failed += 1
            self._last_failure = DeliveryDropReason.SINK_FAILURE

    def snapshot(
        self,
    ) -> tuple[DeliveryStatsSnapshot, DeliveryDropReason | None]:
        with self._lock:
            return (
                DeliveryStatsSnapshot(
                    delivered_count=self._delivered,
                    buffered_count=self._buffered,
                    dropped_count=self._dropped,
                    failed_count=self._failed,
                    rejected_count=self._rejected,
                ),
                self._last_failure,
            )


class _BufferedChannelDelivery[TRecord]:
    def __init__(
        self,
        *,
        channel: ObservationChannel,
        serializer: Callable[[TRecord], SerializedObservation],
        writer: TextRecordWriter,
        policy: ObservabilityDeliveryPolicy,
    ) -> None:
        if not isinstance(writer, TextRecordWriter):
            raise TypeError("writer must implement TextRecordWriter")
        if not isinstance(policy, ObservabilityDeliveryPolicy):
            raise TypeError("policy must be an ObservabilityDeliveryPolicy")
        self._channel = channel
        self._serializer = serializer
        self._writer = writer
        self._policy = policy
        self._buffer = BoundedDeliveryBuffer(channel, policy)
        self._stats = _DeliveryStats()
        self._flush_lock = Lock()

    def submit(self, record: TRecord) -> DeliveryAttempt:
        if not self._policy.enabled:
            reason = DeliveryDropReason.CHANNEL_DISABLED
            self._stats.dropped(reason)
            return DeliveryAttempt(DeliveryDisposition.DROPPED, reason)
        try:
            serialized = self._serializer(record)
        except ObservabilitySerializationError as error:
            reason = (
                DeliveryDropReason.RECORD_TOO_LARGE
                if error.code
                is ObservabilitySerializationErrorCode.RECORD_TOO_LARGE
                else DeliveryDropReason.SERIALIZATION_REJECTED
            )
            self._stats.rejected(reason)
            return DeliveryAttempt(DeliveryDisposition.REJECTED, reason)
        except Exception:
            reason = DeliveryDropReason.SERIALIZATION_REJECTED
            self._stats.rejected(reason)
            return DeliveryAttempt(DeliveryDisposition.REJECTED, reason)
        try:
            result = self._buffer.enqueue(serialized)
        except Exception:
            reason = DeliveryDropReason.SINK_FAILURE
            self._stats.dropped(reason)
            return DeliveryAttempt(DeliveryDisposition.DROPPED, reason)
        if not result.accepted:
            reason = result.reason or DeliveryDropReason.BUFFER_FULL
            self._stats.dropped(reason)
            return DeliveryAttempt(DeliveryDisposition.DROPPED, reason)
        self._stats.buffered(result.displaced_count)
        return DeliveryAttempt(
            DeliveryDisposition.BUFFERED,
            displaced_count=result.displaced_count,
        )

    def flush(self, max_items: int | None = None) -> DeliveryFlushResult:
        limit = self._flush_limit(max_items)
        if not self._policy.enabled:
            return self._flush_result(0, 0, 0)
        if not self._flush_lock.acquire(blocking=False):
            return self._flush_result(0, 0, 0, busy=True)
        attempted = 0
        delivered = 0
        failed = 0
        try:
            while attempted < limit:
                item = self._buffer.pop_oldest()
                if item is None:
                    break
                attempted += 1
                try:
                    written = self._writer.write(item.payload)
                    if type(written) is not int or written != len(item.payload):
                        raise ValueError("writer did not accept the complete record")
                except Exception:
                    failed = 1
                    self._stats.failed()
                    break
                delivered += 1
                self._stats.delivered()
            return self._flush_result(
                attempted,
                delivered,
                failed,
                limit_reached=(
                    attempted == limit
                    and self._buffer.snapshot().occupancy_items > 0
                ),
                stopped_reason=(
                    DeliveryDropReason.SINK_FAILURE if failed else None
                ),
            )
        finally:
            self._flush_lock.release()

    def health_snapshot(self) -> DeliveryHealthSnapshot:
        stats, last_failure = self._stats.snapshot()
        if not self._policy.enabled:
            status = DeliveryHealthStatus.DISABLED
            last_failure = DeliveryDropReason.CHANNEL_DISABLED
        elif last_failure is None:
            status = DeliveryHealthStatus.HEALTHY
        else:
            status = DeliveryHealthStatus.DEGRADED
        return DeliveryHealthSnapshot(
            channel=self._channel,
            status=status,
            stats=stats,
            buffer=self._buffer.snapshot(),
            last_failure_reason=last_failure,
        )

    def _flush_limit(self, value: int | None) -> int:
        if value is None:
            return self._policy.max_flush_items
        if type(value) is not int:
            raise TypeError("max_items must be an integer or None")
        if not 1 <= value <= self._policy.max_flush_items:
            raise ValueError("max_items exceeds the bounded flush policy")
        return value

    def _flush_result(
        self,
        attempted: int,
        delivered: int,
        failed: int,
        *,
        busy: bool = False,
        limit_reached: bool = False,
        stopped_reason: DeliveryDropReason | None = None,
    ) -> DeliveryFlushResult:
        return DeliveryFlushResult(
            channel=self._channel,
            attempted_count=attempted,
            delivered_count=delivered,
            failed_count=failed,
            remaining_items=self._buffer.snapshot().occupancy_items,
            busy=busy,
            limit_reached=limit_reached,
            stopped_reason=stopped_reason,
        )


class FailureIsolatedLogSink:
    def __init__(
        self,
        writer: TextRecordWriter,
        policy: ObservabilityDeliveryPolicy = (
            BASELINE_OBSERVABILITY_DELIVERY_POLICY
        ),
    ) -> None:
        self._delivery = _BufferedChannelDelivery(
            channel=ObservationChannel.LOG,
            serializer=serialize_log_record,
            writer=writer,
            policy=policy,
        )

    def emit(self, record: StructuredLogRecord) -> None:
        self._delivery.submit(record)

    def submit(self, record: StructuredLogRecord) -> DeliveryAttempt:
        return self._delivery.submit(record)

    def flush(self, max_items: int | None = None) -> DeliveryFlushResult:
        return self._delivery.flush(max_items)

    def health_snapshot(self) -> DeliveryHealthSnapshot:
        return self._delivery.health_snapshot()


class FailureIsolatedTraceSink:
    def __init__(
        self,
        writer: TextRecordWriter,
        policy: ObservabilityDeliveryPolicy = (
            BASELINE_OBSERVABILITY_DELIVERY_POLICY
        ),
    ) -> None:
        self._delivery = _BufferedChannelDelivery(
            channel=ObservationChannel.SPAN,
            serializer=serialize_span_record,
            writer=writer,
            policy=policy,
        )

    def emit(self, record: SpanRecord) -> None:
        self._delivery.submit(record)

    def submit(self, record: SpanRecord) -> DeliveryAttempt:
        return self._delivery.submit(record)

    def flush(self, max_items: int | None = None) -> DeliveryFlushResult:
        return self._delivery.flush(max_items)

    def health_snapshot(self) -> DeliveryHealthSnapshot:
        return self._delivery.health_snapshot()


class FailureIsolatedMetricSink:
    def __init__(
        self,
        writer: TextRecordWriter,
        policy: ObservabilityDeliveryPolicy = (
            BASELINE_OBSERVABILITY_DELIVERY_POLICY
        ),
    ) -> None:
        self._delivery = _BufferedChannelDelivery(
            channel=ObservationChannel.METRIC,
            serializer=serialize_metric_point,
            writer=writer,
            policy=policy,
        )

    def record(self, point: MetricPoint) -> None:
        self._delivery.submit(point)

    def submit(self, point: MetricPoint) -> DeliveryAttempt:
        return self._delivery.submit(point)

    def flush(self, max_items: int | None = None) -> DeliveryFlushResult:
        return self._delivery.flush(max_items)

    def health_snapshot(self) -> DeliveryHealthSnapshot:
        return self._delivery.health_snapshot()
