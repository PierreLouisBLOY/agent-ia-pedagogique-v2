"""Bounded technical telemetry contracts for calibration execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final, Protocol

from calibration_tooling.contracts.errors import CalibrationErrorCode
from calibration_tooling.contracts.models import CallRef, RunRef

_SAFE_CODE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_DURATION_MILLISECONDS: Final = 604_800_000
_MAX_TELEMETRY_TOKENS: Final = 10**12
_MAX_TELEMETRY_COST_USD: Final = Decimal("1000000")


class CalibrationEventState(StrEnum):
    BLOCKED = "BLOCKED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CalibrationTelemetryEvent:
    run_ref: RunRef
    provider_code: str
    model_code: str
    state: CalibrationEventState
    duration_milliseconds: int
    call_ref: CallRef | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    measured_cost_usd: Decimal | None = None
    error_code: CalibrationErrorCode | None = None

    def __post_init__(self) -> None:
        if type(self.run_ref) is not RunRef:
            raise TypeError("run_ref must be a RunRef")
        if self.call_ref is not None and type(self.call_ref) is not CallRef:
            raise TypeError("call_ref must be a CallRef or None")
        _require_safe_code(self.provider_code, "provider_code")
        _require_safe_code(self.model_code, "model_code")
        if not isinstance(self.state, CalibrationEventState):
            raise TypeError("state must be a CalibrationEventState")
        if (
            type(self.duration_milliseconds) is not int
            or not 0 <= self.duration_milliseconds <= _MAX_DURATION_MILLISECONDS
        ):
            raise ValueError("duration_milliseconds is outside the telemetry limit")
        for value in (
            self.input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
        ):
            if value is not None and (
                type(value) is not int or not 0 <= value <= _MAX_TELEMETRY_TOKENS
            ):
                raise ValueError("token counters must be bounded non-negative integers")
        if self.measured_cost_usd is not None:
            _require_cost(self.measured_cost_usd)
        if self.error_code is not None and not isinstance(
            self.error_code, CalibrationErrorCode
        ):
            raise TypeError("error_code must be closed")
        if self.state is CalibrationEventState.STARTED and (
            self.duration_milliseconds != 0
            or self.measured_cost_usd is not None
            or self.error_code is not None
        ):
            raise ValueError("a started event cannot contain terminal fields")
        if self.state is CalibrationEventState.COMPLETED and (
            self.measured_cost_usd is None or self.error_code is not None
        ):
            raise ValueError("a completed event requires cost and no error")
        if self.state in {
            CalibrationEventState.BLOCKED,
            CalibrationEventState.FAILED,
        } and self.error_code is None:
            raise ValueError("a blocked or failed event requires a closed error")


class CalibrationTelemetrySink(Protocol):
    def emit(self, event: CalibrationTelemetryEvent) -> None: ...


class NullCalibrationTelemetrySink:
    """Disabled best-effort telemetry channel without I/O or retained state."""

    def emit(self, event: CalibrationTelemetryEvent) -> None:
        del event


def _require_safe_code(value: str, field_name: str) -> None:
    if type(value) is not str or _SAFE_CODE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a bounded opaque code")


def _require_cost(value: Decimal) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError("telemetry cost must be a finite Decimal")
    if not Decimal("0") <= value <= _MAX_TELEMETRY_COST_USD:
        raise ValueError("telemetry cost is outside the active limit")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -6:
        raise ValueError("telemetry cost precision exceeds six decimal places")
