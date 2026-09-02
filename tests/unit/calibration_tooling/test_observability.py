from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from calibration_tooling.contracts.errors import CalibrationErrorCode
from calibration_tooling.contracts.models import CallRef, RunRef
from calibration_tooling.observability.events import (
    CalibrationEventState,
    CalibrationTelemetryEvent,
)
from calibration_tooling.observability.redaction import safe_event_mapping


def test_safe_mapping_contains_only_bounded_technical_fields() -> None:
    event = CalibrationTelemetryEvent(
        run_ref=RunRef("run.telemetry"),
        call_ref=CallRef("call.telemetry"),
        provider_code="anthropic",
        model_code="claude-sonnet-5",
        state=CalibrationEventState.COMPLETED,
        duration_milliseconds=19,
        input_tokens=100,
        cached_input_tokens=25,
        output_tokens=10,
        measured_cost_usd=Decimal("0.000450"),
    )

    mapping = safe_event_mapping(event)

    assert mapping == {
        "workload": "PEDAGOGICAL_CALIBRATION",
        "run_ref": "run.telemetry",
        "call_ref": "call.telemetry",
        "provider_code": "anthropic",
        "model_code": "claude-sonnet-5",
        "state": "COMPLETED",
        "duration_milliseconds": 19,
        "input_tokens": 100,
        "cached_input_tokens": 25,
        "output_tokens": 10,
        "measured_cost_usd": "0.000450",
        "error_code": None,
    }
    assert set(mapping).isdisjoint(
        {"payload", "projection", "prompt", "response", "secret", "thinking"}
    )


def test_telemetry_rejects_unsafe_identity_and_open_error_values() -> None:
    with pytest.raises(ValueError):
        CalibrationTelemetryEvent(
            run_ref=RunRef("run.telemetry"),
            provider_code="anthropic\nsecret",
            model_code="claude-sonnet-5",
            state=CalibrationEventState.STARTED,
            duration_milliseconds=0,
        )
    with pytest.raises(TypeError):
        CalibrationTelemetryEvent(
            run_ref=RunRef("run.telemetry"),
            provider_code="anthropic",
            model_code="claude-sonnet-5",
            state=CalibrationEventState.FAILED,
            duration_milliseconds=1,
            error_code=cast(CalibrationErrorCode, "raw provider failure"),
        )


def test_telemetry_state_invariants_are_fail_closed() -> None:
    with pytest.raises(ValueError):
        CalibrationTelemetryEvent(
            run_ref=RunRef("run.telemetry"),
            provider_code="anthropic",
            model_code="claude-sonnet-5",
            state=CalibrationEventState.COMPLETED,
            duration_milliseconds=1,
        )
    failed = CalibrationTelemetryEvent(
        run_ref=RunRef("run.telemetry"),
        provider_code="anthropic",
        model_code="claude-sonnet-5",
        state=CalibrationEventState.FAILED,
        duration_milliseconds=1,
        error_code=CalibrationErrorCode.PROVIDER_UNAVAILABLE,
    )
    assert safe_event_mapping(failed)["error_code"] == "PROVIDER_UNAVAILABLE"
