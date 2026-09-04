from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from calibration_tooling.contracts.errors import CalibrationErrorCode
from calibration_tooling.contracts.models import AuthorizationRef, CallRef, RunRef
from calibration_tooling.observability.events import (
    CalibrationEventState,
    CalibrationTelemetryEvent,
)
from calibration_tooling.observability.redaction import (
    OperationalCalibrationTelemetrySink,
    safe_event_mapping,
)


def test_safe_mapping_contains_only_bounded_technical_fields() -> None:
    event = CalibrationTelemetryEvent(
        run_ref=RunRef("run.telemetry"),
        call_ref=CallRef("call.telemetry"),
        authorization_ref=AuthorizationRef("auth.telemetry"),
        attempt_number=1,
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
        "authorization_ref": "auth.telemetry",
        "attempt_number": 1,
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


class RecordingOperationalEmitter:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | int | bool | None]] = []

    def provider_call(
        self,
        *,
        state: str,
        provider_id: str,
        call_id: str,
        model_profile_id: str | None = None,
        authorization_id: str | None = None,
        input_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: str | None = None,
        duration_ms: int = 0,
        provider_error_code: str | None = None,
        authorization_consumed: bool | None = None,
    ) -> None:
        self.calls.append(
            {
                "state": state,
                "provider_id": provider_id,
                "call_id": call_id,
                "model_profile_id": model_profile_id,
                "authorization_id": authorization_id,
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "duration_ms": duration_ms,
                "provider_error_code": provider_error_code,
                "authorization_consumed": authorization_consumed,
            }
        )


def test_call_telemetry_bridge_emits_only_minimized_provider_fields() -> None:
    emitter = RecordingOperationalEmitter()
    sink = OperationalCalibrationTelemetrySink(emitter)
    sink.emit(
        CalibrationTelemetryEvent(
            run_ref=RunRef("run.telemetry"),
            call_ref=CallRef("call.telemetry"),
            authorization_ref=AuthorizationRef("auth.telemetry"),
            attempt_number=1,
            provider_code="anthropic",
            model_code="claude-sonnet-5",
            state=CalibrationEventState.COMPLETED,
            duration_milliseconds=19,
            input_tokens=100,
            cached_input_tokens=25,
            output_tokens=10,
            measured_cost_usd=Decimal("0.000450"),
        )
    )

    assert emitter.calls == [
        {
            "state": "COMPLETED",
            "provider_id": "anthropic",
            "call_id": "call.telemetry",
            "model_profile_id": None,
            "authorization_id": None,
            "input_tokens": 100,
            "cached_input_tokens": 25,
            "output_tokens": 10,
            "cost_usd": "0.000450",
            "duration_ms": 19,
            "provider_error_code": None,
            "authorization_consumed": None,
        }
    ]
