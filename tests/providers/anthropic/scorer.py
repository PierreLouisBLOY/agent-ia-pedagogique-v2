"""Anthropic implementation of the existing offline EvaluationScorerPort."""

from __future__ import annotations

import json
from enum import StrEnum

from backend.infrastructure.config.effective_config.provider import (
    EffectiveProviderConfiguration,
)
from backend.infrastructure.config.schemas.provider import (
    ModelProfileConfig,
    ProviderConfigurationError,
    ProviderConfigurationErrorCode,
    ProviderProfileConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderSecretError,
    ProviderSecretResolver,
)
from evaluation_harness.contracts.identity import EvaluationScorerRef
from evaluation_harness.contracts.observation import EvaluationObservationValue
from evaluation_harness.contracts.scoring import (
    NormalizedScore,
    ScorerOutcome,
    ScoreStatus,
)
from evaluation_harness.scoring.ports import ScorerNotFoundError
from tests.providers.anthropic.contracts import (
    AnthropicEffort,
    AnthropicProviderErrorType,
    AnthropicScoringTransportFactory,
    AnthropicStopReason,
    AnthropicThinkingMode,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)
from tests.providers.anthropic.mapping import build_anthropic_scoring_request
from tests.providers.anthropic.transport import AnthropicSDKScoringTransportFactory

CANONICAL_SCORER_REF = "pedagogical-quality-fixture-scorer"
_MODEL_CODE = "claude-sonnet-5"
_THINKING_MODE = AnthropicThinkingMode.ADAPTIVE
_EFFORT = AnthropicEffort.LOW
_MAX_OUTPUT_TOKENS = 2_048


class AnthropicScorerErrorCode(StrEnum):
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class AnthropicScorerError(RuntimeError):
    """Raw-free private calibration failure contained by ScoreEvaluator."""

    code: AnthropicScorerErrorCode
    transport_code: AnthropicTransportErrorCode | None
    http_status: int | None
    provider_error_type: AnthropicProviderErrorType | None
    response_received: bool
    stop_reason: AnthropicStopReason | None
    text_block_count: int | None
    thinking_block_count: int | None
    thinking_tokens: int | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    def __init__(
        self,
        code: AnthropicScorerErrorCode,
        *,
        transport_error: AnthropicTransportError | None = None,
    ) -> None:
        self.code = code
        self.transport_code = transport_error.code if transport_error is not None else None
        self.http_status = transport_error.http_status if transport_error is not None else None
        self.provider_error_type = (
            transport_error.provider_error_type if transport_error is not None else None
        )
        self.response_received = (
            transport_error.response_received if transport_error is not None else False
        )
        self.stop_reason = transport_error.stop_reason if transport_error is not None else None
        self.text_block_count = (
            transport_error.text_block_count if transport_error is not None else None
        )
        self.thinking_block_count = (
            transport_error.thinking_block_count if transport_error is not None else None
        )
        self.thinking_tokens = (
            transport_error.thinking_tokens if transport_error is not None else None
        )
        self.input_tokens = transport_error.input_tokens if transport_error is not None else None
        self.cached_input_tokens = (
            transport_error.cached_input_tokens if transport_error is not None else None
        )
        self.output_tokens = transport_error.output_tokens if transport_error is not None else None
        self.total_tokens = transport_error.total_tokens if transport_error is not None else None
        super().__init__(code.value)


class AnthropicEvaluationScorer:
    """One exact-rational judge call with no runtime or gate authority."""

    __slots__ = (
        "_model_profile",
        "_provider_profile",
        "_secret_resolver",
        "_transport_factory",
    )

    def __init__(
        self,
        *,
        provider_profile: ProviderProfileConfig,
        model_profile: ModelProfileConfig,
        secret_resolver: ProviderSecretResolver,
        transport_factory: AnthropicScoringTransportFactory,
    ) -> None:
        _validate_configuration(provider_profile, model_profile)
        if not isinstance(secret_resolver, ProviderSecretResolver):
            raise TypeError("secret_resolver must satisfy ProviderSecretResolver")
        self._provider_profile = provider_profile
        self._model_profile = model_profile
        self._secret_resolver = secret_resolver
        self._transport_factory = transport_factory

    def __repr__(self) -> str:
        return (
            "AnthropicEvaluationScorer("
            f"provider_profile_id={self._provider_profile.profile_id.value!r}, "
            f"model_profile_id={self._model_profile.model_profile_id.value!r})"
        )

    def score(
        self,
        scorer_ref: EvaluationScorerRef,
        observations: tuple[EvaluationObservationValue, ...],
    ) -> ScorerOutcome:
        if type(scorer_ref) is not EvaluationScorerRef:
            raise TypeError("scorer_ref must be an EvaluationScorerRef")
        if scorer_ref.value != CANONICAL_SCORER_REF:
            raise ScorerNotFoundError(scorer_ref.value)
        request = build_anthropic_scoring_request(
            observations=observations,
            model=self._model_profile.model_code.value,
            max_tokens=_MAX_OUTPUT_TOKENS,
            thinking_mode=_THINKING_MODE,
            effort=_EFFORT,
        )
        try:
            secret = self._secret_resolver.resolve(self._provider_profile.credential_ref)
            transport = self._transport_factory.build(
                secret=secret,
                timeout_seconds=(
                    self._model_profile.invocation_limits.call_timeout_milliseconds / 1_000.0
                ),
            )
            response = transport.create(request=request)
        except ProviderSecretError:
            raise AnthropicScorerError(AnthropicScorerErrorCode.CREDENTIAL_UNAVAILABLE) from None
        except AnthropicTransportError as error:
            raise AnthropicScorerError(
                AnthropicScorerErrorCode.PROVIDER_UNAVAILABLE,
                transport_error=error,
            ) from None
        return _parse_outcome(response.output_text)


def build_anthropic_evaluation_scorer(
    *,
    configuration: EffectiveProviderConfiguration,
    secret_resolver: ProviderSecretResolver,
    transport_factory: AnthropicScoringTransportFactory | None = None,
) -> AnthropicEvaluationScorer:
    """Select only the configured EvaluationScoring primary profile."""

    if type(configuration) is not EffectiveProviderConfiguration:
        raise TypeError("configuration must be an EffectiveProviderConfiguration")
    route = next(
        (
            item
            for item in configuration.routes
            if item.workload_kind is ProviderWorkloadKind.EVALUATION_SCORING
        ),
        None,
    )
    if route is None:
        _configuration_error()
    model = next(
        (
            item
            for item in configuration.model_profiles
            if item.model_profile_id == route.primary_model_profile_id
        ),
        None,
    )
    if model is None:
        _configuration_error()
    provider = next(
        (
            item
            for item in configuration.provider_profiles
            if item.profile_id == model.provider_profile_id
        ),
        None,
    )
    if provider is None:
        _configuration_error()
    return AnthropicEvaluationScorer(
        provider_profile=provider,
        model_profile=model,
        secret_resolver=secret_resolver,
        transport_factory=(
            transport_factory
            if transport_factory is not None
            else AnthropicSDKScoringTransportFactory()
        ),
    )


def _parse_outcome(output_text: str) -> ScorerOutcome:
    try:
        payload = json.loads(output_text)
    except (json.JSONDecodeError, TypeError):
        _invalid_response()
    if type(payload) is not dict or set(payload) != {
        "status",
        "score_numerator",
        "score_denominator",
    }:
        _invalid_response()
    status = payload["status"]
    numerator = payload["score_numerator"]
    denominator = payload["score_denominator"]
    if status == "INCONCLUSIVE":
        if numerator is not None or denominator is not None:
            _invalid_response()
        return ScorerOutcome(ScoreStatus.INCONCLUSIVE)
    if status != "SCORED":
        _invalid_response()
    if type(numerator) is not int or type(denominator) is not int:
        _invalid_response()
    try:
        score = NormalizedScore(numerator, denominator)
    except (TypeError, ValueError):
        _invalid_response()
    return ScorerOutcome(ScoreStatus.SCORED, score)


def _validate_configuration(
    provider: ProviderProfileConfig,
    model: ModelProfileConfig,
) -> None:
    if type(provider) is not ProviderProfileConfig:
        raise TypeError("provider_profile must be a ProviderProfileConfig")
    if type(model) is not ModelProfileConfig:
        raise TypeError("model_profile must be a ModelProfileConfig")
    configured_output_limit = (
        model.invocation_limits.max_output_tokens or model.context_limits.reserved_output_tokens
    )
    if (
        not provider.enabled
        or not model.enabled
        or provider.provider_code.value != "anthropic"
        or model.provider_profile_id != provider.profile_id
        or model.model_code.value != _MODEL_CODE
        or not model.structured_output_required
        or ProviderWorkloadKind.EVALUATION_SCORING not in model.supported_workloads
        or configured_output_limit < _MAX_OUTPUT_TOKENS
    ):
        _configuration_error()


def _configuration_error() -> None:
    raise ProviderConfigurationError(
        ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
    ) from None


def _invalid_response() -> None:
    raise AnthropicScorerError(AnthropicScorerErrorCode.INVALID_RESPONSE) from None
