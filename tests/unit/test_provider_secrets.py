from __future__ import annotations

from dataclasses import dataclass

import pytest

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
    ProviderSecretError,
    ProviderSecretErrorCode,
    ProviderSecretResolver,
    ProviderSecretValue,
)

_RAW_SECRET = "synthetic-provider-secret-value"


@dataclass(frozen=True)
class _SecretHolder:
    value: ProviderSecretValue


def _safe_configuration() -> ProviderConfiguration:
    provider_id = ProviderProfileId("provider-profile-a")
    model_id = ModelProfileId("model-profile-a")
    return ProviderConfiguration(
        ProviderConfigurationVersion(1, 0),
        (
            ProviderProfileConfig(
                provider_id,
                ProviderCode("provider-a"),
                ProviderCredentialRef("credential-ref-a"),
            ),
        ),
        (
            ModelProfileConfig(
                model_id,
                provider_id,
                ModelCode("model-a"),
                ModelContextLimits(8_000, 6_000, 2_000),
                ProviderInvocationLimits(1, 30_000),
                (ProviderWorkloadKind.GENERATION,),
            ),
        ),
        (
            ProviderRouteConfig(
                ProviderWorkloadKind.GENERATION,
                model_id,
            ),
        ),
    )


def test_environment_resolver_returns_opaque_redacted_secret() -> None:
    resolver = EnvironmentProviderSecretResolver(
        {"credential-ref-a": _RAW_SECRET}
    )
    assert isinstance(resolver, ProviderSecretResolver)

    secret = resolver.resolve(ProviderCredentialRef("credential-ref-a"))

    assert secret.reveal_for_transport() == _RAW_SECRET
    assert str(secret) == "[REDACTED]"
    assert _RAW_SECRET not in repr(secret)
    assert _RAW_SECRET not in repr(resolver)
    assert _RAW_SECRET not in repr(_SecretHolder(secret))
    with pytest.raises(TypeError):
        hash(secret)


def test_missing_and_empty_secrets_fail_with_closed_raw_free_errors() -> None:
    missing = EnvironmentProviderSecretResolver({})
    with pytest.raises(ProviderSecretError) as missing_error:
        missing.resolve(ProviderCredentialRef("credential-ref-a"))
    assert missing_error.value.code is ProviderSecretErrorCode.MISSING_PROVIDER_SECRET

    empty = EnvironmentProviderSecretResolver({"credential-ref-a": ""})
    with pytest.raises(ProviderSecretError) as empty_error:
        empty.resolve(ProviderCredentialRef("credential-ref-a"))
    assert empty_error.value.code is ProviderSecretErrorCode.INVALID_PROVIDER_SECRET
    assert _RAW_SECRET not in str(missing_error.value)
    assert _RAW_SECRET not in str(empty_error.value)


def test_effective_config_contains_only_credential_reference() -> None:
    effective = build_effective_provider_configuration(_safe_configuration())
    rendered = repr(effective)

    assert "credential-ref-a" in rendered
    assert _RAW_SECRET not in rendered
    assert not hasattr(effective, "secret")
    assert not hasattr(effective.provider_profiles[0], "credential_value")
