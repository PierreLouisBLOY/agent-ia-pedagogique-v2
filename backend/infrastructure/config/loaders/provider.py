"""Pure strict parser for provider-neutral configuration mappings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

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
    ProviderCostLimit,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderRouteConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef


def load_provider_configuration(source: Mapping[str, object]) -> ProviderConfiguration:
    """Parse a controlled in-memory mapping without resolving any credential."""

    if not isinstance(source, Mapping):
        raise TypeError("source must be a mapping")
    try:
        _require_keys(
            source,
            required=frozenset({"schema_version", "providers", "models", "routes"}),
        )
        version = _parse_version(_mapping(source, "schema_version"))
        providers = tuple(
            _parse_provider(item) for item in _mapping_sequence(source, "providers")
        )
        models = tuple(_parse_model(item) for item in _mapping_sequence(source, "models"))
        routes = tuple(_parse_route(item) for item in _mapping_sequence(source, "routes"))
        return ProviderConfiguration(version, providers, models, routes)
    except ProviderConfigurationError:
        raise
    except (KeyError, TypeError, ValueError):
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
        ) from None


def _parse_version(source: Mapping[str, object]) -> ProviderConfigurationVersion:
    _require_keys(source, required=frozenset({"major", "minor"}))
    return ProviderConfigurationVersion(_integer(source, "major"), _integer(source, "minor"))


def _parse_provider(source: Mapping[str, object]) -> ProviderProfileConfig:
    _require_keys(
        source,
        required=frozenset({"profile_id", "provider_code", "credential_ref"}),
        optional=frozenset({"enabled"}),
    )
    return ProviderProfileConfig(
        profile_id=ProviderProfileId(_string(source, "profile_id")),
        provider_code=ProviderCode(_string(source, "provider_code")),
        credential_ref=ProviderCredentialRef(_string(source, "credential_ref")),
        enabled=_optional_bool(source, "enabled", default=True),
    )


def _parse_model(source: Mapping[str, object]) -> ModelProfileConfig:
    _require_keys(
        source,
        required=frozenset(
            {
                "model_profile_id",
                "provider_profile_id",
                "model_code",
                "context_limits",
                "invocation_limits",
                "supported_workloads",
            }
        ),
        optional=frozenset({"enabled", "structured_output_required"}),
    )
    workloads = tuple(
        ProviderWorkloadKind(_sequence_string(item))
        for item in _sequence(source, "supported_workloads")
    )
    return ModelProfileConfig(
        model_profile_id=ModelProfileId(_string(source, "model_profile_id")),
        provider_profile_id=ProviderProfileId(_string(source, "provider_profile_id")),
        model_code=ModelCode(_string(source, "model_code")),
        context_limits=_parse_context_limits(_mapping(source, "context_limits")),
        invocation_limits=_parse_invocation_limits(
            _mapping(source, "invocation_limits")
        ),
        supported_workloads=workloads,
        enabled=_optional_bool(source, "enabled", default=True),
        structured_output_required=_optional_bool(
            source,
            "structured_output_required",
            default=False,
        ),
    )


def _parse_context_limits(source: Mapping[str, object]) -> ModelContextLimits:
    _require_keys(
        source,
        required=frozenset(
            {
                "context_window_tokens",
                "max_provider_input_tokens",
                "reserved_output_tokens",
            }
        ),
    )
    return ModelContextLimits(
        context_window_tokens=_integer(source, "context_window_tokens"),
        max_provider_input_tokens=_integer(source, "max_provider_input_tokens"),
        reserved_output_tokens=_integer(source, "reserved_output_tokens"),
    )


def _parse_invocation_limits(source: Mapping[str, object]) -> ProviderInvocationLimits:
    _require_keys(
        source,
        required=frozenset({"max_attempts", "call_timeout_milliseconds"}),
        optional=frozenset(
            {
                "max_input_tokens",
                "max_output_tokens",
                "max_total_tokens",
                "max_cost",
            }
        ),
    )
    raw_cost = source.get("max_cost")
    cost = None if raw_cost is None else _parse_cost(_required_mapping_value(raw_cost))
    return ProviderInvocationLimits(
        max_attempts=_integer(source, "max_attempts"),
        call_timeout_milliseconds=_integer(source, "call_timeout_milliseconds"),
        max_input_tokens=_optional_int(source, "max_input_tokens"),
        max_output_tokens=_optional_int(source, "max_output_tokens"),
        max_total_tokens=_optional_int(source, "max_total_tokens"),
        max_cost=cost,
    )


def _parse_cost(source: Mapping[str, object]) -> ProviderCostLimit:
    _require_keys(
        source,
        required=frozenset({"amount_microunits", "currency_code"}),
    )
    return ProviderCostLimit(
        amount_microunits=_integer(source, "amount_microunits"),
        currency_code=_string(source, "currency_code"),
    )


def _parse_route(source: Mapping[str, object]) -> ProviderRouteConfig:
    _require_keys(
        source,
        required=frozenset({"workload_kind", "primary_model_profile_id"}),
        optional=frozenset({"fallback_model_profile_ids"}),
    )
    fallback_source = source.get("fallback_model_profile_ids", ())
    if isinstance(fallback_source, (str, bytes)) or not isinstance(
        fallback_source, Sequence
    ):
        raise TypeError("fallback_model_profile_ids must be a sequence")
    return ProviderRouteConfig(
        workload_kind=ProviderWorkloadKind(_string(source, "workload_kind")),
        primary_model_profile_id=ModelProfileId(
            _string(source, "primary_model_profile_id")
        ),
        fallback_model_profile_ids=tuple(
            ModelProfileId(_sequence_string(item)) for item in fallback_source
        ),
    )


def _require_keys(
    source: Mapping[str, object],
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    keys = frozenset(source)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise ValueError("configuration mapping has invalid keys")


def _string(source: Mapping[str, object], key: str) -> str:
    value = source[key]
    if not isinstance(value, str):
        raise TypeError("configuration value must be a string")
    return value


def _integer(source: Mapping[str, object], key: str) -> int:
    value = source[key]
    if type(value) is not int:
        raise TypeError("configuration value must be an integer")
    return value


def _optional_int(source: Mapping[str, object], key: str) -> int | None:
    value = source.get(key)
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError("configuration value must be an integer")
    return value


def _optional_bool(source: Mapping[str, object], key: str, *, default: bool) -> bool:
    value = source.get(key, default)
    if type(value) is not bool:
        raise TypeError("configuration value must be a bool")
    return value


def _mapping(source: Mapping[str, object], key: str) -> Mapping[str, object]:
    return _required_mapping_value(source[key])


def _required_mapping_value(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise TypeError("configuration value must be a string-keyed mapping")
    return value


def _sequence(source: Mapping[str, object], key: str) -> Sequence[object]:
    value = source[key]
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("configuration value must be a sequence")
    return value


def _mapping_sequence(
    source: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    return tuple(_required_mapping_value(item) for item in _sequence(source, key))


def _sequence_string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("configuration sequence item must be a string")
    return value
