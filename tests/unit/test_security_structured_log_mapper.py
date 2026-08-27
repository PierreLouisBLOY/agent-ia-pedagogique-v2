from __future__ import annotations

from datetime import UTC, datetime

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    LogLevel,
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
)
from backend.agent_runtime.observability import structured_log_from_security_event
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


def _event() -> SecurityEvent:
    return SecurityEvent(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        event_id="security-event:01",
        event_type=SecurityEventType.INDIRECT_CONTENT_INJECTION,
        severity=SecuritySeverity.HIGH,
        boundary=SecurityBoundary.DOCUMENT,
        reason_code=SecurityReasonCode("SECURITY.INJECTION.INDIRECT"),
        occurred_at=NOW,
        run_id="run-01",
        correlation_id=CorrelationId("correlation-01"),
        step_id="step-01",
        refs=("document:01",),
        metadata={
            "detector_id": "detector-01",
            "signals": ("instruction_override", "authority_claim"),
            "confidence_basis": {"rule_count": 2},
        },
    )


def test_security_mapper_preserves_owner_facts_without_metadata() -> None:
    event = _event()

    record = structured_log_from_security_event(event, record_id="log:security:01")

    assert record.schema_version == event.schema_version
    assert record.occurred_at == event.occurred_at
    assert record.level is LogLevel.ERROR
    assert record.code.value == "SECURITY.INDIRECT_CONTENT_INJECTION"
    assert record.correlation_id == event.correlation_id
    assert record.run_id == event.run_id
    assert record.step_id == event.step_id
    assert record.refs == ()
    assert record.attributes == {
        "event_type": "indirect_content_injection",
        "severity": "high",
        "boundary": "document",
        "reason_code": "SECURITY.INJECTION.INDIRECT",
        "ref_count": 1,
    }


def test_security_mapper_never_copies_detailed_metadata() -> None:
    record = structured_log_from_security_event(
        _event(), record_id="log:security:02"
    )
    serialized = repr(dict(record.attributes))

    assert "metadata" not in record.attributes
    assert "detector-01" not in serialized
    assert "instruction_override" not in serialized
    assert "confidence_basis" not in serialized


def test_security_mapper_is_detached_from_later_source_tampering() -> None:
    event = _event()
    record = structured_log_from_security_event(event, record_id="log:security:03")

    object.__setattr__(event, "metadata", {"detector_id": "changed"})

    assert "changed" not in repr(dict(record.attributes))
