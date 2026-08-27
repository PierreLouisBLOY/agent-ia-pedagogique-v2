from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts.observability import (
    MetricPoint,
    SpanRecord,
    StructuredLogRecord,
)


@runtime_checkable
class LogSinkPort(Protocol):
    """Synchronous best-effort delivery of one log record; no durability contract."""

    def emit(self, record: StructuredLogRecord) -> None: ...


@runtime_checkable
class TraceSinkPort(Protocol):
    """Synchronous best-effort delivery of one completed span record."""

    def emit(self, record: SpanRecord) -> None: ...


@runtime_checkable
class MetricSinkPort(Protocol):
    """Synchronous best-effort delivery of one metric point."""

    def record(self, point: MetricPoint) -> None: ...
