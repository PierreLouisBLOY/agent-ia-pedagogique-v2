from __future__ import annotations

import json
from decimal import Decimal

import pytest

from calibration_tooling.adapters.anthropic.contracts import (
    AnthropicEffort,
    AnthropicMessageResponse,
    AnthropicProjectionPayload,
    AnthropicScoringRequest,
    AnthropicStopReason,
    AnthropicThinkingMode,
    AnthropicTokenPricing,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
    AnthropicUsage,
    ResolvedAnthropicConfiguration,
)
from calibration_tooling.adapters.anthropic.scorer import AnthropicCalibrationScorer
from calibration_tooling.application.service import CalibrationService
from calibration_tooling.contracts.errors import (
    CalibrationContractError,
    CalibrationErrorCode,
    CalibrationExecutionError,
)
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    CallRef,
    CriterionRef,
    PairwiseDecision,
    PairwiseObservationResult,
    PairwiseObservationSpec,
    ProjectionRef,
)
from calibration_tooling.contracts.parser import CanonicalCalibrationOutputParser

CONFIGURATION = ResolvedAnthropicConfiguration(
    model="claude-sonnet-5",
    max_tokens=2_048,
    timeout_milliseconds=30_000,
    pricing=AnthropicTokenPricing(
        Decimal("3"), Decimal("3.75"), Decimal("0.30"), Decimal("15")
    ),
    thinking_mode=AnthropicThinkingMode.ADAPTIVE,
    effort=AnthropicEffort.LOW,
)
USAGE = AnthropicUsage(100, 0, 0, 20)


class DictProjectionSource:
    def __init__(self, payloads: dict[CallRef, AnthropicProjectionPayload]) -> None:
        self.payloads = payloads
        self.loads: list[CallRef] = []

    def load(self, call_ref: CallRef) -> AnthropicProjectionPayload:
        self.loads.append(call_ref)
        return self.payloads[call_ref]


class FakeScoringTransport:
    def __init__(self, responses: list[AnthropicMessageResponse]) -> None:
        self.responses = responses
        self.requests: list[AnthropicScoringRequest] = []

    def create(self, *, request: AnthropicScoringRequest) -> AnthropicMessageResponse:
        self.requests.append(request)
        return self.responses[len(self.requests) - 1]


class FailingScoringTransport:
    def __init__(self, error: AnthropicTransportError) -> None:
        self.error = error
        self.call_count = 0

    def create(self, *, request: AnthropicScoringRequest) -> AnthropicMessageResponse:
        self.call_count += 1
        raise self.error


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


def _response(payload: dict[str, object]) -> AnthropicMessageResponse:
    return AnthropicMessageResponse(
        (json.dumps(payload),),
        AnthropicStopReason.END_TURN,
        USAGE,
    )


def test_active_adapter_implements_b02_port_for_absolute_and_pairwise() -> None:
    absolute = _absolute()
    pairwise = _pairwise()
    source = DictProjectionSource(
        {
            absolute.call_ref: AnthropicProjectionPayload(
                absolute.call_ref, '{"content":"strong"}'
            ),
            pairwise.call_ref: AnthropicProjectionPayload(
                pairwise.call_ref, '{"candidate_a":"strong","candidate_b":"mixed"}'
            ),
        }
    )
    transport = FakeScoringTransport(
        [
            _response(
                {
                    "schema_version": "calibration-output.v1",
                    "call_ref": absolute.call_ref.value,
                    "kind": "ABSOLUTE",
                    "status": "SCORED",
                    "score_level": 4,
                }
            ),
            _response(
                {
                    "schema_version": "calibration-output.v1",
                    "call_ref": pairwise.call_ref.value,
                    "kind": "PAIRWISE",
                    "decision": "A_BETTER",
                }
            ),
        ]
    )
    service = CalibrationService(
        AnthropicCalibrationScorer(
            configuration=CONFIGURATION,
            projection_source=source,
            transport=transport,
        ),
        CanonicalCalibrationOutputParser(),
    )
    absolute_call = service.evaluate(absolute)
    pairwise_call = service.evaluate(pairwise)
    assert absolute_call.result == AbsoluteObservationResult(
        absolute.call_ref, AbsoluteScoreStatus.SCORED, 4
    )
    assert pairwise_call.result == PairwiseObservationResult(
        pairwise.call_ref, PairwiseDecision.A_BETTER
    )
    assert source.loads == [absolute.call_ref, pairwise.call_ref]
    assert len(transport.requests) == 2


def test_malformed_provider_payload_is_rejected_by_the_single_active_parser() -> None:
    spec = _absolute()
    source = DictProjectionSource(
        {spec.call_ref: AnthropicProjectionPayload(spec.call_ref, "{}")}
    )
    service = CalibrationService(
        AnthropicCalibrationScorer(
            configuration=CONFIGURATION,
            projection_source=source,
            transport=FakeScoringTransport([_response({"unexpected": True})]),
        ),
        CanonicalCalibrationOutputParser(),
    )
    with pytest.raises(CalibrationContractError) as captured:
        service.evaluate(spec)
    assert captured.value.code is CalibrationErrorCode.INVALID_PAYLOAD


def test_missing_projection_fails_closed_before_provider_transport() -> None:
    spec = _absolute()
    transport = FakeScoringTransport([])
    scorer = AnthropicCalibrationScorer(
        configuration=CONFIGURATION,
        projection_source=DictProjectionSource({}),
        transport=transport,
    )
    with pytest.raises(CalibrationContractError) as captured:
        scorer.invoke(spec)
    assert captured.value.code is CalibrationErrorCode.TRANSFER_SCOPE_MISMATCH
    assert transport.requests == []


def test_transport_failures_are_narrowed_without_retry() -> None:
    spec = _absolute()
    source = DictProjectionSource(
        {spec.call_ref: AnthropicProjectionPayload(spec.call_ref, "{}")}
    )
    cases = (
        (
            AnthropicTransportError(AnthropicTransportErrorCode.CREDENTIAL_UNAVAILABLE),
            CalibrationErrorCode.CREDENTIAL_UNAVAILABLE,
        ),
        (
            AnthropicTransportError(AnthropicTransportErrorCode.TIMEOUT),
            CalibrationErrorCode.PROVIDER_UNAVAILABLE,
        ),
        (
            AnthropicTransportError(
                AnthropicTransportErrorCode.HTTP_ERROR,
                http_status=503,
                response_received=True,
            ),
            CalibrationErrorCode.PROVIDER_UNAVAILABLE,
        ),
    )
    for error, expected in cases:
        transport = FailingScoringTransport(error)
        scorer = AnthropicCalibrationScorer(
            configuration=CONFIGURATION,
            projection_source=source,
            transport=transport,
        )
        with pytest.raises(CalibrationExecutionError) as captured:
            scorer.invoke(spec)
        assert captured.value.code is expected
        assert transport.call_count == 1


def test_invalid_transport_response_is_a_closed_contract_failure() -> None:
    spec = _absolute()
    source = DictProjectionSource(
        {spec.call_ref: AnthropicProjectionPayload(spec.call_ref, "{}")}
    )
    transport = FailingScoringTransport(
        AnthropicTransportError(
            AnthropicTransportErrorCode.RESPONSE_INVALID,
            response_received=True,
        )
    )
    scorer = AnthropicCalibrationScorer(
        configuration=CONFIGURATION,
        projection_source=source,
        transport=transport,
    )
    with pytest.raises(CalibrationContractError) as captured:
        scorer.invoke(spec)
    assert captured.value.code is CalibrationErrorCode.RESPONSE_INVALID
    assert transport.call_count == 1
