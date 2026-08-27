from __future__ import annotations

from backend.agent_runtime.observability import (
    LogSinkPort,
    MetricSinkPort,
    TraceSinkPort,
)


class _LogSink:
    def emit(self, record: object) -> None:
        del record


class _TraceSink:
    def emit(self, record: object) -> None:
        del record


class _MetricSink:
    def record(self, point: object) -> None:
        del point


def test_sink_ports_are_structural_and_separate() -> None:
    assert isinstance(_LogSink(), LogSinkPort)
    assert isinstance(_TraceSink(), TraceSinkPort)
    assert isinstance(_MetricSink(), MetricSinkPort)
    assert LogSinkPort is not TraceSinkPort
    assert TraceSinkPort is not MetricSinkPort
