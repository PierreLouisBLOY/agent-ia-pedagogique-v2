from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ContentOrigin,
    ContentRole,
    ContentTrustClass,
    ContentTrustLabel,
    ErrorSeverity,
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


def _event(**changes: object) -> SecurityEvent:
    values: dict[str, object] = {
        "schema_version": AGENT_CONTRACT_SCHEMA_V1_0,
        "event_id": "security-event:v1:01",
        "event_type": SecurityEventType.INDIRECT_CONTENT_INJECTION,
        "severity": SecuritySeverity.HIGH,
        "boundary": SecurityBoundary.DOCUMENT,
        "reason_code": SecurityReasonCode("SECURITY.INJECTION.INDIRECT"),
        "occurred_at": NOW,
        "run_id": "run-1",
        "correlation_id": CorrelationId("correlation-1"),
        "step_id": "step-1",
        "refs": ("document:lesson-1",),
        "content_label": ContentTrustLabel(
            origin=ContentOrigin.DOCUMENT,
            role=ContentRole.INSTRUCTION,
            trust_class=ContentTrustClass.UNTRUSTED,
            source_ref="document:lesson-1",
        ),
        "metadata": {"detector_id": "detector-1", "signals": ["pattern-1"]},
    }
    values.update(changes)
    return SecurityEvent(**values)  # type: ignore[arg-type]


def test_security_event_type_vocabulary_is_closed() -> None:
    assert {item.name for item in SecurityEventType} == {
        "DIRECT_PROMPT_INJECTION",
        "INDIRECT_CONTENT_INJECTION",
        "TOOL_INJECTION",
        "APPLICATION_INJECTION",
        "AGENT_HANDOFF_VIOLATION",
        "AUTHORITY_SMUGGLING",
        "SECRET_EXFILTRATION_ATTEMPT",
        "SECRET_EXPOSURE",
        "HOSTILE_CONTENT_PROPAGATION",
        "TRUST_BOUNDARY_VIOLATION",
        "INPUT_LIMIT_EXCEEDED",
    }


def test_security_severity_is_distinct_from_operational_error_severity() -> None:
    assert {item.name for item in SecuritySeverity} == {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }
    assert SecuritySeverity.HIGH != ErrorSeverity.ERROR
    assert SecuritySeverity.MEDIUM.value not in {item.value for item in ErrorSeverity}


@pytest.mark.parametrize(
    "value",
    ["", "lowercase", "1_INVALID", "HAS SPACE", "A" * 129, "RAW/PATH"],
)
def test_security_reason_code_rejects_open_or_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError, match="safe closed security reason code"):
        SecurityReasonCode(value)


def test_security_reason_code_accepts_canonical_bounded_value() -> None:
    code = SecurityReasonCode("SECURITY.TRUST-VIOLATION_01")

    assert str(code) == "SECURITY.TRUST-VIOLATION_01"


def test_security_event_is_immutable_minimal_and_data_only() -> None:
    event = _event()
    names = {item.name for item in fields(SecurityEvent)}

    assert names == {
        "schema_version",
        "event_id",
        "event_type",
        "severity",
        "boundary",
        "reason_code",
        "occurred_at",
        "run_id",
        "correlation_id",
        "step_id",
        "refs",
        "content_label",
        "metadata",
    }
    assert names.isdisjoint(
        {
            "message",
            "summary",
            "description",
            "prompt",
            "document",
            "payload",
            "idempotency_key",
            "decision",
            "authority",
        }
    )
    assert not hasattr(event, "__dict__")
    with pytest.raises(FrozenInstanceError):
        event.severity = SecuritySeverity.LOW  # type: ignore[misc]


def test_security_event_content_label_is_optional() -> None:
    event = _event(content_label=None)

    assert event.content_label is None


def test_security_event_freezes_metadata_recursively() -> None:
    event = _event(metadata={"signals": ["pattern-1"], "nested": {"count": 1}})

    assert isinstance(event.metadata, MappingProxyType)
    assert event.metadata["signals"] == ("pattern-1",)
    assert isinstance(event.metadata["nested"], MappingProxyType)
    with pytest.raises(TypeError):
        event.metadata["new"] = "value"  # type: ignore[index]


@pytest.mark.parametrize(
    "unsafe_key",
    [
        "password",
        "client_secret",
        "api_key",
        "access_token",
        "provider_payload",
        "local_path",
        "stack_trace",
        "system_prompt",
        "private_reasoning",
        "prompt",
        "document",
        "payload",
        "content",
        "credential",
        "tool_output",
        "application_output",
        "raw_idempotency_key",
    ],
)
def test_security_event_rejects_unsafe_or_raw_metadata_keys(unsafe_key: str) -> None:
    with pytest.raises(ValueError):
        _event(metadata={"nested": {unsafe_key: "redacted-or-raw"}})


def test_security_event_rejects_raw_exception_metadata() -> None:
    with pytest.raises(TypeError, match="raw exceptions"):
        _event(metadata={"failure": RuntimeError("private runtime detail")})


@pytest.mark.parametrize("ref", ["C:\\private\\result.txt", "https://example.test/a"])
def test_security_event_rejects_path_or_url_string_refs(ref: str) -> None:
    with pytest.raises(ValueError, match="opaque identifiers"):
        _event(refs=(ref,))


def test_security_event_refs_are_bounded_unique_and_immutable() -> None:
    with pytest.raises(TypeError, match="immutable tuple"):
        _event(refs=["document:1"])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="unique"):
        _event(refs=("document:1", "document:1"))
    with pytest.raises(ValueError, match="at most 16"):
        _event(refs=tuple(f"ref:{index}" for index in range(17)))


def test_security_event_metadata_is_locally_bounded() -> None:
    with pytest.raises(ValueError, match="at most 32"):
        _event(metadata={f"key_{index}": index for index in range(33)})


def test_security_event_requires_utc_and_safe_opaque_identifiers() -> None:
    non_utc = Instant(datetime(2026, 8, 27, 13, 0, tzinfo=timezone(timedelta(hours=1))))

    with pytest.raises(ValueError, match="occurred_at must be UTC"):
        _event(occurred_at=non_utc)
    with pytest.raises(ValueError, match="event_id must be a bounded opaque"):
        _event(event_id="security event 1")
    with pytest.raises(ValueError, match="run_id must be a bounded opaque"):
        _event(run_id="../run")


def test_security_event_rejects_untyped_boundary_fields() -> None:
    with pytest.raises(TypeError, match="event_type must be"):
        _event(event_type="indirect_prompt_injection")
    with pytest.raises(TypeError, match="reason_code must be"):
        _event(reason_code="SECURITY.INJECTION.INDIRECT")
