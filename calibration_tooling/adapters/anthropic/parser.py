"""Fail-closed normalization of bounded Anthropic structured responses."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import Final

from calibration_tooling.adapters.anthropic.contracts import (
    AnthropicMessageResponse,
    AnthropicStopReason,
    AnthropicTokenPricing,
    AnthropicUsage,
)
from calibration_tooling.contracts.errors import CalibrationErrorCode, fail_contract
from calibration_tooling.contracts.models import (
    MAX_COST_USD,
    CalibrationObservationSpec,
    RawProviderResponse,
)

_ONE_MILLION: Final = Decimal("1000000")
_MICRO_USD: Final = Decimal("0.000001")


def parse_anthropic_response(
    *,
    spec: CalibrationObservationSpec,
    response: AnthropicMessageResponse,
    pricing: AnthropicTokenPricing,
) -> RawProviderResponse:
    if type(response) is not AnthropicMessageResponse:
        fail_contract(CalibrationErrorCode.RESPONSE_INVALID)
    if type(pricing) is not AnthropicTokenPricing:
        raise TypeError("pricing must be AnthropicTokenPricing")
    if response.stop_reason is AnthropicStopReason.MAX_TOKENS:
        output_text = response.text_blocks[0] if len(response.text_blocks) == 1 else ""
        return RawProviderResponse(
            call_ref=spec.call_ref,
            output_text=output_text,
            measured_cost_usd=measure_anthropic_cost(response.usage, pricing),
            complete=False,
        )
    if response.stop_reason not in {
        AnthropicStopReason.END_TURN,
        AnthropicStopReason.STOP_SEQUENCE,
    }:
        fail_contract(CalibrationErrorCode.RESPONSE_INVALID)
    if len(response.text_blocks) != 1 or not response.text_blocks[0].strip():
        fail_contract(CalibrationErrorCode.RESPONSE_INVALID)
    return RawProviderResponse(
        call_ref=spec.call_ref,
        output_text=response.text_blocks[0],
        measured_cost_usd=measure_anthropic_cost(response.usage, pricing),
        complete=True,
    )


def measure_anthropic_cost(
    usage: AnthropicUsage,
    pricing: AnthropicTokenPricing,
) -> Decimal:
    if type(usage) is not AnthropicUsage:
        raise TypeError("usage must be AnthropicUsage")
    if type(pricing) is not AnthropicTokenPricing:
        raise TypeError("pricing must be AnthropicTokenPricing")
    raw_cost = (
        Decimal(usage.uncached_input_tokens) * pricing.uncached_input_per_million_usd
        + Decimal(usage.cache_creation_input_tokens)
        * pricing.cache_creation_input_per_million_usd
        + Decimal(usage.cache_read_input_tokens)
        * pricing.cache_read_input_per_million_usd
        + Decimal(usage.output_tokens) * pricing.output_per_million_usd
    ) / _ONE_MILLION
    measured_cost = raw_cost.quantize(_MICRO_USD, rounding=ROUND_CEILING)
    if measured_cost > MAX_COST_USD:
        fail_contract(CalibrationErrorCode.RESPONSE_INVALID)
    return measured_cost
