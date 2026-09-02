from __future__ import annotations

from decimal import Decimal

import pytest

from calibration_tooling.contracts.errors import (
    CalibrationErrorCode,
    CalibrationExecutionError,
)
from calibration_tooling.contracts.models import (
    AbsoluteObservationResult,
    AbsoluteScoreStatus,
    CallExecutionState,
    CallRef,
)
from calibration_tooling.runtime.ledger import InMemoryCallLedger


def test_started_without_terminal_result_is_ambiguous_and_blocks_recall() -> None:
    ledger = InMemoryCallLedger()
    call_ref = CallRef("call.ambiguous")
    ledger.reserve(call_ref)
    assert ledger.snapshot()[0].state is CallExecutionState.STARTED
    with pytest.raises(CalibrationExecutionError) as captured:
        ledger.reserve(call_ref)
    assert captured.value.code is CalibrationErrorCode.LEDGER_AMBIGUOUS


def test_completed_call_is_terminal_and_cannot_be_recalled() -> None:
    ledger = InMemoryCallLedger()
    call_ref = CallRef("call.completed")
    result = AbsoluteObservationResult(call_ref, AbsoluteScoreStatus.SCORED, 4)
    ledger.reserve(call_ref)
    ledger.complete(result, Decimal("0.001000"))
    record = ledger.snapshot()[0]
    assert record.state is CallExecutionState.COMPLETED
    assert record.result == result
    with pytest.raises(CalibrationExecutionError) as captured:
        ledger.reserve(call_ref)
    assert captured.value.code is CalibrationErrorCode.CALL_ALREADY_TERMINAL


def test_contract_failure_is_terminal_without_raw_payload() -> None:
    ledger = InMemoryCallLedger()
    call_ref = CallRef("call.failed")
    ledger.reserve(call_ref)
    ledger.fail(call_ref, CalibrationErrorCode.INVALID_PAYLOAD)
    record = ledger.snapshot()[0]
    assert record.state is CallExecutionState.FAILED
    assert record.error_code is CalibrationErrorCode.INVALID_PAYLOAD
    assert record.result is None
