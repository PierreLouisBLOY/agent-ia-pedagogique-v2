"""Owner-approved local policy, not a statement of current provider availability."""

from dataclasses import replace

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
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef


def load_harden_profile() -> tuple[ProviderProfileConfig, ModelProfileConfig]:
    """Pure construction on explicit invocation; no default route or credential read."""
    provider = ProviderProfileConfig(
        ProviderProfileId("openai.r3.harden.private"),
        ProviderCode("openai"),
        ProviderCredentialRef("openai.r3.harden.private"),
    )
    model = ModelProfileConfig(
        ModelProfileId("openai.gpt-5.6-terra.harden.v1"),
        provider.profile_id,
        ModelCode("gpt-5.6-terra"),
        ModelContextLimits(1050000, 32768, 8192),
        ProviderInvocationLimits(1, 90000, 32768, 8192, 40960, None),
        (ProviderWorkloadKind.GENERATION,),
        structured_output_required=True,
    )
    return provider, model


def validate_harden_profile(
    model: ModelProfileConfig, provider: ProviderProfileConfig | None = None
) -> None:
    expected_provider, expected_model = load_harden_profile()
    cost = model.invocation_limits.max_cost
    # A later separately hash-bound grant can supply a cost; this loader never does.
    unpriced = replace(model, invocation_limits=replace(model.invocation_limits, max_cost=None))
    if (
        unpriced != expected_model
        or (cost is not None and cost.currency_code != "USD")
        or (provider is not None and provider != expected_provider)
    ):
        raise ValueError("R3_HARDEN_PROFILE_REJECTED")
