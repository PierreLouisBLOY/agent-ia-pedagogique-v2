from __future__ import annotations

from backend.adapters.outbound.openai import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.infrastructure.composition.factories.openai import build_openai_review_adapter
from backend.infrastructure.config.effective_config.provider import (
    build_effective_provider_configuration,
)
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderConfiguration,
    ProviderConfigurationVersion,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderRouteConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from evaluation_harness import (
    EvaluationScorerRef,
    ObservationScalar,
    ObservationScalarKind,
    ScoreStatus,
)
from tests.providers.anthropic import (
    AnthropicScoringResponse,
    build_anthropic_evaluation_scorer,
)
from tests.support.anthropic_scoring_fakes import (
    RecordingAnthropicScoringTransport,
    RecordingAnthropicScoringTransportFactory,
)
from tests.support.openai_generation_fakes import (
    RecordingOpenAIResponsesTransport,
    RecordingOpenAITransportFactory,
)


def _configuration() -> ProviderConfiguration:
    openai_id = ProviderProfileId("openai-provider")
    anthropic_id = ProviderProfileId("anthropic-calibration-provider")
    sol_review = ModelProfileId("openai.gpt-5.6-sol.review")
    terra_review = ModelProfileId("openai.gpt-5.6-terra.review-fallback")
    claude_scorer = ModelProfileId("anthropic.claude-sonnet-5.scorer")
    openai_scorer = ModelProfileId("openai.gpt-5.6-sol.scorer-degraded")
    openai_context = ModelContextLimits(1_050_000, 900_000, 128_000)
    anthropic_context = ModelContextLimits(1_000_000, 872_000, 128_000)
    limits = ProviderInvocationLimits(1, 30_000, max_output_tokens=4_096)
    return ProviderConfiguration(
        ProviderConfigurationVersion(1, 0),
        (
            ProviderProfileConfig(
                openai_id,
                ProviderCode("openai"),
                ProviderCredentialRef("OPENAI_API_KEY"),
            ),
            ProviderProfileConfig(
                anthropic_id,
                ProviderCode("anthropic"),
                ProviderCredentialRef("ANTHROPIC_CALIBRATION_API_KEY"),
            ),
        ),
        (
            ModelProfileConfig(
                sol_review,
                openai_id,
                ModelCode("gpt-5.6-sol"),
                openai_context,
                limits,
                (ProviderWorkloadKind.REVIEW,),
                structured_output_required=True,
            ),
            ModelProfileConfig(
                terra_review,
                openai_id,
                ModelCode("gpt-5.6-terra"),
                openai_context,
                limits,
                (ProviderWorkloadKind.REVIEW,),
                structured_output_required=True,
            ),
            ModelProfileConfig(
                claude_scorer,
                anthropic_id,
                ModelCode("claude-sonnet-5"),
                anthropic_context,
                limits,
                (ProviderWorkloadKind.EVALUATION_SCORING,),
                structured_output_required=True,
            ),
            ModelProfileConfig(
                openai_scorer,
                openai_id,
                ModelCode("gpt-5.6-sol"),
                openai_context,
                limits,
                (ProviderWorkloadKind.EVALUATION_SCORING,),
                structured_output_required=True,
            ),
        ),
        (
            ProviderRouteConfig(
                ProviderWorkloadKind.REVIEW,
                sol_review,
                (terra_review,),
            ),
            ProviderRouteConfig(
                ProviderWorkloadKind.EVALUATION_SCORING,
                claude_scorer,
                (openai_scorer,),
            ),
        ),
    )


def test_review_factory_selects_sol_primary_without_touching_terra_fallback() -> None:
    transport = RecordingOpenAIResponsesTransport(
        response=OpenAIResponsesResponse(OpenAIResponseStatus.REFUSED)
    )
    adapter = build_openai_review_adapter(
        configuration=build_effective_provider_configuration(_configuration()),
        secret_resolver=EnvironmentProviderSecretResolver({}),
        transport_factory=RecordingOpenAITransportFactory(transport),
    )
    assert "openai.gpt-5.6-sol.review" in repr(adapter)
    assert "terra" not in repr(adapter)


def test_scorer_factory_selects_claude_primary_without_openai_fallback() -> None:
    transport = RecordingAnthropicScoringTransport(
        response=AnthropicScoringResponse(
            '{"status":"SCORED","score_numerator":1,"score_denominator":1}'
        )
    )
    scorer = build_anthropic_evaluation_scorer(
        configuration=build_effective_provider_configuration(_configuration()),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"ANTHROPIC_CALIBRATION_API_KEY": "synthetic"}
        ),
        transport_factory=RecordingAnthropicScoringTransportFactory(transport),
    )
    outcome = scorer.score(
        EvaluationScorerRef("pedagogical-quality-fixture-scorer"),
        (ObservationScalar(ObservationScalarKind.STRING, "criterion=synthetic"),),
    )
    assert outcome.status is ScoreStatus.SCORED
    assert transport.calls[0].model == "claude-sonnet-5"
    assert "openai" not in repr(scorer).casefold()
