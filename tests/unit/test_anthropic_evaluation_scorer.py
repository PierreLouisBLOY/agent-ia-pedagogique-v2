from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from evaluation_harness import (
    EvaluationObservationFieldCode,
    EvaluationScorerRef,
    NormalizedScore,
    ObservationField,
    ObservationObject,
    ObservationScalar,
    ObservationScalarKind,
    ObservationSequence,
    ScorerNotFoundError,
    ScoreStatus,
)
from tests.providers.anthropic import (
    AnthropicEvaluationScorer,
    AnthropicScorerError,
    AnthropicScoringResponse,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)
from tests.providers.anthropic.mapping import (
    build_anthropic_scoring_request,
    score_output_schema,
    serialize_observation,
)
from tests.support.anthropic_scoring_fakes import (
    RecordingAnthropicScoringTransport,
    RecordingAnthropicScoringTransportFactory,
)

_SCORER_REF = EvaluationScorerRef("pedagogical-quality-fixture-scorer")
_SECRET = "synthetic-anthropic-calibration-secret"


def _provider() -> ProviderProfileConfig:
    return ProviderProfileConfig(
        ProviderProfileId("anthropic-calibration-provider"),
        ProviderCode("anthropic"),
        ProviderCredentialRef("ANTHROPIC_CALIBRATION_API_KEY"),
    )


def _model() -> ModelProfileConfig:
    return ModelProfileConfig(
        ModelProfileId("anthropic.claude-sonnet-5.scorer"),
        ProviderProfileId("anthropic-calibration-provider"),
        ModelCode("claude-sonnet-5"),
        ModelContextLimits(1_000_000, 872_000, 128_000),
        ProviderInvocationLimits(1, 45_000, max_output_tokens=4_096),
        (ProviderWorkloadKind.EVALUATION_SCORING,),
        structured_output_required=True,
    )


def _criterion_observation() -> ObservationObject:
    def scalar(value: str) -> ObservationScalar:
        return ObservationScalar(ObservationScalarKind.STRING, value)

    return ObservationObject(
        (
            ObservationField(
                EvaluationObservationFieldCode("criterion-code"),
                scalar("pedagogical-adaptation"),
            ),
            ObservationField(
                EvaluationObservationFieldCode("candidate-projection"),
                scalar("A bounded synthetic lesson projection."),
            ),
            ObservationField(
                EvaluationObservationFieldCode("pedagogical-level"),
                scalar("CM1"),
            ),
            ObservationField(
                EvaluationObservationFieldCode("task-kind"),
                scalar("lesson-plan"),
            ),
            ObservationField(
                EvaluationObservationFieldCode("reference-constraints"),
                ObservationSequence((scalar("age-appropriate"), scalar("French"))),
            ),
        )
    )


def _scorer(
    output_text: str | None = None,
    *,
    error: AnthropicTransportError | None = None,
) -> tuple[
    AnthropicEvaluationScorer,
    RecordingAnthropicScoringTransport,
    RecordingAnthropicScoringTransportFactory,
]:
    transport = RecordingAnthropicScoringTransport(
        response=(
            AnthropicScoringResponse(output_text)
            if output_text is not None
            else None
        ),
        error=error,
    )
    factory = RecordingAnthropicScoringTransportFactory(transport)
    scorer = AnthropicEvaluationScorer(
        provider_profile=_provider(),
        model_profile=_model(),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"ANTHROPIC_CALIBRATION_API_KEY": _SECRET}
        ),
        transport_factory=factory,
    )
    return scorer, transport, factory


def _output(
    status: str,
    numerator: int | float | None,
    denominator: int | float | None,
) -> str:
    return json.dumps(
        {
            "status": status,
            "score_numerator": numerator,
            "score_denominator": denominator,
        }
    )


def test_observation_serialization_is_closed_deterministic_and_exact() -> None:
    scalar = ObservationScalar(ObservationScalarKind.DECIMAL, Decimal("0.1250"))
    sequence = ObservationSequence(
        (ObservationScalar(ObservationScalarKind.INTEGER, 2), scalar)
    )
    observation = _criterion_observation()

    assert serialize_observation(scalar) == {"kind": "DECIMAL", "value": "0.1250"}
    assert serialize_observation(sequence) == {
        "kind": "SEQUENCE",
        "items": [
            {"kind": "INTEGER", "value": 2},
            {"kind": "DECIMAL", "value": "0.1250"},
        ],
    }
    serialized = serialize_observation(observation)
    assert [item["code"] for item in serialized["fields"]] == [  # type: ignore[index]
        "criterion-code",
        "candidate-projection",
        "pedagogical-level",
        "task-kind",
        "reference-constraints",
    ]
    with pytest.raises(TypeError, match="unsupported"):
        serialize_observation({"arbitrary": "mapping"})  # type: ignore[arg-type]


def test_anthropic_request_is_model_exact_tool_free_by_contract_and_strict() -> None:
    request = build_anthropic_scoring_request(
        observations=(_criterion_observation(),),
        model="claude-sonnet-5",
        max_tokens=4_096,
    )
    assert request.model == "claude-sonnet-5"
    assert request.max_tokens == 4_096
    assert "criterion must be explicit" in request.system
    assert json.loads(request.input_json)["observations"][0]["kind"] == "OBJECT"
    assert request.output_schema == score_output_schema()
    assert request.output_schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    (
        (0, 1, NormalizedScore.zero()),
        (1, 1, NormalizedScore.whole()),
        (2, 4, NormalizedScore(1, 2)),
    ),
)
def test_known_scorer_maps_only_exact_rational_scores(
    numerator: int,
    denominator: int,
    expected: NormalizedScore,
) -> None:
    scorer, transport, factory = _scorer(_output("SCORED", numerator, denominator))
    result = scorer.score(_SCORER_REF, (_criterion_observation(),))
    assert result.status is ScoreStatus.SCORED
    assert result.score == expected
    assert transport.calls[0].model == "claude-sonnet-5"
    assert factory.build_calls == [("ProviderSecretValue([REDACTED])", 45.0)]
    assert _SECRET not in repr(scorer)


def test_unknown_scorer_is_not_routed_or_called() -> None:
    scorer, transport, _ = _scorer(_output("SCORED", 1, 1))
    with pytest.raises(ScorerNotFoundError):
        scorer.score(EvaluationScorerRef("unknown-scorer"), (_criterion_observation(),))
    assert transport.calls == []


def test_inconclusive_has_no_score() -> None:
    scorer, _, _ = _scorer(_output("INCONCLUSIVE", None, None))
    result = scorer.score(_SCORER_REF, (_criterion_observation(),))
    assert result.status is ScoreStatus.INCONCLUSIVE
    assert result.score is None


@pytest.mark.parametrize(
    "output_text",
    (
        "not-json",
        json.dumps({"status": "SCORED"}),
        _output("SCORED", 1, 0),
        _output("SCORED", 2, 1),
        _output("SCORED", 0.5, 1),
        _output("INCONCLUSIVE", 0, 1),
        _output("UNKNOWN", None, None),
    ),
)
def test_malformed_scores_raise_one_raw_free_private_error(output_text: str) -> None:
    scorer, _, _ = _scorer(output_text)
    with pytest.raises(AnthropicScorerError) as raised:
        scorer.score(_SCORER_REF, (_criterion_observation(),))
    assert str(raised.value) == "INVALID_RESPONSE"
    assert output_text not in str(raised.value)


@pytest.mark.parametrize("code", tuple(AnthropicTransportErrorCode))
def test_provider_failures_and_refusal_are_closed(
    code: AnthropicTransportErrorCode,
) -> None:
    scorer, _, _ = _scorer(error=AnthropicTransportError(code))
    with pytest.raises(AnthropicScorerError) as raised:
        scorer.score(_SCORER_REF, (_criterion_observation(),))
    assert str(raised.value) == "PROVIDER_UNAVAILABLE"
    assert _SECRET not in str(raised.value)
