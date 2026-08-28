from __future__ import annotations

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
    EVALUATION_SCHEMA_V1_0,
    EvaluationCriterionRef,
    EvaluationObservationRef,
    EvaluationScorerRef,
    EvaluationScoringCriterionSpec,
    NormalizedScore,
    ObservationScalar,
    ObservationScalarKind,
    ScoreEvaluator,
    ScoreReasonCode,
    ScoreStatus,
)
from tests.providers.anthropic import (
    AnthropicEvaluationScorer,
    AnthropicScoringResponse,
)
from tests.support.anthropic_scoring_fakes import (
    RecordingAnthropicScoringTransport,
    RecordingAnthropicScoringTransportFactory,
)
from tests.support.evaluation_assertion_fakes import RecordingObservationSource


def _evaluate(output_text: str):  # type: ignore[no-untyped-def]
    observation_ref = EvaluationObservationRef("quality-observation")
    scorer_ref = EvaluationScorerRef("pedagogical-quality-fixture-scorer")
    provider_id = ProviderProfileId("anthropic-calibration-provider")
    scorer = AnthropicEvaluationScorer(
        provider_profile=ProviderProfileConfig(
            provider_id,
            ProviderCode("anthropic"),
            ProviderCredentialRef("ANTHROPIC_CALIBRATION_API_KEY"),
        ),
        model_profile=ModelProfileConfig(
            ModelProfileId("anthropic.claude-sonnet-5.scorer"),
            provider_id,
            ModelCode("claude-sonnet-5"),
            ModelContextLimits(1_000_000, 872_000, 128_000),
            ProviderInvocationLimits(1, 30_000, max_output_tokens=2_048),
            (ProviderWorkloadKind.EVALUATION_SCORING,),
            structured_output_required=True,
        ),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"ANTHROPIC_CALIBRATION_API_KEY": "synthetic"}
        ),
        transport_factory=RecordingAnthropicScoringTransportFactory(
            RecordingAnthropicScoringTransport(
                response=AnthropicScoringResponse(output_text)
            )
        ),
    )
    source = RecordingObservationSource(
        (
            observation_ref,
            ObservationScalar(
                ObservationScalarKind.STRING,
                "criterion=pedagogical-adaptation; candidate=synthetic",
            ),
        )
    )
    spec = EvaluationScoringCriterionSpec(
        EVALUATION_SCHEMA_V1_0,
        EvaluationCriterionRef("pedagogical-adaptation"),
        scorer_ref,
        (observation_ref,),
        NormalizedScore.whole(),
    )
    return ScoreEvaluator(source, scorer).evaluate(spec)


def test_real_score_evaluator_maps_scored_inconclusive_and_private_failure() -> None:
    scored = _evaluate(
        '{"status":"SCORED","score_numerator":3,"score_denominator":4}'
    )
    assert scored.status is ScoreStatus.SCORED
    assert scored.score == NormalizedScore(3, 4)

    inconclusive = _evaluate(
        '{"status":"INCONCLUSIVE","score_numerator":null,"score_denominator":null}'
    )
    assert inconclusive.status is ScoreStatus.INCONCLUSIVE
    assert inconclusive.reason_code is ScoreReasonCode.SCORER_INCONCLUSIVE

    malformed = _evaluate("not-json")
    assert malformed.status is ScoreStatus.ERROR
    assert malformed.reason_code is ScoreReasonCode.SCORER_EVALUATION_ERROR
