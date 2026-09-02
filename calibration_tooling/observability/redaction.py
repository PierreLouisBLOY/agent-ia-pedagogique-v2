"""Serialize only the allowlisted, content-free calibration telemetry fields."""

from __future__ import annotations

from calibration_tooling.observability.events import CalibrationTelemetryEvent

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
