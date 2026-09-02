from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest

from calibration_tooling.adapters.anthropic.contracts import (
    AnthropicEffort,
    AnthropicProjectionPayload,
    AnthropicThinkingMode,
    AnthropicTokenPricing,
    ResolvedAnthropicConfiguration,
)
from calibration_tooling.adapters.anthropic.mapping import (
    build_anthropic_scoring_request,
)
from calibration_tooling.contracts.errors import CalibrationContractError, CalibrationErrorCode
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationSpec,
    CallRef,
    CriterionRef,
    PairwiseObservationSpec,
    ProjectionRef,
)

PRICING = AnthropicTokenPricing(
    uncached_input_per_million_usd=Decimal("3"),
    cache_creation_input_per_million_usd=Decimal("3.75"),
    cache_read_input_per_million_usd=Decimal("0.30"),
    output_per_million_usd=Decimal("15"),
)
CONFIGURATION = ResolvedAnthropicConfiguration(
    model="claude-sonnet-5",
    max_tokens=2_048,
    timeout_milliseconds=30_000,
    pricing=PRICING,
    thinking_mode=AnthropicThinkingMode.ADAPTIVE,
    effort=AnthropicEffort.LOW,
)


def _absolute() -> AbsoluteObservationSpec:
    return AbsoluteObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.absolute"),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        Decimal("0.055600"),
    )


def _pairwise() -> PairwiseObservationSpec:
    return PairwiseObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.pairwise"),
        CriterionRef("criterion.coherence"),
        ProjectionRef("projection.strong"),
        ProjectionRef("projection.mixed"),
        Decimal("0.055600"),
    )


def test_resolved_configuration_is_explicit_adaptive_low_and_zero_retry() -> None:
    assert CONFIGURATION.model == "claude-sonnet-5"
    assert CONFIGURATION.max_tokens == 2_048
    assert CONFIGURATION.retry_count == 0
    assert CONFIGURATION.retain_raw_response is False
    with pytest.raises(ValueError):
        ResolvedAnthropicConfiguration(
            model="claude-sonnet-5",
            max_tokens=2_048,
            timeout_milliseconds=30_000,
            pricing=PRICING,
            effort=AnthropicEffort.LOW,
        )
    with pytest.raises(ValueError):
        ResolvedAnthropicConfiguration(
            model="claude-sonnet-5",
            max_tokens=2_048,
            timeout_milliseconds=30_000,
            pricing=PRICING,
            retry_count=1,
        )


def test_absolute_request_mapping_is_bounded_blind_and_schema_driven() -> None:
    spec = _absolute()
    payload = AnthropicProjectionPayload(
        spec.call_ref,
        json.dumps({"content": "synthetic strong projection", "tier": "STRONG"}),
    )
    request = build_anthropic_scoring_request(
        spec=spec,
        payload=payload,
        configuration=CONFIGURATION,
    )
    mapped = json.loads(request.messages[0].content)
    assert request.model == "claude-sonnet-5"
    assert request.max_tokens == 2_048
    assert request.thinking_mode is AnthropicThinkingMode.ADAPTIVE
    assert request.effort is AnthropicEffort.LOW
    assert mapped["calibration_call"] == {
        "call_ref": "call.absolute",
        "criterion_ref": "criterion.clarity",
        "kind": "ABSOLUTE",
        "projection_ref": "projection.strong",
        "schema_version": "calibration-tooling.v1",
    }
    assert "expected" not in request.messages[0].content.lower()
    assert request.output_schema["additionalProperties"] is False


def test_pairwise_mapping_keeps_candidate_order_and_hides_content_from_repr() -> None:
    spec = _pairwise()
    content = "synthetic pairwise pedagogical content"
    payload = AnthropicProjectionPayload(spec.call_ref, json.dumps({"content": content}))
    request = build_anthropic_scoring_request(
        spec=spec,
        payload=payload,
        configuration=CONFIGURATION,
    )
    mapped = json.loads(request.messages[0].content)
    properties = cast(dict[str, object], request.output_schema["properties"])
    decision = cast(dict[str, object], properties["decision"])
    assert mapped["calibration_call"]["candidate_a_ref"] == "projection.strong"
    assert mapped["calibration_call"]["candidate_b_ref"] == "projection.mixed"
    assert decision["enum"] == [
        "A_BETTER",
        "B_BETTER",
        "TIE",
    ]
    assert content not in repr(payload)
    assert content not in repr(request)
    assert content not in repr(request.messages[0])


def test_mapping_rejects_wrong_scope_and_non_object_payload() -> None:
    spec = _absolute()
    with pytest.raises(CalibrationContractError) as captured:
        build_anthropic_scoring_request(
            spec=spec,
            payload=AnthropicProjectionPayload(CallRef("call.other"), "{}"),
            configuration=CONFIGURATION,
        )
    assert captured.value.code is CalibrationErrorCode.TRANSFER_SCOPE_MISMATCH
    with pytest.raises(CalibrationContractError) as captured:
        build_anthropic_scoring_request(
            spec=spec,
            payload=AnthropicProjectionPayload(spec.call_ref, "[]"),
            configuration=CONFIGURATION,
        )
    assert captured.value.code is CalibrationErrorCode.INVALID_PAYLOAD
