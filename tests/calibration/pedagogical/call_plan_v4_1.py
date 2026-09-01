"""Corrective V4.1 calibration matrix with offline fail-closed contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.call_plan import (
    PEDAGOGICAL_CALIBRATION_CALL_MATRIX as V4_CALL_MATRIX,
)
from tests.calibration.pedagogical.call_plan import (
    V4_ANCHOR_BY_SCENARIO_TIER as V4_ANCHOR_BY_SCENARIO_TIER,
)
from tests.calibration.pedagogical.call_plan import (
    V4_TIER_BY_ANCHOR_ID as V4_TIER_BY_ANCHOR_ID,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationBudgetError,
    CalibrationBudgetErrorCode,
    CalibrationCallSpec,
    CalibrationProvider,
    CalibrationWorkload,
    CostEstimate,
)
from tests.calibration.pedagogical.call_plan import (
    CalibrationRole as CalibrationRole,
)
from tests.calibration.pedagogical.pricing import (
    MODEL_PRICE_QUOTES,
    PRICING_SNAPSHOT_ID,
    ModelPriceQuote,
    pricing_snapshot_sha256,
)
from tests.providers.anthropic.scorer import (
    _MAX_OUTPUT_TOKENS as ANTHROPIC_SCORER_REQUIRED_OUTPUT_TOKENS,
)

PEDAGOGICAL_CALIBRATION_PLAN_VERSION = "12.16-g2-v4.1-plan-v1"
RAW_OUTPUT_DIRECTORY = "artifacts/calibration/12.16-g2-v4-1/raw"
COST_SAFETY_MARGIN = Decimal("1.25")
OPENAI_REVIEW_MAX_OUTPUT_TOKENS = 2_048
LIVE_PROVIDER_CALL_COUNT = 0
LIVE_PROVIDER_COST_USD = Decimal("0")


class CalibrationMatrixContractErrorCode(StrEnum):
    ANTHROPIC_SCORER_OUTPUT_BUDGET_TOO_LOW = (
        "ANTHROPIC_SCORER_OUTPUT_BUDGET_TOO_LOW"
    )
    OPENAI_REVIEW_OUTPUT_BUDGET_TOO_LOW = "OPENAI_REVIEW_OUTPUT_BUDGET_TOO_LOW"
    HISTORICAL_PLAN_REFERENCE = "HISTORICAL_PLAN_REFERENCE"


class CalibrationMatrixContractError(RuntimeError):
    code: CalibrationMatrixContractErrorCode

    def __init__(self, code: CalibrationMatrixContractErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _corrective_call(call: CalibrationCallSpec) -> CalibrationCallSpec:
    max_output_tokens = call.max_output_tokens
    if call.provider is CalibrationProvider.ANTHROPIC:
        max_output_tokens = ANTHROPIC_SCORER_REQUIRED_OUTPUT_TOKENS
    elif call.workload is CalibrationWorkload.REVIEW:
        max_output_tokens = OPENAI_REVIEW_MAX_OUTPUT_TOKENS
    input_refs = tuple(
        ref.replace(
            "corpus:12.16-g2-v4-plan-v1:",
            f"corpus:{PEDAGOGICAL_CALIBRATION_PLAN_VERSION}:",
        )
        for ref in call.input_refs
    )
    return replace(
        call,
        max_output_tokens=max_output_tokens,
        input_refs=input_refs,
    )


PEDAGOGICAL_CALIBRATION_CALL_MATRIX = tuple(
    _corrective_call(call) for call in V4_CALL_MATRIX
)

OPENAI_CALL_COUNT = sum(
    call.provider is CalibrationProvider.OPENAI
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
)
ANTHROPIC_CALL_COUNT = sum(
    call.provider is CalibrationProvider.ANTHROPIC
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
)


def validate_call_matrix_contracts(
    calls: tuple[CalibrationCallSpec, ...] = PEDAGOGICAL_CALIBRATION_CALL_MATRIX,
) -> None:
    for call in calls:
        if (
            call.provider is CalibrationProvider.ANTHROPIC
            and call.max_output_tokens
            < ANTHROPIC_SCORER_REQUIRED_OUTPUT_TOKENS
        ):
            raise CalibrationMatrixContractError(
                CalibrationMatrixContractErrorCode.ANTHROPIC_SCORER_OUTPUT_BUDGET_TOO_LOW
            )
        if (
            call.workload is CalibrationWorkload.REVIEW
            and call.max_output_tokens < OPENAI_REVIEW_MAX_OUTPUT_TOKENS
        ):
            raise CalibrationMatrixContractError(
                CalibrationMatrixContractErrorCode.OPENAI_REVIEW_OUTPUT_BUDGET_TOO_LOW
            )
        if any("12.16-g2-v4-plan-v1" in ref for ref in call.input_refs):
            raise CalibrationMatrixContractError(
                CalibrationMatrixContractErrorCode.HISTORICAL_PLAN_REFERENCE
            )


def call_matrix_sha256() -> str:
    validate_call_matrix_contracts()
    payload = {
        "plan_version": PEDAGOGICAL_CALIBRATION_PLAN_VERSION,
        "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
        "corpus_sha256": v4_calibration_corpus_sha256(),
        "pricing_snapshot_id": PRICING_SNAPSHOT_ID,
        "pricing_snapshot_sha256": pricing_snapshot_sha256(),
        "calls": [
            {
                "call_id": call.call_id,
                "provider": call.provider.value,
                "model": call.model,
                "model_profile_id": call.model_profile_id,
                "role": call.role.value,
                "workload": call.workload.value,
                "scenario_code": call.scenario_code,
                "task_kind": call.task_kind,
                "repetition": call.repetition,
                "max_output_tokens": call.max_output_tokens,
                "input_utf8_upper_bound_bytes": call.input_utf8_upper_bound_bytes,
                "criterion_refs": call.criterion_refs,
                "input_refs": call.input_refs,
            }
            for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
        ],
    }
    canonical = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def estimate_call_plan_cost() -> CostEstimate:
    """Use the canonical pricing snapshot and conservative V4 estimation rules."""

    validate_call_matrix_contracts()
    quotes = {quote.model: quote for quote in MODEL_PRICE_QUOTES}
    base_input = 0
    base_output = 0
    max_input = 0
    max_output = 0
    base_cost = Decimal("0")
    max_cost = Decimal("0")
    for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX:
        quote = quotes[call.model]
        estimated_input = _ceil_div(call.input_utf8_upper_bound_bytes, 4)
        estimated_output = _ceil_div(call.max_output_tokens, 2)
        maximum_input = call.input_utf8_upper_bound_bytes
        base_input += estimated_input
        base_output += estimated_output
        max_input += maximum_input
        max_output += call.max_output_tokens
        base_cost += _token_cost(estimated_input, estimated_output, quote)
        max_cost += _token_cost(maximum_input, call.max_output_tokens, quote)
    return CostEstimate(
        call_count=len(PEDAGOGICAL_CALIBRATION_CALL_MATRIX),
        estimated_input_tokens=base_input,
        estimated_output_tokens=base_output,
        estimated_base_usd=_money(base_cost),
        maximum_input_tokens=max_input,
        maximum_output_tokens=max_output,
        estimated_maximum_before_margin_usd=_money(max_cost),
        estimated_maximum_with_margin_usd=_money(max_cost * COST_SAFETY_MARGIN),
    )


class CalibrationBudgetGuard:
    """V4.1 pre-call budget guard bound to the corrective matrix."""

    def authorize_next(
        self,
        *,
        call_id: str,
        provider: CalibrationProvider,
        model: str,
        model_profile_id: str,
        matrix_checksum: str,
        approved_ceiling_usd: Decimal | None,
        credential_available: bool,
        completed_call_ids: tuple[str, ...],
        actual_cost_usd: Decimal,
    ) -> CalibrationCallSpec:
        validate_call_matrix_contracts()
        if matrix_checksum != call_matrix_sha256():
            _budget_error(CalibrationBudgetErrorCode.PLAN_MISMATCH)
        if approved_ceiling_usd is None:
            _budget_error(CalibrationBudgetErrorCode.APPROVED_CEILING_MISSING)
        if approved_ceiling_usd < estimate_call_plan_cost().estimated_maximum_with_margin_usd:
            _budget_error(CalibrationBudgetErrorCode.APPROVED_CEILING_TOO_LOW)
        if actual_cost_usd > approved_ceiling_usd:
            _budget_error(CalibrationBudgetErrorCode.ACTUAL_USAGE_EXCEEDS_POLICY)
        if len(completed_call_ids) != len(set(completed_call_ids)):
            _budget_error(CalibrationBudgetErrorCode.CALL_COUNT_EXCEEDED)
        known_ids = {call.call_id for call in PEDAGOGICAL_CALIBRATION_CALL_MATRIX}
        if any(completed not in known_ids for completed in completed_call_ids):
            _budget_error(CalibrationBudgetErrorCode.PLAN_MISMATCH)
        try:
            call = next(
                item
                for item in PEDAGOGICAL_CALIBRATION_CALL_MATRIX
                if item.call_id == call_id
            )
        except StopIteration:
            _budget_error(CalibrationBudgetErrorCode.CALL_NOT_PLANNED)
        if call_id in completed_call_ids:
            _budget_error(CalibrationBudgetErrorCode.CALL_COUNT_EXCEEDED)
        if (
            call.provider is not provider
            or call.model != model
            or call.model_profile_id != model_profile_id
        ):
            _budget_error(CalibrationBudgetErrorCode.MODEL_MISMATCH)
        if not credential_available:
            _budget_error(CalibrationBudgetErrorCode.CREDENTIAL_UNAVAILABLE)
        return call


def _ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def _token_cost(
    input_tokens: int,
    output_tokens: int,
    quote: ModelPriceQuote,
) -> Decimal:
    million = Decimal(1_000_000)
    return (
        Decimal(input_tokens) * quote.input_usd_per_million_tokens
        + Decimal(output_tokens) * quote.output_usd_per_million_tokens
    ) / million


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


def _budget_error(code: CalibrationBudgetErrorCode) -> None:
    raise CalibrationBudgetError(code) from None
