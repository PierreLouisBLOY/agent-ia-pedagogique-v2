from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    RecommendedAction,
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
)
from backend.agent_runtime.security import (
    SensitiveValuePolicy,
    SensitiveValueRejected,
    StructuredDataLimitCode,
    StructuredDataLimitError,
    security_event_from_sensitive_value_rejection,
    security_event_from_structured_limit_error,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.synthetic_secret_fixtures import fake_bearer_token

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


def _error(**changes: object) -> ErrorEnvelope:
    values: dict[str, object] = {
        "error_code": "SAFE_FAILURE",
        "category": ErrorCategory.UNKNOWN,
        "source": ErrorSource.AGENT,
        "retryable": False,
        "severity": ErrorSeverity.ERROR,
        "message": "A safe public failure",
        "step_id": "step-f",
        "attempt": 1,
        "effect_state": EffectState.NONE,
        "recommended_action": RecommendedAction.STOP,
        "details": {},
    }
    values.update(changes)
    return ErrorEnvelope(**values)  # type: ignore[arg-type]


def _event(**changes: object) -> SecurityEvent:
    values: dict[str, object] = {
        "schema_version": AGENT_CONTRACT_SCHEMA_V1_0,
        "event_id": "event-f",
        "event_type": SecurityEventType.SECRET_EXPOSURE,
        "severity": SecuritySeverity.CRITICAL,
        "boundary": SecurityBoundary.AGENT,
        "reason_code": SecurityReasonCode("SECRET.AUTH_TOKEN_LIKE"),
        "occurred_at": NOW,
        "run_id": "run-f",
        "correlation_id": CorrelationId("corr-f"),
        "metadata": {"classification": "AUTH_TOKEN_LIKE"},
    }
    values.update(changes)
    return SecurityEvent(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    (
        {"message": fake_bearer_token()},
        {"details": {"note": fake_bearer_token()}},
    ),
)
def test_error_envelope_rejects_secret_like_message_or_neutral_details(
    changes: dict[str, object],
) -> None:
    raw = fake_bearer_token()

    with pytest.raises(SensitiveValueRejected) as raised:
        _error(**changes)

    assert raw not in str(raised.value)


def test_error_envelope_bounds_message_refs_and_details() -> None:
    with pytest.raises(StructuredDataLimitError) as text_error:
        _error(message="x" * 1_025)
    with pytest.raises(ValueError, match="at most 16"):
        _error(related_refs=tuple(f"ref-{index}" for index in range(17)))
    with pytest.raises(StructuredDataLimitError) as details_error:
        _error(details={"items": list(range(65))})

    assert text_error.value.code is StructuredDataLimitCode.MAX_STRING_LENGTH_EXCEEDED
    assert details_error.value.code is StructuredDataLimitCode.MAX_SEQUENCE_ITEMS_EXCEEDED


def test_security_event_rejects_secret_under_neutral_metadata_key_without_echo() -> None:
    raw = fake_bearer_token()

    with pytest.raises(SensitiveValueRejected) as raised:
        _event(metadata={"note": raw})

    assert raw not in str(raised.value)


def test_security_event_factories_are_raw_free_and_use_existing_event_types() -> None:
    raw = fake_bearer_token()
    with pytest.raises(SensitiveValueRejected) as sensitive:
        SensitiveValuePolicy().require_safe(raw, root_location="tool.output")
    exposure = security_event_from_sensitive_value_rejection(
        sensitive.value,
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        event_id="event-secret-f",
        occurred_at=NOW,
        run_id="run-f",
        correlation_id=CorrelationId("corr-f"),
        boundary=SecurityBoundary.TOOL,
    )
    exfiltration = security_event_from_sensitive_value_rejection(
        sensitive.value,
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        event_id="event-exfil-f",
        occurred_at=NOW,
        run_id="run-f",
        correlation_id=CorrelationId("corr-f"),
        boundary=SecurityBoundary.TOOL,
        exfiltration_requested=True,
    )

    assert exposure.event_type is SecurityEventType.SECRET_EXPOSURE
    assert exfiltration.event_type is SecurityEventType.SECRET_EXFILTRATION_ATTEMPT
    assert raw not in repr(exposure)
    assert raw not in repr(exfiltration)

    limit = StructuredDataLimitError(
        StructuredDataLimitCode.MAX_DEPTH_EXCEEDED,
        "tool.output",
    )
    limit_event = security_event_from_structured_limit_error(
        limit,
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        event_id="event-limit-f",
        occurred_at=NOW,
        run_id="run-f",
        correlation_id=CorrelationId("corr-f"),
        boundary=SecurityBoundary.TOOL,
    )
    assert limit_event.event_type is SecurityEventType.INPUT_LIMIT_EXCEEDED


def test_security_event_nested_metadata_limit_is_enforced() -> None:
    with pytest.raises(StructuredDataLimitError) as raised:
        _event(metadata={"nested": {f"field_{index}": index for index in range(33)}})

    assert raised.value.code is StructuredDataLimitCode.MAX_MAPPING_KEYS_EXCEEDED
