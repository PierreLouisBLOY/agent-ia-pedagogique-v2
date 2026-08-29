"""G2 live-calibration scaffold. G1 must never invoke either provider."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Protocol

import pytest

from tests.calibration.pedagogical.call_plan import (
    LIVE_PROVIDER_CALL_COUNT,
    LIVE_PROVIDER_COST_USD,
    RAW_OUTPUT_DIRECTORY,
    CalibrationBudgetError,
    CalibrationBudgetErrorCode,
    CalibrationBudgetGuard,
    CalibrationProvider,
    call_matrix_sha256,
    estimate_call_plan_cost,
)

LIVE_FLAG = "RUN_PEDAGOGICAL_LIVE_CALIBRATION"
LIVE_OUTPUT_PATH_ENV = "PEDAGOGICAL_CALIBRATION_OUTPUT_PATH"
APPROVED_CEILING_ENV = "PEDAGOGICAL_CALIBRATION_APPROVED_CEILING_USD"


class InjectableCalibrationTransport(Protocol):
    def invoke(self, *, call_id: str) -> object: ...


class _DenyingTransport:
    calls = 0

    def invoke(self, *, call_id: str) -> object:
        self.calls += 1
        raise AssertionError(f"G1 transport must not be invoked: {call_id}")


def test_g1_provider_call_guard_is_zero_without_live_execution() -> None:
    openai_transport = _DenyingTransport()
    anthropic_transport = _DenyingTransport()
    assert LIVE_PROVIDER_CALL_COUNT == 0
    assert LIVE_PROVIDER_COST_USD == Decimal("0")
    assert openai_transport.calls == 0
    assert anthropic_transport.calls == 0


@pytest.mark.skipif(
    os.environ.get(LIVE_FLAG) != "1",
    reason=f"explicit live gate requires {LIVE_FLAG}=1",
)
def test_g2_live_calibration_scaffold_remains_closed_during_g1() -> None:
    """Even with the flag, G1 stops before transport pending explicit G2 approval."""

    openai_transport: InjectableCalibrationTransport = _DenyingTransport()
    anthropic_transport: InjectableCalibrationTransport = _DenyingTransport()
    output_path = os.environ.get(LIVE_OUTPUT_PATH_ENV)
    approved_ceiling = os.environ.get(APPROVED_CEILING_ENV)
    assert output_path == RAW_OUTPUT_DIRECTORY, (
        f"live gate requires {LIVE_OUTPUT_PATH_ENV}={RAW_OUTPUT_DIRECTORY}"
    )
    assert approved_ceiling, f"live gate requires {APPROVED_CEILING_ENV}"
    assert RAW_OUTPUT_DIRECTORY.startswith("artifacts/")
    assert call_matrix_sha256()
    estimated_maximum = estimate_call_plan_cost().estimated_maximum_with_margin_usd
    assert estimated_maximum == Decimal("4.096440")
    assert Decimal(approved_ceiling) >= estimated_maximum
    with pytest.raises(CalibrationBudgetError) as raised:
        CalibrationBudgetGuard().authorize_next(
            call_id="cal.generation.course.primary.r1",
            provider=CalibrationProvider.OPENAI,
            model="gpt-5.6-terra",
            model_profile_id="openai.gpt-5.6-terra.generation",
            matrix_checksum=call_matrix_sha256(),
            approved_ceiling_usd=Decimal(approved_ceiling),
            credential_available=False,
            completed_call_ids=(),
            actual_cost_usd=Decimal("0"),
        )
    assert raised.value.code is CalibrationBudgetErrorCode.CREDENTIAL_UNAVAILABLE
    assert openai_transport.calls == 0
    assert anthropic_transport.calls == 0
