from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.application_routing.model import UseCaseDescriptor
from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityClass,
    CapabilityExecutionRoute,
    CapabilityRegistry,
    UnknownCapabilityError,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class UnknownUseCaseError(LookupError):
    def __init__(self, use_case_id: str) -> None:
        require_non_empty(use_case_id, "use_case_id")
        self.use_case_id = use_case_id
        super().__init__("unknown use case")


@dataclass(frozen=True, slots=True)
class UseCaseRegistry:
    _descriptors: tuple[UseCaseDescriptor, ...]
    capability_registry: CapabilityRegistry
    _by_id: MappingProxyType[str, UseCaseDescriptor]

    def __init__(
        self,
        descriptors: Iterable[UseCaseDescriptor],
        capability_registry: CapabilityRegistry = BASELINE_CAPABILITY_REGISTRY,
    ) -> None:
        if not isinstance(capability_registry, CapabilityRegistry):
            raise TypeError("capability_registry must be a CapabilityRegistry")
        normalized = tuple(descriptors)
        if any(type(item) is not UseCaseDescriptor for item in normalized):
            raise TypeError("descriptors must contain UseCaseDescriptor values")
        use_case_ids = tuple(item.use_case_id for item in normalized)
        canonical_names = tuple(item.canonical_name for item in normalized)
        if len(set(use_case_ids)) != len(use_case_ids):
            raise ValueError("duplicate use_case_id in registry")
        if len(set(canonical_names)) != len(canonical_names):
            raise ValueError("duplicate canonical_name in registry")
        for descriptor in normalized:
            try:
                capability = capability_registry.get(descriptor.capability_id)
            except UnknownCapabilityError as error:
                raise ValueError("unknown capability in use-case registry") from error
            if (
                capability.execution_route is not CapabilityExecutionRoute.APPLICATION
                or capability.capability_class
                not in {CapabilityClass.READ, CapabilityClass.APPLICATION_ACTION}
                or capability.owner_agent is not None
            ):
                raise ValueError("use-case capability must be owned by Application")
        object.__setattr__(self, "_descriptors", normalized)
        object.__setattr__(self, "capability_registry", capability_registry)
        object.__setattr__(
            self,
            "_by_id",
            MappingProxyType({item.use_case_id: item for item in normalized}),
        )

    def get(self, use_case_id: str) -> UseCaseDescriptor:
        require_non_empty(use_case_id, "use_case_id")
        try:
            return self._by_id[use_case_id]
        except KeyError as error:
            raise UnknownUseCaseError(use_case_id) from error

    def contains(self, use_case_id: str) -> bool:
        require_non_empty(use_case_id, "use_case_id")
        return use_case_id in self._by_id

    def all(self) -> tuple[UseCaseDescriptor, ...]:
        return self._descriptors

    def by_capability(self, capability_id: CapabilityId) -> tuple[UseCaseDescriptor, ...]:
        if not isinstance(capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        return tuple(
            descriptor
            for descriptor in self._descriptors
            if descriptor.capability_id == capability_id
        )


def _descriptor(
    use_case_id: str,
    canonical_name: str,
    capability_id: str,
    *,
    idempotency_required: bool,
) -> UseCaseDescriptor:
    return UseCaseDescriptor(
        use_case_id=use_case_id,
        canonical_name=canonical_name,
        capability_id=CapabilityId(capability_id),
        request_contract_id="C-12",
        result_contract_id="C-13",
        idempotency_required=idempotency_required,
    )


BASELINE_USE_CASE_REGISTRY: Final = UseCaseRegistry(
    (
        _descriptor(
            "application.read_canonical_resource",
            "read_canonical_resource",
            "CAP-R01",
            idempotency_required=False,
        ),
        _descriptor(
            "application.read_production",
            "read_production",
            "CAP-R02",
            idempotency_required=False,
        ),
        _descriptor(
            "application.read_metadata_status",
            "read_metadata_status",
            "CAP-R03",
            idempotency_required=False,
        ),
        _descriptor(
            "application.run_deterministic_validation",
            "run_deterministic_validation",
            "CAP-A01",
            idempotency_required=False,
        ),
        _descriptor(
            "application.request_promotion",
            "request_promotion",
            "CAP-A02",
            idempotency_required=True,
        ),
        _descriptor(
            "application.export_artifact",
            "export_artifact",
            "CAP-A03",
            idempotency_required=True,
        ),
    )
)
