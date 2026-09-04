"""Serialize only the allowlisted, content-free calibration telemetry fields."""

from __future__ import annotations

from typing import Protocol

from calibration_tooling.observability.events import (
    CalibrationEventState,
    CalibrationTelemetryEvent,
)

type SafeTelemetryValue = str | int | None


def safe_event_mapping(
    event: CalibrationTelemetryEvent,
) -> dict[str, SafeTelemetryValue]:
    if type(event) is not CalibrationTelemetryEvent:
        raise TypeError("event must be a CalibrationTelemetryEvent")
    return {
        "workload": "PEDAGOGICAL_CALIBRATION",
        "run_ref": event.run_ref.value,
        "call_ref": event.call_ref.value if event.call_ref is not None else None,
        "authorization_ref": (
            event.authorization_ref.value
            if event.authorization_ref is not None
            else None
        ),
        "attempt_number": event.attempt_number,
        "provider_code": event.provider_code,
        "model_code": event.model_code,
        "state": event.state.value,
        "duration_milliseconds": event.duration_milliseconds,
        "input_tokens": event.input_tokens,
        "cached_input_tokens": event.cached_input_tokens,
        "output_tokens": event.output_tokens,
        "measured_cost_usd": (
            format(event.measured_cost_usd, "f")
            if event.measured_cost_usd is not None
            else None
        ),
        "error_code": event.error_code.value if event.error_code is not None else None,
    }


class OperationalProviderEmitter(Protocol):
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
    ) -> None: ...


class OperationalCalibrationTelemetrySink:
    """Bridge call-level calibration telemetry to the local operational sink."""

    def __init__(self, emitter: OperationalProviderEmitter) -> None:
        self._emitter = emitter

    def emit(self, event: CalibrationTelemetryEvent) -> None:
        if type(event) is not CalibrationTelemetryEvent or event.call_ref is None:
            return
        if event.state is CalibrationEventState.STARTED:
            assert event.authorization_ref is not None
            self._emitter.provider_call(
                state=event.state.value,
                provider_id=event.provider_code,
                model_profile_id=event.model_code,
                call_id=event.call_ref.value,
                authorization_id=event.authorization_ref.value,
            )
            return
        if event.state is CalibrationEventState.COMPLETED:
            assert event.input_tokens is not None
            assert event.output_tokens is not None
            assert event.measured_cost_usd is not None
            self._emitter.provider_call(
                state=event.state.value,
                provider_id=event.provider_code,
                call_id=event.call_ref.value,
                input_tokens=event.input_tokens,
                cached_input_tokens=event.cached_input_tokens,
                output_tokens=event.output_tokens,
                cost_usd=format(event.measured_cost_usd, "f"),
                duration_ms=event.duration_milliseconds,
            )
            return
        if event.state is CalibrationEventState.FAILED:
            assert event.error_code is not None
            self._emitter.provider_call(
                state=event.state.value,
                provider_id=event.provider_code,
                call_id=event.call_ref.value,
                duration_ms=event.duration_milliseconds,
                provider_error_code=event.error_code.value,
                authorization_consumed=True,
            )
