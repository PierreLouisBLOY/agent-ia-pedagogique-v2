from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.contracts import AgentId
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class CapabilityClass(StrEnum):
    READ = "READ"
    EVIDENCE = "EVIDENCE"
    GENERATE_TRANSFORM = "GENERATE_TRANSFORM"
    REVIEW = "REVIEW"
    APPLICATION_ACTION = "APPLICATION_ACTION"
    TECHNICAL_UTILITY = "TECHNICAL_UTILITY"
    ORCHESTRATION = "ORCHESTRATION"


class CapabilityRisk(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class CapabilityExecutionRoute(StrEnum):
    APPLICATION = "APPLICATION"
    AGENT = "AGENT"
    RUNTIME = "RUNTIME"
    UTILITY = "UTILITY"


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability_id: CapabilityId
    canonical_name: str
    capability_class: CapabilityClass
    risk: CapabilityRisk
    execution_route: CapabilityExecutionRoute
    owner_agent: AgentId | None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        require_non_empty(self.canonical_name, "canonical_name")
        if not isinstance(self.capability_class, CapabilityClass):
            raise TypeError("capability_class must be a CapabilityClass")
        if not isinstance(self.risk, CapabilityRisk):
            raise TypeError("risk must be a CapabilityRisk")
        if not isinstance(self.execution_route, CapabilityExecutionRoute):
            raise TypeError("execution_route must be a CapabilityExecutionRoute")
        if self.owner_agent is not None and not isinstance(self.owner_agent, AgentId):
            raise TypeError("owner_agent must be an AgentId or None")
        if self.execution_route is CapabilityExecutionRoute.AGENT:
            if self.owner_agent is None:
                raise ValueError("owner_agent is required for the AGENT route")
        elif self.owner_agent is not None:
            raise ValueError("owner_agent is forbidden outside the AGENT route")


class UnknownCapabilityError(LookupError):
    def __init__(self, capability_id: CapabilityId) -> None:
        self.capability_id = capability_id
        super().__init__(f"unknown capability: {capability_id.value}")


@dataclass(frozen=True, slots=True)
class CapabilityRegistry:
    _descriptors: tuple[CapabilityDescriptor, ...]

    def __init__(self, descriptors: Iterable[CapabilityDescriptor]) -> None:
        normalized = tuple(descriptors)
        if any(not isinstance(item, CapabilityDescriptor) for item in normalized):
            raise TypeError("descriptors must contain CapabilityDescriptor values")
        capability_ids = tuple(item.capability_id for item in normalized)
        canonical_names = tuple(item.canonical_name for item in normalized)
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("duplicate CapabilityId in registry")
        if len(set(canonical_names)) != len(canonical_names):
            raise ValueError("duplicate canonical_name in registry")
        object.__setattr__(self, "_descriptors", normalized)
        object.__setattr__(
            self,
            "_by_id",
            MappingProxyType({item.capability_id: item for item in normalized}),
        )

    _by_id: MappingProxyType[CapabilityId, CapabilityDescriptor]

    def get(self, capability_id: CapabilityId) -> CapabilityDescriptor:
        if not isinstance(capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        try:
            return self._by_id[capability_id]
        except KeyError as error:
            raise UnknownCapabilityError(capability_id) from error

    def contains(self, capability_id: CapabilityId) -> bool:
        if not isinstance(capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        return capability_id in self._by_id

    def all(self) -> tuple[CapabilityDescriptor, ...]:
        return self._descriptors

    def by_class(self, capability_class: CapabilityClass) -> tuple[CapabilityDescriptor, ...]:
        if not isinstance(capability_class, CapabilityClass):
            raise TypeError("capability_class must be a CapabilityClass")
        return tuple(
            item for item in self._descriptors if item.capability_class is capability_class
        )

    def owned_by(self, agent_id: AgentId) -> tuple[CapabilityDescriptor, ...]:
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        return tuple(
            item
            for item in self._descriptors
            if item.execution_route is CapabilityExecutionRoute.AGENT
            and item.owner_agent is agent_id
        )


def _descriptor(
    code: str,
    canonical_name: str,
    capability_class: CapabilityClass,
    risk: CapabilityRisk,
    route: CapabilityExecutionRoute,
    owner_agent: AgentId | None = None,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=CapabilityId(code),
        canonical_name=canonical_name,
        capability_class=capability_class,
        risk=risk,
        execution_route=route,
        owner_agent=owner_agent,
    )


BASELINE_CAPABILITY_REGISTRY: Final = CapabilityRegistry(
    (
        _descriptor(
            "CAP-R01",
            "read_canonical_resource",
            CapabilityClass.READ,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.APPLICATION,
        ),
        _descriptor(
            "CAP-R02",
            "read_production",
            CapabilityClass.READ,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.APPLICATION,
        ),
        _descriptor(
            "CAP-R03",
            "read_metadata_status",
            CapabilityClass.READ,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.APPLICATION,
        ),
        _descriptor(
            "CAP-E01",
            "search_evidence",
            CapabilityClass.EVIDENCE,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_02,
        ),
        _descriptor(
            "CAP-E02",
            "fetch_evidence_item",
            CapabilityClass.EVIDENCE,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_02,
        ),
        _descriptor(
            "CAP-E03",
            "assess_evidence_coverage",
            CapabilityClass.EVIDENCE,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_02,
        ),
        _descriptor(
            "CAP-G01",
            "generate_production",
            CapabilityClass.GENERATE_TRANSFORM,
            CapabilityRisk.R1,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_03,
        ),
        _descriptor(
            "CAP-G02",
            "transform_production",
            CapabilityClass.GENERATE_TRANSFORM,
            CapabilityRisk.R1,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_03,
        ),
        _descriptor(
            "CAP-G03",
            "correct_production",
            CapabilityClass.GENERATE_TRANSFORM,
            CapabilityRisk.R1,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_03,
        ),
        _descriptor(
            "CAP-V01",
            "semantic_review",
            CapabilityClass.REVIEW,
            CapabilityRisk.R1,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_04,
        ),
        _descriptor(
            "CAP-V02",
            "assess_findings",
            CapabilityClass.REVIEW,
            CapabilityRisk.R1,
            CapabilityExecutionRoute.AGENT,
            AgentId.AG_04,
        ),
        _descriptor(
            "CAP-A01",
            "run_deterministic_validation",
            CapabilityClass.APPLICATION_ACTION,
            CapabilityRisk.R3,
            CapabilityExecutionRoute.APPLICATION,
        ),
        _descriptor(
            "CAP-A02",
            "request_promotion",
            CapabilityClass.APPLICATION_ACTION,
            CapabilityRisk.R4,
            CapabilityExecutionRoute.APPLICATION,
        ),
        _descriptor(
            "CAP-A03",
            "export_artifact",
            CapabilityClass.APPLICATION_ACTION,
            CapabilityRisk.R3,
            CapabilityExecutionRoute.APPLICATION,
        ),
        _descriptor(
            "CAP-T01",
            "validate_schema",
            CapabilityClass.TECHNICAL_UTILITY,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.UTILITY,
        ),
        _descriptor(
            "CAP-T02",
            "render_document",
            CapabilityClass.TECHNICAL_UTILITY,
            CapabilityRisk.R2,
            CapabilityExecutionRoute.UTILITY,
        ),
        _descriptor(
            "CAP-T03",
            "convert_format",
            CapabilityClass.TECHNICAL_UTILITY,
            CapabilityRisk.R2,
            CapabilityExecutionRoute.UTILITY,
        ),
        _descriptor(
            "CAP-T04",
            "estimate_token_cost",
            CapabilityClass.TECHNICAL_UTILITY,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.UTILITY,
        ),
        _descriptor(
            "CAP-O01",
            "plan_workflow",
            CapabilityClass.ORCHESTRATION,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.RUNTIME,
        ),
        _descriptor(
            "CAP-O02",
            "route_capability",
            CapabilityClass.ORCHESTRATION,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.RUNTIME,
        ),
        _descriptor(
            "CAP-O03",
            "delegate_agent",
            CapabilityClass.ORCHESTRATION,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.RUNTIME,
        ),
        _descriptor(
            "CAP-O04",
            "join_results",
            CapabilityClass.ORCHESTRATION,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.RUNTIME,
        ),
        _descriptor(
            "CAP-O05",
            "request_gate",
            CapabilityClass.ORCHESTRATION,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.RUNTIME,
        ),
        _descriptor(
            "CAP-O06",
            "stop_or_replan",
            CapabilityClass.ORCHESTRATION,
            CapabilityRisk.R0,
            CapabilityExecutionRoute.RUNTIME,
        ),
    )
)
