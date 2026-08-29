"""Deterministic safe provider configuration snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from backend.infrastructure.config.schemas.provider import (
    EmbeddingProfileConfig,
    ModelProfileConfig,
    ProviderConfiguration,
    ProviderConfigurationVersion,
    ProviderProfileConfig,
    ProviderRouteConfig,
)


@dataclass(frozen=True, slots=True)
class EffectiveProviderConfiguration:
    """Resolved technical routing data containing credential references only."""

    schema_version: ProviderConfigurationVersion
    provider_profiles: tuple[ProviderProfileConfig, ...]
    model_profiles: tuple[ModelProfileConfig, ...]
    routes: tuple[ProviderRouteConfig, ...]
    embedding_profiles: tuple[EmbeddingProfileConfig, ...] = ()

    def __post_init__(self) -> None:
        normalized = ProviderConfiguration(
            schema_version=self.schema_version,
            provider_profiles=self.provider_profiles,
            model_profiles=self.model_profiles,
            routes=self.routes,
            embedding_profiles=self.embedding_profiles,
        )
        if any(not profile.enabled for profile in normalized.provider_profiles):
            raise ValueError("effective provider profiles must be enabled")
        if any(not profile.enabled for profile in normalized.model_profiles):
            raise ValueError("effective model profiles must be enabled")
        if any(not profile.enabled for profile in normalized.embedding_profiles):
            raise ValueError("effective embedding profiles must be enabled")


def build_effective_provider_configuration(
    source: ProviderConfiguration,
) -> EffectiveProviderConfiguration:
    """Build an immutable, order-stable snapshot without resolving credentials."""

    if type(source) is not ProviderConfiguration:
        raise TypeError("source must be a ProviderConfiguration")
    return EffectiveProviderConfiguration(
        schema_version=source.schema_version,
        provider_profiles=tuple(
            sorted(
                (item for item in source.provider_profiles if item.enabled),
                key=lambda item: item.profile_id.value,
            )
        ),
        model_profiles=tuple(
            sorted(
                (item for item in source.model_profiles if item.enabled),
                key=lambda item: item.model_profile_id.value,
            )
        ),
        routes=tuple(sorted(source.routes, key=lambda item: item.workload_kind.value)),
        embedding_profiles=tuple(
            sorted(
                (item for item in source.embedding_profiles if item.enabled),
                key=lambda item: item.model_profile_id.value,
            )
        ),
    )
