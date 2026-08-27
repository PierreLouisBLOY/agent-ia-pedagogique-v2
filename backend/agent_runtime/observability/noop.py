from __future__ import annotations

from backend.agent_runtime.contracts import MetricPoint, SpanRecord, StructuredLogRecord


class NullLogSink:
    """Provider-neutral disabled log channel without I/O or state."""

    def emit(self, record: StructuredLogRecord) -> None:
        del record


class NullTraceSink:
    """Provider-neutral disabled trace channel without I/O or state."""

    def emit(self, record: SpanRecord) -> None:
        del record


class NullMetricSink:
    """Provider-neutral disabled metric channel without I/O or state."""

    def record(self, point: MetricPoint) -> None:
        del point
