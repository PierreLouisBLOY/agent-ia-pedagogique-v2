from __future__ import annotations

from datetime import timedelta

from backend.agent_runtime.contracts import (
    MetricPoint,
    SpanId,
    SpanRecord,
    StructuredLogRecord,
)
from backend.shared_kernel.time import Instant


class DeterministicObservationProvider:
    def __init__(self, *, prefix: str = "observation") -> None:
        self._prefix = prefix
        self._record_count = 0
        self._span_count = 0

    def new_record_id(self) -> str:
        self._record_count += 1
        return f"{self._prefix}-record-{self._record_count}"

    def new_span_id(self) -> SpanId:
        self._span_count += 1
        return SpanId(f"{self._prefix}-span-{self._span_count}")


class AdvancingObservationClock:
    def __init__(self, initial: Instant) -> None:
        self._current = initial

    def now(self) -> Instant:
        value = self._current
        self._current = Instant(value.value + timedelta(microseconds=1))
        return value


class CollectingLogSink:
    def __init__(self) -> None:
        self.records: list[StructuredLogRecord] = []

    def emit(self, record: StructuredLogRecord) -> None:
        self.records.append(record)


class CollectingTraceSink:
    def __init__(self) -> None:
        self.records: list[SpanRecord] = []

    def emit(self, record: SpanRecord) -> None:
        self.records.append(record)


class CollectingMetricSink:
    def __init__(self) -> None:
        self.points: list[MetricPoint] = []

    def record(self, point: MetricPoint) -> None:
        self.points.append(point)


class RaisingLogSink:
    def emit(self, record: StructuredLogRecord) -> None:
        del record
        raise RuntimeError("synthetic log sink failure")


class RaisingTraceSink:
    def emit(self, record: SpanRecord) -> None:
        del record
        raise RuntimeError("synthetic trace sink failure")


class RaisingMetricSink:
    def record(self, point: MetricPoint) -> None:
        del point
        raise RuntimeError("synthetic metric sink failure")


class RaisingObservationProvider:
    def new_record_id(self) -> str:
        raise RuntimeError("synthetic observation id failure")

    def new_span_id(self) -> SpanId:
        raise RuntimeError("synthetic observation id failure")


class RaisingObservationClock:
    def now(self) -> Instant:
        raise RuntimeError("synthetic observation clock failure")
