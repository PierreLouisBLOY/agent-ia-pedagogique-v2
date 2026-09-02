from __future__ import annotations

from decimal import Decimal

from calibration_tooling.contracts.errors import CalibrationErrorCode, fail_execution
from calibration_tooling.contracts.models import (
    CalibrationObservationResult,
    CallExecutionState,
    CallLedgerRecord,
    CallRef,
)


class InMemoryCallLedger:
    """Process-local ledger used by the offline runner; never serialized implicitly."""

    def __init__(self) -> None:
        self._records: dict[CallRef, CallLedgerRecord] = {}

    def reserve(self, call_ref: CallRef) -> None:
        if type(call_ref) is not CallRef:
            raise TypeError("call_ref must be a CallRef")
        current = self._records.get(call_ref)
        if current is not None:
            if current.state is CallExecutionState.STARTED:
                fail_execution(CalibrationErrorCode.LEDGER_AMBIGUOUS)
            fail_execution(CalibrationErrorCode.CALL_ALREADY_TERMINAL)
        self._records[call_ref] = CallLedgerRecord(
            call_ref=call_ref,
            state=CallExecutionState.STARTED,
        )

    def complete(
        self,
        result: CalibrationObservationResult,
        measured_cost_usd: Decimal,
    ) -> None:
        current = self._require_started(result.call_ref)
        self._records[current.call_ref] = CallLedgerRecord(
            call_ref=current.call_ref,
            state=CallExecutionState.COMPLETED,
            result=result,
            measured_cost_usd=measured_cost_usd,
        )

    def fail(
        self,
        call_ref: CallRef,
        error_code: CalibrationErrorCode,
        measured_cost_usd: Decimal | None = None,
    ) -> None:
        current = self._require_started(call_ref)
        self._records[current.call_ref] = CallLedgerRecord(
            call_ref=current.call_ref,
            state=CallExecutionState.FAILED,
            measured_cost_usd=measured_cost_usd,
            error_code=error_code,
        )

    def snapshot(self) -> tuple[CallLedgerRecord, ...]:
        return tuple(self._records.values())

    def _require_started(self, call_ref: CallRef) -> CallLedgerRecord:
        current = self._records.get(call_ref)
        if current is None or current.state is not CallExecutionState.STARTED:
            fail_execution(CalibrationErrorCode.CALL_ALREADY_TERMINAL)
        return current
