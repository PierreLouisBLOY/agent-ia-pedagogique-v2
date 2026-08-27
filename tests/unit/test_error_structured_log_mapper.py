from __future__ import annotations

from datetime import UTC, datetime

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    LogLevel,
    RecommendedAction,
)
from backend.agent_runtime.observability import structured_log_from_error_envelope
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


def _error() -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="PROVIDER_TEMPORARY_FAILURE",
        category=ErrorCategory.TRANSIENT,
        source=ErrorSource.PROVIDER,
        retryable=True,
        severity=ErrorSeverity.WARNING,
        message="Detailed provider failure narrative excluded from logs",
        step_id="step-01",
        attempt=2,
        effect_state=EffectState.UNKNOWN,
        related_refs=("request:01", "provider-call:01"),
        recommended_action=RecommendedAction.INSPECT,
        details={
            "provider_response": {"status": "temporarily_unavailable"},
            "diagnostic_notes": ("upstream timeout",),
        },
    )


def test_error_mapper_uses_caller_context_and_explicit_error_facts() -> None:
    record = structured_log_from_error_envelope(
        _error(),
        correlation_id=CorrelationId("correlation-01"),
        run_id="run-01",
        occurred_at=NOW,
        record_id="log:error:01",
    )

    assert record.occurred_at == NOW
    assert record.level is LogLevel.WARNING
    assert record.code.value == "ERROR.ENVELOPE"
    assert record.correlation_id == CorrelationId("correlation-01")
    assert record.run_id == "run-01"
    assert record.step_id == "step-01"
    assert record.refs == ()
    assert record.attributes == {
        "error_code": "PROVIDER_TEMPORARY_FAILURE",
        "category": "transient",
        "source": "provider",
        "retryable": True,
        "severity": "warning",
        "effect_state": "unknown",
        "recommended_action": "inspect",
        "attempt": 2,
        "related_ref_count": 2,
    }


def test_error_mapper_excludes_message_details_and_related_refs() -> None:
    record = structured_log_from_error_envelope(
        _error(),
        correlation_id=CorrelationId("correlation-01"),
        run_id="run-01",
        occurred_at=NOW,
        record_id="log:error:02",
    )
    serialized = repr(dict(record.attributes))

    assert "message" not in record.attributes
    assert "details" not in record.attributes
    assert "provider_response" not in serialized
    assert "upstream timeout" not in serialized
    assert "Detailed provider failure" not in serialized
    assert "request:01" not in serialized


def test_error_mapper_is_deterministic_for_identical_explicit_inputs() -> None:
    arguments = {
        "correlation_id": CorrelationId("correlation-01"),
        "run_id": "run-01",
        "occurred_at": NOW,
        "record_id": "log:error:03",
    }

    first = structured_log_from_error_envelope(_error(), **arguments)
    second = structured_log_from_error_envelope(_error(), **arguments)

    assert first == second
