from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    LogLevel,
    ObservationCode,
    SamplingDecision,
    SpanId,
    StructuredLogRecord,
    TraceContext,
    TraceId,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


def _record(**changes: object) -> StructuredLogRecord:
    values: dict[str, object] = {
        "schema_version": AGENT_CONTRACT_SCHEMA_V1_0,
        "record_id": "log-record:01",
        "occurred_at": NOW,
        "level": LogLevel.INFO,
        "code": ObservationCode("RUNTIME.STEP_STARTED"),
        "correlation_id": CorrelationId("correlation-01"),
        "run_id": "run-01",
        "step_id": "step-01",
        "trace_context": TraceContext(
            TraceId("trace-01"),
            SpanId("span-01"),
            None,
            SamplingDecision.RECORD_ONLY,
        ),
        "refs": ("plan:01",),
        "attributes": {"route": "APPLICATION", "attempt": 1},
    }
    values.update(changes)
    return StructuredLogRecord(**values)  # type: ignore[arg-type]


def test_structured_log_record_is_code_first_immutable_and_message_free() -> None:
    record = _record()
    names = {item.name for item in fields(StructuredLogRecord)}

    assert names == {
        "schema_version",
        "record_id",
        "occurred_at",
        "level",
        "code",
        "correlation_id",
        "run_id",
        "step_id",
        "trace_context",
        "refs",
        "attributes",
    }
    assert names.isdisjoint({"message", "authority", "decision", "payload"})
    assert isinstance(record.attributes, MappingProxyType)
    assert not hasattr(record, "__dict__")
    with pytest.raises(FrozenInstanceError):
        record.level = LogLevel.ERROR  # type: ignore[misc]


def test_log_level_and_observation_code_are_distinct_closed_vocabularies() -> None:
    assert [item.value for item in LogLevel] == [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]
    assert str(ObservationCode("RECOVERY.REPLAY_BLOCKED")) == (
        "RECOVERY.REPLAY_BLOCKED"
    )
    for value in ("", "lowercase", "HAS SPACE", "1_INVALID", "A" * 129):
        with pytest.raises(ValueError, match="closed code"):
            ObservationCode(value)


@pytest.mark.parametrize(
    "unsafe_key",
    [
        "prompt",
        "rawPrompt",
        "document_text",
        "evidenceExcerpt",
        "tool_output",
        "applicationPayload",
        "provider_response",
        "error_message",
        "errorDetails",
        "raw_idempotency_key",
        "local_path",
        "stack_trace",
        "private_reasoning",
    ],
)
def test_structured_log_rejects_raw_or_sensitive_attribute_keys(
    unsafe_key: str,
) -> None:
    with pytest.raises(ValueError):
        _record(attributes={"nested": {unsafe_key: "redacted"}})


@pytest.mark.parametrize(
    "attributes",
    [
        {"value": "C:\\private\\report.txt"},
        {"value": "Bearer " + "a" * 40},
        {"value": float("nan")},
        {"value": float("inf")},
    ],
)
def test_structured_log_rejects_sensitive_or_non_finite_values(
    attributes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _record(attributes=attributes)


def test_structured_log_rejects_unbounded_attributes_and_raw_refs() -> None:
    with pytest.raises(ValueError, match="at most 16"):
        _record(refs=tuple(f"ref:{index}" for index in range(17)))
    with pytest.raises(ValueError, match="opaque"):
        _record(refs=("https://example.test/private",))
    with pytest.raises(ValueError):
        _record(attributes={f"field_{index}": index for index in range(33)})


def test_structured_log_requires_utc_and_safe_correlation() -> None:
    non_utc = Instant(
        datetime(2026, 8, 27, 13, 0, tzinfo=timezone(timedelta(hours=1)))
    )

    with pytest.raises(ValueError, match="UTC"):
        _record(occurred_at=non_utc)
    with pytest.raises(ValueError, match="correlation_id"):
        _record(correlation_id=CorrelationId("../private"))
