from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from calibration_tooling.contracts.errors import CalibrationErrorCode
from calibration_tooling.contracts.models import (
    CalibrationObservationResult,
    CalibrationObservationSpec,
    CallLedgerRecord,
    CallRef,
    RawProviderResponse,
    ScoredCall,
)


class ProviderTransportPort(Protocol):
    def invoke(self, spec: CalibrationObservationSpec) -> RawProviderResponse: ...


class CalibrationOutputParserPort(Protocol):
    def parse(
        self,
        spec: CalibrationObservationSpec,
        response: RawProviderResponse,
    ) -> CalibrationObservationResult: ...


class CalibrationServicePort(Protocol):
    def evaluate(self, spec: CalibrationObservationSpec) -> ScoredCall: ...


class CallLedgerPort(Protocol):
    def reserve(self, call_ref: CallRef) -> None: ...

    def complete(
        self,
        result: CalibrationObservationResult,
        measured_cost_usd: Decimal,
    ) -> None: ...

    def fail(
        self,
        call_ref: CallRef,
        error_code: CalibrationErrorCode,
        measured_cost_usd: Decimal | None = None,
    ) -> None: ...

    def snapshot(self) -> tuple[CallLedgerRecord, ...]: ...


class MonotonicClockPort(Protocol):
    def now_milliseconds(self) -> int: ...
