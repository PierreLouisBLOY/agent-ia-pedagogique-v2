from __future__ import annotations

from enum import StrEnum
from typing import NoReturn


class CalibrationErrorCode(StrEnum):
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    INVALID_CONTRACT = "INVALID_CONTRACT"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RESPONSE_TRUNCATED = "RESPONSE_TRUNCATED"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    AUTHORIZATION_CONSUMED = "AUTHORIZATION_CONSUMED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    ALLOWLIST_MISMATCH = "ALLOWLIST_MISMATCH"
    TRANSFER_SCOPE_MISMATCH = "TRANSFER_SCOPE_MISMATCH"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CALL_ALREADY_TERMINAL = "CALL_ALREADY_TERMINAL"
    LEDGER_AMBIGUOUS = "LEDGER_AMBIGUOUS"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RESULT_MISMATCH = "RESULT_MISMATCH"


class CalibrationError(Exception):
    """Safe public failure carrying a closed code and no raw provider content."""

    code: CalibrationErrorCode

    def __init__(self, code: CalibrationErrorCode) -> None:
        if not isinstance(code, CalibrationErrorCode):
            raise TypeError("code must be a CalibrationErrorCode")
        self.code = code
        super().__init__(code.value)


class CalibrationContractError(CalibrationError, ValueError):
    """Terminal rejection of an input or provider output contract."""


class CalibrationExecutionError(CalibrationError, RuntimeError):
    """Fail-closed execution failure whose provider state may be ambiguous."""


def fail_contract(code: CalibrationErrorCode) -> NoReturn:
    raise CalibrationContractError(code) from None


def fail_execution(code: CalibrationErrorCode) -> NoReturn:
    raise CalibrationExecutionError(code) from None
