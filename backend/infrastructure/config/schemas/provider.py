"""Provider-neutral configuration contracts with no runtime authority semantics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from backend.infrastructure.config.secrets.provider import ProviderCredentialRef

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
_MAX_ATTEMPTS = 10
_MAX_CALL_TIMEOUT_MILLISECONDS = 600_000


class ProviderConfigurationErrorCode(StrEnum):
    INVALID_PROVIDER_CONFIGURATION = "INVALID_PROVIDER_CONFIGURATION"
    DUPLICATE_PROVIDER_PROFILE = "DUPLICATE_PROVIDER_PROFILE"
    DUPLICATE_MODEL_PROFILE = "DUPLICATE_MODEL_PROFILE"
    UNKNOWN_PROVIDER_PROFILE = "UNKNOWN_PROVIDER_PROFILE"
    UNKNOWN_MODEL_PROFILE = "UNKNOWN_MODEL_PROFILE"
    INVALID_PROVIDER_ROUTE = "INVALID_PROVIDER_ROUTE"
    DUPLICATE_WORKLOAD_ROUTE = "DUPLICATE_WORKLOAD_ROUTE"
    DISABLED_PROVIDER_PROFILE = "DISABLED_PROVIDER_PROFILE"
    DISABLED_MODEL_PROFILE = "DISABLED_MODEL_PROFILE"
    INCOMPATIBLE_MODEL_WORKLOAD = "INCOMPATIBLE_MODEL_WORKLOAD"


class ProviderConfigurationError(ValueError):
    """Closed configuration failure that never embeds source values."""

    code: ProviderConfigurationErrorCode

    def __init__(self, code: ProviderConfigurationErrorCode) -> None:
        if type(code) is not ProviderConfigurationErrorCode:
            raise TypeError("code must be a ProviderConfigurationErrorCode")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ProviderProfileId:
    value: str

    def __post_init__(self) -> None:
        _validate_identifier(self.value, "provider profile id")


@dataclass(frozen=True, slots=True)
class ModelProfileId:
    value: str

    def __post_init__(self) -> None:
        _validate_identifier(self.value, "model profile id")


@dataclass(frozen=True, slots=True)
class ProviderCode:
    value: str

    def __post_init__(self) -> None:
        _validate_identifier(self.value, "provider code")


@dataclass(frozen=True, slots=True)
class ModelCode:
    value: str

    def __post_init__(self) -> None:
        _validate_identifier(self.value, "model code")


class ProviderWorkloadKind(StrEnum):
    """Technical routing vocabulary; values grant no capability or permission."""

    GENERATION = "GENERATION"
    CORRECTION = "CORRECTION"
    REVIEW = "REVIEW"
    EVALUATION_SCORING = "EVALUATION_SCORING"


@dataclass(frozen=True, slots=True)
class ProviderConfigurationVersion:
    major: int
    minor: int

    def __post_init__(self) -> None:
        _require_non_negative_int(self.major, "major")
        _require_non_negative_int(self.minor, "minor")
        if self.major < 1:
            raise ValueError("major must be >= 1")


@dataclass(frozen=True, slots=True)
class ProviderCostLimit:
    """Exact monetary ceiling; pricing remains outside this contract."""

    amount_microunits: int
    currency_code: str

    def __post_init__(self) -> None:
        _require_positive_int(self.amount_microunits, "amount_microunits")
        if not isinstance(self.currency_code, str):
            raise TypeError("currency_code must be a string")
        if _CURRENCY_CODE.fullmatch(self.currency_code) is None:
            raise ValueError("currency_code must contain three uppercase letters")


@dataclass(frozen=True, slots=True)
class ProviderInvocationLimits:
    """Per-invocation technical limits, distinct from the Recovery budget."""

    max_attempts: int
    call_timeout_milliseconds: int
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_cost: ProviderCostLimit | None = None

    def __post_init__(self) -> None:
        _require_bounded_positive_int(
            self.max_attempts,
            "max_attempts",
            maximum=_MAX_ATTEMPTS,
        )
        _require_bounded_positive_int(
            self.call_timeout_milliseconds,
            "call_timeout_milliseconds",
            maximum=_MAX_CALL_TIMEOUT_MILLISECONDS,
        )
        for field_name in (
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
        ):
            _require_optional_positive_int(getattr(self, field_name), field_name)
        if self.max_cost is not None and type(self.max_cost) is not ProviderCostLimit:
            raise TypeError("max_cost must be a ProviderCostLimit or None")

        required_total = sum(
            value
            for value in (self.max_input_tokens, self.max_output_tokens)
            if value is not None
        )
        if self.max_total_tokens is not None and self.max_total_tokens < required_total:
            raise ValueError("max_total_tokens must cover configured input and output limits")


@dataclass(frozen=True, slots=True)
class ModelContextLimits:
    """Technical model capacity, unrelated to pedagogical context."""

    context_window_tokens: int
    max_provider_input_tokens: int
    reserved_output_tokens: int

    def __post_init__(self) -> None:
        _require_positive_int(self.context_window_tokens, "context_window_tokens")
        _require_positive_int(
            self.max_provider_input_tokens,
            "max_provider_input_tokens",
        )
        _require_positive_int(self.reserved_output_tokens, "reserved_output_tokens")
        if self.max_provider_input_tokens > self.context_window_tokens:
            raise ValueError("max_provider_input_tokens exceeds context window")
        if self.reserved_output_tokens >= self.context_window_tokens:
            raise ValueError("reserved_output_tokens must be smaller than context window")
        if (
            self.max_provider_input_tokens + self.reserved_output_tokens
            > self.context_window_tokens
        ):
            raise ValueError("input and reserved output exceed context window")


@dataclass(frozen=True, slots=True)
class ProviderProfileConfig:
    profile_id: ProviderProfileId
    provider_code: ProviderCode
    credential_ref: ProviderCredentialRef
    enabled: bool = True

    def __post_init__(self) -> None:
        if type(self.profile_id) is not ProviderProfileId:
            raise TypeError("profile_id must be a ProviderProfileId")
        if type(self.provider_code) is not ProviderCode:
            raise TypeError("provider_code must be a ProviderCode")
        if type(self.credential_ref) is not ProviderCredentialRef:
            raise TypeError("credential_ref must be a ProviderCredentialRef")
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be a bool")


@dataclass(frozen=True, slots=True)
class ModelProfileConfig:
    model_profile_id: ModelProfileId
    provider_profile_id: ProviderProfileId
    model_code: ModelCode
    context_limits: ModelContextLimits
    invocation_limits: ProviderInvocationLimits
    supported_workloads: tuple[ProviderWorkloadKind, ...]
    enabled: bool = True
    structured_output_required: bool = False

    def __post_init__(self) -> None:
        if type(self.model_profile_id) is not ModelProfileId:
            raise TypeError("model_profile_id must be a ModelProfileId")
        if type(self.provider_profile_id) is not ProviderProfileId:
            raise TypeError("provider_profile_id must be a ProviderProfileId")
        if type(self.model_code) is not ModelCode:
            raise TypeError("model_code must be a ModelCode")
        if type(self.context_limits) is not ModelContextLimits:
            raise TypeError("context_limits must be ModelContextLimits")
        if type(self.invocation_limits) is not ProviderInvocationLimits:
            raise TypeError("invocation_limits must be ProviderInvocationLimits")
        _validate_workloads(self.supported_workloads, allow_empty=False)
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be a bool")
        if type(self.structured_output_required) is not bool:
            raise TypeError("structured_output_required must be a bool")


@dataclass(frozen=True, slots=True)
class ProviderRouteConfig:
    workload_kind: ProviderWorkloadKind
    primary_model_profile_id: ModelProfileId
    fallback_model_profile_ids: tuple[ModelProfileId, ...] = ()

    def __post_init__(self) -> None:
        if type(self.workload_kind) is not ProviderWorkloadKind:
            raise TypeError("workload_kind must be a ProviderWorkloadKind")
        if type(self.primary_model_profile_id) is not ModelProfileId:
            raise TypeError("primary_model_profile_id must be a ModelProfileId")
        fallbacks = self.fallback_model_profile_ids
        if type(fallbacks) is not tuple or any(
            type(item) is not ModelProfileId for item in fallbacks
        ):
            raise TypeError("fallback_model_profile_ids must contain ModelProfileId values")
        if len(fallbacks) != len(set(fallbacks)):
            raise ProviderConfigurationError(
                ProviderConfigurationErrorCode.INVALID_PROVIDER_ROUTE
            )
        if self.primary_model_profile_id in fallbacks:
            raise ProviderConfigurationError(
                ProviderConfigurationErrorCode.INVALID_PROVIDER_ROUTE
            )


@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
    schema_version: ProviderConfigurationVersion
    provider_profiles: tuple[ProviderProfileConfig, ...]
    model_profiles: tuple[ModelProfileConfig, ...]
    routes: tuple[ProviderRouteConfig, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not ProviderConfigurationVersion:
            raise TypeError("schema_version must be a ProviderConfigurationVersion")
        _validate_typed_tuple(
            self.provider_profiles,
            ProviderProfileConfig,
            "provider_profiles",
        )
        _validate_typed_tuple(self.model_profiles, ModelProfileConfig, "model_profiles")
        _validate_typed_tuple(self.routes, ProviderRouteConfig, "routes")
        _validate_provider_configuration(self)


def _validate_provider_configuration(config: ProviderConfiguration) -> None:
    provider_ids = tuple(item.profile_id for item in config.provider_profiles)
    if len(provider_ids) != len(set(provider_ids)):
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.DUPLICATE_PROVIDER_PROFILE
        )
    model_ids = tuple(item.model_profile_id for item in config.model_profiles)
    if len(model_ids) != len(set(model_ids)):
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.DUPLICATE_MODEL_PROFILE
        )
    workload_kinds = tuple(item.workload_kind for item in config.routes)
    if len(workload_kinds) != len(set(workload_kinds)):
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.DUPLICATE_WORKLOAD_ROUTE
        )

    providers = {item.profile_id: item for item in config.provider_profiles}
    models = {item.model_profile_id: item for item in config.model_profiles}
    active = any(item.enabled for item in config.provider_profiles) or any(
        item.enabled for item in config.model_profiles
    )
    if active and not config.routes:
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
        )

    for model in config.model_profiles:
        provider = providers.get(model.provider_profile_id)
        if provider is None:
            raise ProviderConfigurationError(
                ProviderConfigurationErrorCode.UNKNOWN_PROVIDER_PROFILE
            )
        if model.enabled and not provider.enabled:
            raise ProviderConfigurationError(
                ProviderConfigurationErrorCode.DISABLED_PROVIDER_PROFILE
            )

    for route in config.routes:
        for model_id in (
            route.primary_model_profile_id,
            *route.fallback_model_profile_ids,
        ):
            route_model = models.get(model_id)
            if route_model is None:
                raise ProviderConfigurationError(
                    ProviderConfigurationErrorCode.UNKNOWN_MODEL_PROFILE
                )
            if not route_model.enabled:
                raise ProviderConfigurationError(
                    ProviderConfigurationErrorCode.DISABLED_MODEL_PROFILE
                )
            provider = providers[route_model.provider_profile_id]
            if not provider.enabled:
                raise ProviderConfigurationError(
                    ProviderConfigurationErrorCode.DISABLED_PROVIDER_PROFILE
                )
            if route.workload_kind not in route_model.supported_workloads:
                raise ProviderConfigurationError(
                    ProviderConfigurationErrorCode.INCOMPATIBLE_MODEL_WORKLOAD
                )


def _validate_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field_name} has an invalid format")


def _validate_typed_tuple(
    values: tuple[object, ...],
    item_type: type[object],
    field_name: str,
) -> None:
    if type(values) is not tuple or any(type(item) is not item_type for item in values):
        raise TypeError(f"{field_name} contains unsupported values")


def _validate_workloads(
    values: tuple[ProviderWorkloadKind, ...],
    *,
    allow_empty: bool,
) -> None:
    if type(values) is not tuple or any(
        type(item) is not ProviderWorkloadKind for item in values
    ):
        raise TypeError("supported_workloads must contain ProviderWorkloadKind values")
    if not allow_empty and not values:
        raise ValueError("supported_workloads must not be empty")
    if len(values) != len(set(values)):
        raise ValueError("supported_workloads must contain unique values")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _require_optional_positive_int(value: int | None, field_name: str) -> None:
    if value is not None:
        _require_positive_int(value, field_name)


def _require_bounded_positive_int(
    value: int,
    field_name: str,
    *,
    maximum: int,
) -> None:
    _require_positive_int(value, field_name)
    if value > maximum:
        raise ValueError(f"{field_name} exceeds its technical ceiling")
