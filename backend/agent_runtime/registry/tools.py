from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.registry.capabilities import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityClass,
    CapabilityExecutionRoute,
    CapabilityRegistry,
    UnknownCapabilityError,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class ToolEffectClass(StrEnum):
    """Anticipated effect class; distinct from post-execution EffectState."""

    READ_ONLY = "READ_ONLY"
    PURE_COMPUTE = "PURE_COMPUTE"
    LOCAL_FILE_TRANSFORM = "LOCAL_FILE_TRANSFORM"
    EXTERNAL_MUTATION = "EXTERNAL_MUTATION"


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """Static tool metadata with no handler, credential, or execution authority."""

    tool_id: str
    canonical_name: str
    capability_id: CapabilityId
    input_contract_id: str
    output_contract_id: str
    effect_class: ToolEffectClass
    sandbox_profile_id: str | None
    idempotency_required: bool
    timeout_ceiling: int | float | None

    def __post_init__(self) -> None:
        require_non_empty(self.tool_id, "tool_id")
        require_non_empty(self.canonical_name, "canonical_name")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        require_non_empty(self.input_contract_id, "input_contract_id")
        require_non_empty(self.output_contract_id, "output_contract_id")
        if not isinstance(self.effect_class, ToolEffectClass):
            raise TypeError("effect_class must be a ToolEffectClass")
        if self.sandbox_profile_id is not None:
            require_non_empty(self.sandbox_profile_id, "sandbox_profile_id")
        if not isinstance(self.idempotency_required, bool):
            raise TypeError("idempotency_required must be a bool")
        if self.timeout_ceiling is not None:
            if not isinstance(self.timeout_ceiling, (int, float)) or isinstance(
                self.timeout_ceiling, bool
            ):
                raise TypeError("timeout_ceiling must be a number")
            if self.timeout_ceiling < 0:
                raise ValueError("timeout_ceiling must be >= 0")
            if isinstance(self.timeout_ceiling, float) and not isfinite(
                self.timeout_ceiling
            ):
                raise ValueError("timeout_ceiling must be finite")

        if self.effect_class in {
            ToolEffectClass.READ_ONLY,
            ToolEffectClass.PURE_COMPUTE,
        } and self.sandbox_profile_id is not None:
            raise ValueError("read-only and pure-compute tools must not declare a sandbox")
        if self.effect_class is ToolEffectClass.LOCAL_FILE_TRANSFORM:
            if self.sandbox_profile_id is None:
                raise ValueError("local file transforms require a sandbox_profile_id")
            if not self.idempotency_required:
                raise ValueError("local file transforms require idempotency")
        if (
            self.effect_class is ToolEffectClass.EXTERNAL_MUTATION
            and not self.idempotency_required
        ):
            raise ValueError("external mutations require idempotency")


class UnknownToolError(LookupError):
    def __init__(self, tool_id: str) -> None:
        require_non_empty(tool_id, "tool_id")
        self.tool_id = tool_id
        super().__init__(f"unknown tool: {tool_id}")


class ToolRegistryConfigurationError(ValueError):
    """Raised when static tool metadata conflicts with canonical capabilities."""


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    _descriptors: tuple[ToolDescriptor, ...]
    capability_registry: CapabilityRegistry
    _by_id: MappingProxyType[str, ToolDescriptor]

    def __init__(
        self,
        descriptors: Iterable[ToolDescriptor],
        *,
        capability_registry: CapabilityRegistry = BASELINE_CAPABILITY_REGISTRY,
    ) -> None:
        normalized = tuple(descriptors)
        if any(not isinstance(item, ToolDescriptor) for item in normalized):
            raise TypeError("descriptors must contain ToolDescriptor values")
        if not isinstance(capability_registry, CapabilityRegistry):
            raise TypeError("capability_registry must be a CapabilityRegistry")

        tool_ids = tuple(item.tool_id for item in normalized)
        canonical_names = tuple(item.canonical_name for item in normalized)
        if len(set(tool_ids)) != len(tool_ids):
            raise ToolRegistryConfigurationError("duplicate tool_id in registry")
        if len(set(canonical_names)) != len(canonical_names):
            raise ToolRegistryConfigurationError("duplicate canonical_name in registry")

        for descriptor in normalized:
            try:
                capability = capability_registry.get(descriptor.capability_id)
            except UnknownCapabilityError as error:
                raise ToolRegistryConfigurationError(
                    f"unknown capability for tool {descriptor.tool_id}"
                ) from error
            if capability.capability_class is not CapabilityClass.TECHNICAL_UTILITY:
                raise ToolRegistryConfigurationError(
                    f"tool {descriptor.tool_id} capability must be TECHNICAL_UTILITY"
                )
            if capability.execution_route is not CapabilityExecutionRoute.UTILITY:
                raise ToolRegistryConfigurationError(
                    f"tool {descriptor.tool_id} capability must use UTILITY route"
                )
            if capability.owner_agent is not None:
                raise ToolRegistryConfigurationError(
                    f"tool {descriptor.tool_id} capability must not have an agent owner"
                )

        object.__setattr__(self, "_descriptors", normalized)
        object.__setattr__(self, "capability_registry", capability_registry)
        object.__setattr__(
            self,
            "_by_id",
            MappingProxyType({item.tool_id: item for item in normalized}),
        )

    def get(self, tool_id: str) -> ToolDescriptor:
        require_non_empty(tool_id, "tool_id")
        try:
            return self._by_id[tool_id]
        except KeyError as error:
            raise UnknownToolError(tool_id) from error

    def contains(self, tool_id: str) -> bool:
        require_non_empty(tool_id, "tool_id")
        return tool_id in self._by_id

    def all(self) -> tuple[ToolDescriptor, ...]:
        return self._descriptors

    def by_capability(self, capability_id: CapabilityId) -> tuple[ToolDescriptor, ...]:
        if not isinstance(capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        return tuple(
            descriptor
            for descriptor in self._descriptors
            if descriptor.capability_id == capability_id
        )


_LOCAL_FILE_SANDBOX_PROFILE: Final[str] = "sandbox.local_file_transform.v1"


BASELINE_TOOL_REGISTRY: Final = ToolRegistry(
    (
        ToolDescriptor(
            tool_id="tool.render_document",
            canonical_name="render_document",
            capability_id=CapabilityId("CAP-T02"),
            input_contract_id="tool.render_document.input.v1",
            output_contract_id="tool.render_document.output.v1",
            effect_class=ToolEffectClass.LOCAL_FILE_TRANSFORM,
            sandbox_profile_id=_LOCAL_FILE_SANDBOX_PROFILE,
            idempotency_required=True,
            timeout_ceiling=120,
        ),
        ToolDescriptor(
            tool_id="tool.convert_format",
            canonical_name="convert_format",
            capability_id=CapabilityId("CAP-T03"),
            input_contract_id="tool.convert_format.input.v1",
            output_contract_id="tool.convert_format.output.v1",
            effect_class=ToolEffectClass.LOCAL_FILE_TRANSFORM,
            sandbox_profile_id=_LOCAL_FILE_SANDBOX_PROFILE,
            idempotency_required=True,
            timeout_ceiling=120,
        ),
    )
)
