"""Explicit runtime configuration with provider execution disabled by default."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from calibration_tooling.adapters.anthropic.contracts import (
    ResolvedAnthropicConfiguration,
)
from calibration_tooling.contracts.errors import CalibrationErrorCode, fail_execution

CALIBRATION_RUNTIME_CONFIGURATION_VERSION: Final = "calibration-runtime.v1"
LIVE_PROVIDER_DEFAULT_ENABLED: Final = False


class CalibrationProviderCode(StrEnum):
    ANTHROPIC = "anthropic"


@dataclass(frozen=True, slots=True)
class CalibrationRuntimeConfiguration:
    schema_version: str = CALIBRATION_RUNTIME_CONFIGURATION_VERSION
    provider_code: CalibrationProviderCode = CalibrationProviderCode.ANTHROPIC
    live_provider_enabled: bool = LIVE_PROVIDER_DEFAULT_ENABLED
    anthropic: ResolvedAnthropicConfiguration | None = None

    def __post_init__(self) -> None:
        if self.schema_version != CALIBRATION_RUNTIME_CONFIGURATION_VERSION:
            raise ValueError("runtime configuration version is not supported")
        if self.provider_code is not CalibrationProviderCode.ANTHROPIC:
            raise ValueError("runtime provider is not supported")
        if type(self.live_provider_enabled) is not bool:
            raise TypeError("live_provider_enabled must be a bool")
        if (
            self.anthropic is not None
            and type(self.anthropic) is not ResolvedAnthropicConfiguration
        ):
            raise TypeError("anthropic configuration must be resolved")
        if self.live_provider_enabled and self.anthropic is None:
            raise ValueError("enabled provider requires resolved configuration")

    def __repr__(self) -> str:
        model = self.anthropic.model if self.anthropic is not None else None
        return (
            "CalibrationRuntimeConfiguration("
            f"provider_code={self.provider_code.value!r}, "
            f"live_provider_enabled={self.live_provider_enabled!r}, "
            f"model={model!r})"
        )


def require_enabled_anthropic_configuration(
    configuration: CalibrationRuntimeConfiguration,
) -> ResolvedAnthropicConfiguration:
    if type(configuration) is not CalibrationRuntimeConfiguration:
        fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
    if not configuration.live_provider_enabled:
        fail_execution(CalibrationErrorCode.PROVIDER_DISABLED)
    resolved = configuration.anthropic
    if resolved is None:
        fail_execution(CalibrationErrorCode.CONFIGURATION_INVALID)
    return resolved
