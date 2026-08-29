"""Closed composition of a configured OpenAI GenerationPort adapter."""

from __future__ import annotations

from typing import NoReturn

from backend.adapters.outbound.generation.openai import (
    OpenAIGenerationAdapter,
)
from backend.adapters.outbound.openai import (
    OpenAIResponsesTransportFactory,
    OpenAISDKResponsesTransportFactory,
)
from backend.adapters.outbound.review.openai import OpenAIReviewAdapter
from backend.adapters.outbound.semantic import (
    ConfiguredEmbeddingService,
    EmbeddingTransportFactory,
    OpenAISDKEmbeddingTransportFactory,
)
from backend.infrastructure.config.effective_config.provider import (
    EffectiveProviderConfiguration,
)
from backend.infrastructure.config.schemas.provider import (
    EmbeddingProfileConfig,
    ModelProfileConfig,
    ProviderConfigurationError,
    ProviderConfigurationErrorCode,
    ProviderProfileConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretResolver


def build_openai_generation_adapter(
    *,
    configuration: EffectiveProviderConfiguration,
    workload_kind: ProviderWorkloadKind,
    secret_resolver: ProviderSecretResolver,
    transport_factory: OpenAIResponsesTransportFactory | None = None,
) -> OpenAIGenerationAdapter:
    """Select only the explicit primary route; fallback is intentionally external."""

    if type(configuration) is not EffectiveProviderConfiguration:
        raise TypeError("configuration must be an EffectiveProviderConfiguration")
    if workload_kind not in {
        ProviderWorkloadKind.GENERATION,
        ProviderWorkloadKind.CORRECTION,
    }:
        _configuration_error()
    route = next(
        (item for item in configuration.routes if item.workload_kind is workload_kind),
        None,
    )
    if route is None:
        _configuration_error()
    model = _model_by_id(configuration, route.primary_model_profile_id.value)
    provider = _provider_by_id(configuration, model.provider_profile_id.value)
    return OpenAIGenerationAdapter(
        provider_profile=provider,
        model_profile=model,
        secret_resolver=secret_resolver,
        transport_factory=(
            transport_factory
            if transport_factory is not None
            else OpenAISDKResponsesTransportFactory()
        ),
    )


def build_openai_review_adapter(
    *,
    configuration: EffectiveProviderConfiguration,
    secret_resolver: ProviderSecretResolver,
    transport_factory: OpenAIResponsesTransportFactory | None = None,
) -> OpenAIReviewAdapter:
    """Compose only the configured Review primary; never execute fallbacks."""

    if type(configuration) is not EffectiveProviderConfiguration:
        raise TypeError("configuration must be an EffectiveProviderConfiguration")
    route = next(
        (
            item
            for item in configuration.routes
            if item.workload_kind is ProviderWorkloadKind.REVIEW
        ),
        None,
    )
    if route is None:
        _configuration_error()
    model = _model_by_id(configuration, route.primary_model_profile_id.value)
    provider = _provider_by_id(configuration, model.provider_profile_id.value)
    return OpenAIReviewAdapter(
        provider_profile=provider,
        model_profile=model,
        secret_resolver=secret_resolver,
        transport_factory=(
            transport_factory
            if transport_factory is not None
            else OpenAISDKResponsesTransportFactory()
        ),
    )


def build_openai_embedding_service(
    *,
    configuration: EffectiveProviderConfiguration,
    secret_resolver: ProviderSecretResolver,
    transport_factory: EmbeddingTransportFactory | None = None,
) -> ConfiguredEmbeddingService:
    if type(configuration) is not EffectiveProviderConfiguration:
        raise TypeError("configuration must be an EffectiveProviderConfiguration")
    route = next(
        (
            item
            for item in configuration.routes
            if item.workload_kind is ProviderWorkloadKind.SEMANTIC_EMBEDDING
        ),
        None,
    )
    if route is None:
        _configuration_error()
    embedding = _embedding_by_id(
        configuration,
        route.primary_model_profile_id.value,
    )
    provider = _provider_by_id(
        configuration,
        embedding.provider_profile_id.value,
    )
    return ConfiguredEmbeddingService(
        provider_profile=provider,
        embedding_profile=embedding,
        secret_resolver=secret_resolver,
        transport_factory=(
            transport_factory
            if transport_factory is not None
            else OpenAISDKEmbeddingTransportFactory()
        ),
    )


def _model_by_id(
    configuration: EffectiveProviderConfiguration,
    model_profile_id: str,
) -> ModelProfileConfig:
    model = next(
        (
            item
            for item in configuration.model_profiles
            if item.model_profile_id.value == model_profile_id
        ),
        None,
    )
    if model is None:
        _configuration_error()
    return model


def _provider_by_id(
    configuration: EffectiveProviderConfiguration,
    provider_profile_id: str,
) -> ProviderProfileConfig:
    provider = next(
        (
            item
            for item in configuration.provider_profiles
            if item.profile_id.value == provider_profile_id
        ),
        None,
    )
    if provider is None:
        _configuration_error()
    return provider


def _embedding_by_id(
    configuration: EffectiveProviderConfiguration,
    model_profile_id: str,
) -> EmbeddingProfileConfig:
    embedding = next(
        (
            item
            for item in configuration.embedding_profiles
            if item.model_profile_id.value == model_profile_id
        ),
        None,
    )
    if embedding is None:
        _configuration_error()
    return embedding


def _configuration_error() -> NoReturn:
    raise ProviderConfigurationError(
        ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
    )
