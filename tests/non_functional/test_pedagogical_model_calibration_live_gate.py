"""Explicit opt-in gate for the approved G2 live calibration."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from tests.calibration.pedagogical.call_plan import (
    LIVE_PROVIDER_CALL_COUNT,
    LIVE_PROVIDER_COST_USD,
    RAW_OUTPUT_DIRECTORY,
    call_matrix_sha256,
    estimate_call_plan_cost,
)
from tests.calibration.pedagogical.live_runner import (
    APPROVED_HARD_CEILING_USD,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    run_live_calibration,
)

LIVE_FLAG = "RUN_PEDAGOGICAL_LIVE_CALIBRATION"
LIVE_OUTPUT_PATH_ENV = "PEDAGOGICAL_CALIBRATION_OUTPUT_PATH"
APPROVED_CEILING_ENV = "PEDAGOGICAL_CALIBRATION_APPROVED_CEILING_USD"


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
    os.environ.get(LIVE_FLAG) != "1"
    or LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is not True,
    reason=(
        f"live gate requires {LIVE_FLAG}=1 and separate live owner authorization"
    ),
)
def test_g2_live_calibration_executes_or_resumes_approved_matrix() -> None:
    """Execute or safely resume the exact approved matrix when explicitly enabled."""

    output_path = os.environ.get(LIVE_OUTPUT_PATH_ENV)
    approved_ceiling = os.environ.get(APPROVED_CEILING_ENV)
    assert output_path == RAW_OUTPUT_DIRECTORY, (
        f"live gate requires {LIVE_OUTPUT_PATH_ENV}={RAW_OUTPUT_DIRECTORY}"
    )
    assert approved_ceiling, f"live gate requires {APPROVED_CEILING_ENV}"
    assert RAW_OUTPUT_DIRECTORY.startswith("artifacts/")
    assert call_matrix_sha256()
    estimated_maximum = estimate_call_plan_cost().estimated_maximum_with_margin_usd
    assert estimated_maximum == APPROVED_HARD_CEILING_USD == Decimal("3.251640")
    assert Decimal(approved_ceiling) == APPROVED_HARD_CEILING_USD
    aggregate = run_live_calibration(
        progress=lambda message: print(message, flush=True)
    )
    cost = aggregate["cost"]
    assert isinstance(cost, dict)
    assert Decimal(cost["budget_accounted_total_usd"]) <= Decimal(approved_ceiling)
    assert cost["ceiling_preserved"] is True
