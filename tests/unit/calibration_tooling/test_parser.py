from __future__ import annotations

import json
from decimal import Decimal

import pytest

from calibration_tooling.contracts.errors import (
    CalibrationContractError,
    CalibrationErrorCode,
)
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    MAX_PROVIDER_OUTPUT_BYTES,
    AbsoluteObservationResult,
    AbsoluteObservationSpec,
    AbsoluteScoreStatus,
    CallRef,
    CriterionRef,
    ObservationKind,
    PairwiseDecision,
    PairwiseObservationResult,
    PairwiseObservationSpec,
    ProjectionRef,
    RawProviderResponse,
)
from calibration_tooling.contracts.parser import (
    ACTIVE_OUTPUT_SCHEMA_VERSION,
    CanonicalCalibrationOutputParser,
    active_output_schema,
)

PARSER = CanonicalCalibrationOutputParser()


def _absolute() -> AbsoluteObservationSpec:
    return AbsoluteObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.absolute"),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        Decimal("0.010000"),
    )


def _pairwise() -> PairwiseObservationSpec:
    return PairwiseObservationSpec(
        CALIBRATION_SCHEMA_V1,
        CallRef("call.pairwise"),
        CriterionRef("criterion.clarity"),
        ProjectionRef("projection.strong"),
        ProjectionRef("projection.mixed"),
        Decimal("0.020000"),
    )


def _response(call_ref: CallRef, payload: dict[str, object]) -> RawProviderResponse:
    return RawProviderResponse(
        call_ref=call_ref,
        output_text=json.dumps(payload),
        measured_cost_usd=Decimal("0.001000"),
        complete=True,
    )


def test_parser_accepts_only_the_active_absolute_schema() -> None:
    spec = _absolute()
    response = _response(
        spec.call_ref,
        {
            "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
            "call_ref": spec.call_ref.value,
            "kind": "ABSOLUTE",
            "status": "SCORED",
            "score_level": 4,
        },
    )
    assert PARSER.parse(spec, response) == AbsoluteObservationResult(
        spec.call_ref,
        AbsoluteScoreStatus.SCORED,
        4,
    )


def test_active_schema_is_exact_bounded_and_provider_neutral() -> None:
    absolute = active_output_schema(ObservationKind.ABSOLUTE)
    pairwise = active_output_schema(ObservationKind.PAIRWISE)
    assert absolute["additionalProperties"] is False
    assert pairwise["additionalProperties"] is False
    assert absolute["required"] == [
        "call_ref",
        "kind",
        "schema_version",
        "score_level",
        "status",
    ]
    assert pairwise["required"] == [
        "call_ref",
        "decision",
        "kind",
        "schema_version",
    ]


def test_parser_accepts_inconclusive_only_without_a_score() -> None:
    spec = _absolute()
    payload: dict[str, object] = {
        "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
        "call_ref": spec.call_ref.value,
        "kind": "ABSOLUTE",
        "status": "INCONCLUSIVE",
        "score_level": None,
    }
    assert PARSER.parse(spec, _response(spec.call_ref, payload)) == (
        AbsoluteObservationResult(
            spec.call_ref,
            AbsoluteScoreStatus.INCONCLUSIVE,
            None,
        )
    )
    payload["score_level"] = 1
    with pytest.raises(CalibrationContractError) as captured:
        PARSER.parse(spec, _response(spec.call_ref, payload))
    assert captured.value.code is CalibrationErrorCode.INVALID_PAYLOAD


def test_parser_dispatches_pairwise_without_union_reassignment() -> None:
    spec = _pairwise()
    response = _response(
        spec.call_ref,
        {
            "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
            "call_ref": spec.call_ref.value,
            "kind": "PAIRWISE",
            "decision": "A_BETTER",
        },
    )
    assert PARSER.parse(spec, response) == PairwiseObservationResult(
        spec.call_ref,
        PairwiseDecision.A_BETTER,
    )


@pytest.mark.parametrize(
    ("output_text", "code"),
    (
        ("not-json-secret-material", CalibrationErrorCode.INVALID_PAYLOAD),
        ("", CalibrationErrorCode.RESPONSE_TOO_LARGE),
        ("x" * (MAX_PROVIDER_OUTPUT_BYTES + 1), CalibrationErrorCode.RESPONSE_TOO_LARGE),
    ),
)
def test_parser_failures_are_closed_and_never_echo_raw_output(
    output_text: str,
    code: CalibrationErrorCode,
) -> None:
    spec = _absolute()
    response = RawProviderResponse(
        spec.call_ref,
        output_text,
        Decimal("0.001000"),
        True,
    )
    with pytest.raises(CalibrationContractError) as captured:
        PARSER.parse(spec, response)
    assert captured.value.code is code
    assert str(captured.value) == code.value
    if output_text:
        assert output_text not in repr(captured.value)


def test_parser_rejects_truncation_extra_fields_and_identity_mismatch() -> None:
    spec = _absolute()
    valid: dict[str, object] = {
        "schema_version": ACTIVE_OUTPUT_SCHEMA_VERSION,
        "call_ref": spec.call_ref.value,
        "kind": "ABSOLUTE",
        "status": "SCORED",
        "score_level": 4,
    }
    truncated = RawProviderResponse(
        spec.call_ref,
        json.dumps(valid),
        Decimal("0.001000"),
        False,
    )
    with pytest.raises(CalibrationContractError) as captured:
        PARSER.parse(spec, truncated)
    assert captured.value.code is CalibrationErrorCode.RESPONSE_TRUNCATED

    valid["unexpected"] = "field"
    with pytest.raises(CalibrationContractError) as captured:
        PARSER.parse(spec, _response(spec.call_ref, valid))
    assert captured.value.code is CalibrationErrorCode.INVALID_PAYLOAD

    valid.pop("unexpected")
    valid["call_ref"] = "call.other"
    with pytest.raises(CalibrationContractError) as captured:
        PARSER.parse(spec, _response(spec.call_ref, valid))
    assert captured.value.code is CalibrationErrorCode.IDENTITY_MISMATCH
