from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.infrastructure.config.effective_config.provider import (
    build_effective_provider_configuration,
)
from backend.infrastructure.config.loaders.provider import load_provider_configuration
from backend.infrastructure.config.schemas.provider import (
    EmbeddingProfileConfig,
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderConfiguration,
    ProviderConfigurationError,
    ProviderConfigurationErrorCode,
    ProviderConfigurationVersion,
    ProviderCostLimit,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderRouteConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef


def _provider(
    profile_id: str = "provider-profile-a",
    *,
    code: str = "provider-a",
    credential_ref: str = "credential-ref-a",
    enabled: bool = True,
) -> ProviderProfileConfig:
    return ProviderProfileConfig(
        ProviderProfileId(profile_id),
        ProviderCode(code),
        ProviderCredentialRef(credential_ref),
        enabled,
    )


def _limits() -> ProviderInvocationLimits:
    return ProviderInvocationLimits(
        max_attempts=2,
        call_timeout_milliseconds=30_000,
        max_input_tokens=2_000,
        max_output_tokens=1_000,
        max_total_tokens=3_000,
        max_cost=ProviderCostLimit(250_000, "EUR"),
    )


def _context() -> ModelContextLimits:
    return ModelContextLimits(
        context_window_tokens=8_000,
        max_provider_input_tokens=6_000,
        reserved_output_tokens=2_000,
    )


def _model(
    model_profile_id: str = "model-profile-a",
    *,
    provider_profile_id: str = "provider-profile-a",
    code: str = "model-a",
    workloads: tuple[ProviderWorkloadKind, ...] = (
        ProviderWorkloadKind.GENERATION,
    ),
    enabled: bool = True,
) -> ModelProfileConfig:
    return ModelProfileConfig(
        ModelProfileId(model_profile_id),
        ProviderProfileId(provider_profile_id),
        ModelCode(code),
        _context(),
        _limits(),
        workloads,
        enabled,
    )


def _route(
    model_profile_id: str = "model-profile-a",
    *,
    workload: ProviderWorkloadKind = ProviderWorkloadKind.GENERATION,
    fallbacks: tuple[ModelProfileId, ...] = (),
) -> ProviderRouteConfig:
    return ProviderRouteConfig(
        workload,
        ModelProfileId(model_profile_id),
        fallbacks,
    )


def _embedding(
    model_profile_id: str = "embedding-profile-a",
    *,
    provider_profile_id: str = "provider-profile-a",
    code: str = "text-embedding-3-small",
    dimensions: int | None = 256,
) -> EmbeddingProfileConfig:
    return EmbeddingProfileConfig(
        ModelProfileId(model_profile_id),
        ProviderProfileId(provider_profile_id),
        ModelCode(code),
        8_192,
        300_000,
        30_000,
        dimensions,
    )


def _configuration() -> ProviderConfiguration:
    return ProviderConfiguration(
        ProviderConfigurationVersion(1, 0),
        (_provider(),),
        (_model(),),
        (_route(),),
    )


def test_valid_configuration_and_effective_snapshot_are_deterministic() -> None:
    provider_b = _provider(
        "provider-profile-b",
        code="provider-b",
        credential_ref="credential-ref-b",
    )
    model_b = _model(
        "model-profile-b",
        provider_profile_id="provider-profile-b",
        code="model-b",
    )
    source = ProviderConfiguration(
        ProviderConfigurationVersion(1, 0),
        (provider_b, _provider()),
        (model_b, _model()),
        (
            _route(
                fallbacks=(ModelProfileId("model-profile-b"),),
            ),
        ),
    )

    first = build_effective_provider_configuration(source)
    second = build_effective_provider_configuration(source)

    assert first == second
    assert tuple(item.profile_id.value for item in first.provider_profiles) == (
        "provider-profile-a",
        "provider-profile-b",
    )
    assert tuple(item.model_profile_id.value for item in first.model_profiles) == (
        "model-profile-a",
        "model-profile-b",
    )
    with pytest.raises(FrozenInstanceError):
        first.routes = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("providers", "models", "expected_code"),
    [
        (
            (_provider(), _provider()),
            (_model(),),
            ProviderConfigurationErrorCode.DUPLICATE_PROVIDER_PROFILE,
        ),
        (
            (_provider(),),
            (_model(), _model()),
            ProviderConfigurationErrorCode.DUPLICATE_MODEL_PROFILE,
        ),
    ],
)
def test_configuration_rejects_duplicate_profile_ids(
    providers: tuple[ProviderProfileConfig, ...],
    models: tuple[ModelProfileConfig, ...],
    expected_code: ProviderConfigurationErrorCode,
) -> None:
    with pytest.raises(ProviderConfigurationError) as raised:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 0),
            providers,
            models,
            (_route(),),
        )
    assert raised.value.code is expected_code


def test_model_rejects_unknown_provider_reference() -> None:
    with pytest.raises(ProviderConfigurationError) as raised:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 0),
            (_provider(),),
            (_model(provider_profile_id="provider-profile-unknown"),),
            (_route(),),
        )
    assert raised.value.code is ProviderConfigurationErrorCode.UNKNOWN_PROVIDER_PROFILE


def test_route_rejects_unknown_or_incompatible_model_reference() -> None:
    with pytest.raises(ProviderConfigurationError) as unknown:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 0),
            (_provider(),),
            (_model(),),
            (_route("model-profile-unknown"),),
        )
    assert unknown.value.code is ProviderConfigurationErrorCode.UNKNOWN_MODEL_PROFILE

    with pytest.raises(ProviderConfigurationError) as incompatible:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 0),
            (_provider(),),
            (_model(workloads=(ProviderWorkloadKind.REVIEW,)),),
            (_route(),),
        )
    assert (
        incompatible.value.code
        is ProviderConfigurationErrorCode.INCOMPATIBLE_MODEL_WORKLOAD
    )


def test_route_rejects_duplicate_fallback_and_primary_as_fallback() -> None:
    duplicate = (ModelProfileId("model-profile-b"),) * 2
    with pytest.raises(ProviderConfigurationError) as repeated:
        _route(fallbacks=duplicate)
    assert repeated.value.code is ProviderConfigurationErrorCode.INVALID_PROVIDER_ROUTE

    with pytest.raises(ProviderConfigurationError) as primary:
        _route(fallbacks=(ModelProfileId("model-profile-a"),))
    assert primary.value.code is ProviderConfigurationErrorCode.INVALID_PROVIDER_ROUTE


def test_configuration_rejects_duplicate_workload_owner() -> None:
    with pytest.raises(ProviderConfigurationError) as raised:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 0),
            (_provider(),),
            (_model(),),
            (_route(), _route()),
        )
    assert raised.value.code is ProviderConfigurationErrorCode.DUPLICATE_WORKLOAD_ROUTE


@pytest.mark.parametrize(
    ("provider_enabled", "model_enabled", "expected_code"),
    [
        (
            False,
            True,
            ProviderConfigurationErrorCode.DISABLED_PROVIDER_PROFILE,
        ),
        (
            True,
            False,
            ProviderConfigurationErrorCode.DISABLED_MODEL_PROFILE,
        ),
    ],
)
def test_route_rejects_disabled_provider_or_model(
    provider_enabled: bool,
    model_enabled: bool,
    expected_code: ProviderConfigurationErrorCode,
) -> None:
    with pytest.raises(ProviderConfigurationError) as raised:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 0),
            (_provider(enabled=provider_enabled),),
            (_model(enabled=model_enabled),),
            (_route(),),
        )
    assert raised.value.code is expected_code


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_attempts": 0},
        {"max_attempts": 11},
        {"call_timeout_milliseconds": 0},
        {"max_input_tokens": 0},
        {"max_output_tokens": -1},
        {"max_total_tokens": 2_999},
    ],
)
def test_invocation_limits_fail_closed(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "max_attempts": 2,
        "call_timeout_milliseconds": 30_000,
        "max_input_tokens": 2_000,
        "max_output_tokens": 1_000,
        "max_total_tokens": 3_000,
    }
    values.update(overrides)
    with pytest.raises((TypeError, ValueError)):
        ProviderInvocationLimits(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("context", "input_tokens", "reserved"),
    [
        (0, 1, 1),
        (8_000, 8_001, 1),
        (8_000, 7_000, 1_001),
        (8_000, 1, 8_000),
    ],
)
def test_context_limits_reject_invalid_capacity_math(
    context: int,
    input_tokens: int,
    reserved: int,
) -> None:
    with pytest.raises(ValueError):
        ModelContextLimits(context, input_tokens, reserved)


def test_cost_limit_uses_exact_integer_microunits() -> None:
    limit = ProviderCostLimit(125_001, "EUR")
    assert limit.amount_microunits == 125_001
    with pytest.raises(TypeError):
        ProviderCostLimit(0.1, "EUR")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ProviderCostLimit(1, "eur")


def test_loader_parses_controlled_mapping_without_secret_values() -> None:
    source: dict[str, object] = {
        "schema_version": {"major": 1, "minor": 0},
        "providers": (
            {
                "profile_id": "provider-profile-a",
                "provider_code": "provider-a",
                "credential_ref": "credential-ref-a",
            },
        ),
        "models": (
            {
                "model_profile_id": "model-profile-a",
                "provider_profile_id": "provider-profile-a",
                "model_code": "model-a",
                "context_limits": {
                    "context_window_tokens": 8_000,
                    "max_provider_input_tokens": 6_000,
                    "reserved_output_tokens": 2_000,
                },
                "invocation_limits": {
                    "max_attempts": 2,
                    "call_timeout_milliseconds": 30_000,
                    "max_input_tokens": 2_000,
                    "max_output_tokens": 1_000,
                    "max_total_tokens": 3_000,
                    "max_cost": {
                        "amount_microunits": 250_000,
                        "currency_code": "EUR",
                    },
                },
                "supported_workloads": ("GENERATION",),
            },
        ),
        "routes": (
            {
                "workload_kind": "GENERATION",
                "primary_model_profile_id": "model-profile-a",
            },
        ),
    }

    assert load_provider_configuration(source) == _configuration()

    provider = source["providers"][0]  # type: ignore[index]
    assert isinstance(provider, dict)
    provider["credential_value"] = "synthetic-secret-must-not-enter-config"
    with pytest.raises(ProviderConfigurationError) as raised:
        load_provider_configuration(source)
    assert (
        raised.value.code
        is ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
    )
    assert "synthetic-secret-must-not-enter-config" not in str(raised.value)


def test_active_configuration_requires_a_route() -> None:
    with pytest.raises(ProviderConfigurationError) as raised:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 0),
            (_provider(),),
            (_model(),),
            (),
        )
    assert (
        raised.value.code
        is ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
    )


def test_embedding_profile_routes_without_fake_generation_limits() -> None:
    configuration = ProviderConfiguration(
        ProviderConfigurationVersion(1, 1),
        (_provider(),),
        (),
        (
            _route(
                "embedding-profile-a",
                workload=ProviderWorkloadKind.SEMANTIC_EMBEDDING,
            ),
        ),
        (_embedding(),),
    )

    effective = build_effective_provider_configuration(configuration)

    assert effective.embedding_profiles == (_embedding(),)
    assert not hasattr(effective.embedding_profiles[0], "reserved_output_tokens")
    assert not hasattr(effective.embedding_profiles[0], "context_limits")
    assert effective.routes[0].workload_kind is ProviderWorkloadKind.SEMANTIC_EMBEDDING


def test_embedding_route_rejects_generation_profile_and_duplicate_id() -> None:
    with pytest.raises(ProviderConfigurationError) as incompatible:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 1),
            (_provider(),),
            (_model(),),
            (
                _route(
                    workload=ProviderWorkloadKind.SEMANTIC_EMBEDDING,
                ),
            ),
        )
    assert (
        incompatible.value.code
        is ProviderConfigurationErrorCode.INCOMPATIBLE_MODEL_WORKLOAD
    )

    with pytest.raises(ProviderConfigurationError) as duplicate:
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 1),
            (_provider(),),
            (_model("shared-id"),),
            (_route("shared-id"),),
            (_embedding("shared-id"),),
        )
    assert duplicate.value.code is ProviderConfigurationErrorCode.DUPLICATE_MODEL_PROFILE


def test_loader_parses_embedding_profile_without_credential_material() -> None:
    source: dict[str, object] = {
        "schema_version": {"major": 1, "minor": 1},
        "providers": (
            {
                "profile_id": "provider-profile-a",
                "provider_code": "openai",
                "credential_ref": "OPENAI_API_KEY",
            },
        ),
        "models": (),
        "embeddings": (
            {
                "model_profile_id": "embedding-profile-a",
                "provider_profile_id": "provider-profile-a",
                "model_code": "text-embedding-3-small",
                "max_input_tokens_per_item": 8_192,
                "max_batch_input_tokens": 300_000,
                "call_timeout_milliseconds": 30_000,
                "requested_dimensions": 256,
                "max_attempts": 1,
            },
        ),
        "routes": (
            {
                "workload_kind": "SEMANTIC_EMBEDDING",
                "primary_model_profile_id": "embedding-profile-a",
            },
        ),
    }

    loaded = load_provider_configuration(source)

    assert loaded.embedding_profiles[0] == EmbeddingProfileConfig(
        ModelProfileId("embedding-profile-a"),
        ProviderProfileId("provider-profile-a"),
        ModelCode("text-embedding-3-small"),
        8_192,
        300_000,
        30_000,
        256,
    )
    assert "credential_value" not in repr(loaded)


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_input_tokens_per_item": 0},
        {"max_batch_input_tokens": 8_191},
        {"call_timeout_milliseconds": 0},
        {"requested_dimensions": 0},
        {"max_attempts": 2},
    ],
)
def test_embedding_profile_limits_fail_closed(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "model_profile_id": ModelProfileId("embedding"),
        "provider_profile_id": ProviderProfileId("provider"),
        "model_code": ModelCode("embedding-model"),
        "max_input_tokens_per_item": 8_192,
        "max_batch_input_tokens": 300_000,
        "call_timeout_milliseconds": 30_000,
        "requested_dimensions": 256,
        "max_attempts": 1,
    }
    values.update(overrides)
    with pytest.raises((TypeError, ValueError)):
        EmbeddingProfileConfig(**values)  # type: ignore[arg-type]
