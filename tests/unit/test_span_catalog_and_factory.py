from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest

from backend.agent_runtime.contracts import (
    SamplingDecision,
    SpanId,
    SpanKind,
    SpanRecord,
    SpanStatus,
    TraceContext,
    TraceId,
)
from backend.agent_runtime.observability import (
    SpanCode,
    StructuredLogCode,
    TraceContextPolicy,
    completed_span,
    span_observation_code,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

STARTED = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
ENDED = Instant(datetime(2026, 8, 27, 12, 0, 1, tzinfo=UTC))


def _context() -> TraceContext:
    return TraceContextPolicy().root(
        trace_id=TraceId("trace-run-01"),
        span_id=SpanId("span-step-01"),
        sampling_decision=SamplingDecision.RECORD_AND_SAMPLE,
    )


def _span(**changes: object) -> SpanRecord:
    values: dict[str, object] = {
        "trace_context": _context(),
        "code": SpanCode.RUNTIME_STEP,
        "kind": SpanKind.RUNTIME,
        "status": SpanStatus.OK,
        "started_at": STARTED,
        "ended_at": ENDED,
        "correlation_id": CorrelationId("correlation-01"),
        "run_id": "run-01",
        "step_id": "step-01",
        "refs": ("plan:01",),
        "attributes": {"attempt": 1, "route": "AGENT"},
    }
    values.update(changes)
    return completed_span(**values)  # type: ignore[arg-type]


def test_span_catalog_is_closed_unique_and_distinct_from_log_catalog() -> None:
    assert [item.value for item in SpanCode] == [
        "RUNTIME.CYCLE",
        "RUNTIME.STEP",
        "ROUTING.PRELAUNCH",
        "AGENT.INVOCATION",
        "TOOL.CALL",
        "APPLICATION.CALL",
        "GATE.EVALUATION",
        "RECOVERY.CYCLE",
        "RECOVERY.RECONCILIATION",
        "RECOVERY.RETRY",
    ]
    assert len({item.value for item in SpanCode}) == len(SpanCode)
    assert type(SpanCode.RUNTIME_STEP) is SpanCode
    assert type(StructuredLogCode.RUNTIME_STOPPED) is StructuredLogCode
    assert span_observation_code(SpanCode.TOOL_CALL).value == "TOOL.CALL"


def test_completed_span_factory_composes_only_completed_immutable_data() -> None:
    span = _span()

    assert span.trace_context == _context()
    assert span.code.value == "RUNTIME.STEP"
    assert span.started_at == STARTED
    assert span.ended_at == ENDED
    assert span.correlation_id == CorrelationId("correlation-01")
    assert span.refs == ("plan:01",)
    assert span.attributes == {"attempt": 1, "route": "AGENT"}
    assert isinstance(span.attributes, MappingProxyType)
    assert not hasattr(span, "__dict__")


def test_completed_span_is_deterministic_for_identical_explicit_inputs() -> None:
    assert _span() == _span()


def test_completed_span_requires_closed_code_and_valid_interval() -> None:
    with pytest.raises(TypeError, match="SpanCode"):
        _span(code=StructuredLogCode.RUNTIME_STOPPED)
    with pytest.raises(ValueError, match="ended_at"):
        _span(ended_at=Instant(STARTED.value - timedelta(seconds=1)))


@pytest.mark.parametrize(
    "attributes",
    [
        {"payload": {"lesson": "private"}},
        {"error_message": "private failure"},
        {"provider_response": {"body": "private"}},
        {"local_path": "opaque-private-value"},
    ],
)
def test_completed_span_reuses_b_privacy_guards(
    attributes: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="forbidden"):
        _span(attributes=attributes)


def test_span_status_ok_has_no_domain_or_gate_authority_field() -> None:
    names = {item.name for item in fields(type(_span()))}

    assert names.isdisjoint(
        {
            "authority",
            "decision",
            "domain_validated",
            "gate_approved",
            "permission",
            "retry_decision",
        }
    )
