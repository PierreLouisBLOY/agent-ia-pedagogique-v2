from __future__ import annotations

import pytest

from backend.adapters.outbound.generation.openai import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
)
from backend.infrastructure.composition.factories.openai import (
    build_openai_generation_adapter,
)
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
    ProviderConfigurationError,
    ProviderConfigurationErrorCode,
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
from tests.support.openai_generation_fakes import (
    RecordingOpenAIResponsesTransport,
    RecordingOpenAITransportFactory,
)


def _configuration() -> ProviderConfiguration:
    provider_id = ProviderProfileId("openai-provider")
    terra_id = ModelProfileId("terra-profile")
    sol_id = ModelProfileId("sol-profile")
    limits = ProviderInvocationLimits(1, 30_000, max_output_tokens=32_000)
    context = ModelContextLimits(1_050_000, 900_000, 128_000)
    return ProviderConfiguration(
        ProviderConfigurationVersion(1, 0),
        (
            ProviderProfileConfig(
                provider_id,
                ProviderCode("openai"),
                ProviderCredentialRef("OPENAI_API_KEY"),
            ),
        ),
        (
            ModelProfileConfig(
                terra_id,
                provider_id,
                ModelCode("gpt-5.6-terra"),
                context,
                limits,
                (ProviderWorkloadKind.GENERATION,),
                structured_output_required=True,
            ),
            ModelProfileConfig(
                sol_id,
                provider_id,
                ModelCode("gpt-5.6-sol"),
                context,
                limits,
                (ProviderWorkloadKind.CORRECTION,),
                structured_output_required=True,
            ),
        ),
        (
            ProviderRouteConfig(
                ProviderWorkloadKind.GENERATION,
                terra_id,
            ),
            ProviderRouteConfig(
                ProviderWorkloadKind.CORRECTION,
                sol_id,
            ),
        ),
    )


@pytest.mark.parametrize(
    ("workload", "model_code"),
    (
        (ProviderWorkloadKind.GENERATION, "gpt-5.6-terra"),
        (ProviderWorkloadKind.CORRECTION, "gpt-5.6-sol"),
    ),
)
def test_factory_selects_only_the_explicit_primary_route(
    workload: ProviderWorkloadKind,
    model_code: str,
) -> None:
    transport = RecordingOpenAIResponsesTransport(
        response=OpenAIResponsesResponse(status=OpenAIResponseStatus.REFUSED)
    )
    adapter = build_openai_generation_adapter(
        configuration=build_effective_provider_configuration(_configuration()),
        workload_kind=workload,
        secret_resolver=EnvironmentProviderSecretResolver({}),
        transport_factory=RecordingOpenAITransportFactory(transport),
    )
    assert f"model_profile_id={'terra-profile' if 'terra' in model_code else 'sol-profile'!r}" in repr(
        adapter
    )


def test_factory_rejects_non_generation_workload() -> None:
    transport = RecordingOpenAIResponsesTransport(
        response=OpenAIResponsesResponse(status=OpenAIResponseStatus.REFUSED)
    )
    with pytest.raises(ProviderConfigurationError) as raised:
        build_openai_generation_adapter(
            configuration=build_effective_provider_configuration(_configuration()),
            workload_kind=ProviderWorkloadKind.REVIEW,
            secret_resolver=EnvironmentProviderSecretResolver({}),
            transport_factory=RecordingOpenAITransportFactory(transport),
        )
    assert (
        raised.value.code
        is ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
    )
