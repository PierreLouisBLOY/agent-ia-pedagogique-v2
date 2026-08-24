from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.contracts import AgentId
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class AgentRole(StrEnum):
    ORCHESTRATOR = "ORCHESTRATOR"
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    GENERATOR_TRANSFORMER = "GENERATOR_TRANSFORMER"
    REVIEWER_CRITIC = "REVIEWER_CRITIC"


@dataclass(frozen=True, slots=True)
class AgentDescriptor:
    agent_id: AgentId
    canonical_name: str
    role: AgentRole
    mission: str
    primary_capability_ids: tuple[CapabilityId, ...]
    is_orchestrator: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        require_non_empty(self.canonical_name, "canonical_name")
        if not isinstance(self.role, AgentRole):
            raise TypeError("role must be an AgentRole")
        require_non_empty(self.mission, "mission")
        capability_ids = tuple(self.primary_capability_ids)
        if any(not isinstance(item, CapabilityId) for item in capability_ids):
            raise TypeError("primary_capability_ids must contain CapabilityId values")
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("primary_capability_ids must be unique")
        if not isinstance(self.is_orchestrator, bool):
            raise TypeError("is_orchestrator must be a bool")
        if self.is_orchestrator is not (self.agent_id is AgentId.AG_01):
            raise ValueError("AG-01 must be the only orchestrator")
        object.__setattr__(self, "primary_capability_ids", capability_ids)


class UnknownAgentError(LookupError):
    def __init__(self, agent_id: AgentId) -> None:
        self.agent_id = agent_id
        super().__init__(f"unknown agent: {agent_id.value}")


@dataclass(frozen=True, slots=True)
class AgentRegistry:
    _descriptors: tuple[AgentDescriptor, ...]

    def __init__(self, descriptors: Iterable[AgentDescriptor]) -> None:
        normalized = tuple(descriptors)
        if any(not isinstance(item, AgentDescriptor) for item in normalized):
            raise TypeError("descriptors must contain AgentDescriptor values")
        agent_ids = tuple(item.agent_id for item in normalized)
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("duplicate AgentId in registry")
        for descriptor in normalized:
            expected = descriptor.agent_id is AgentId.AG_01
            if descriptor.is_orchestrator is not expected:
                raise ValueError("AG-01 must be the only orchestrator")
        object.__setattr__(self, "_descriptors", normalized)
        object.__setattr__(
            self,
            "_by_id",
            MappingProxyType({item.agent_id: item for item in normalized}),
        )

    _by_id: MappingProxyType[AgentId, AgentDescriptor]

    def get(self, agent_id: AgentId) -> AgentDescriptor:
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        try:
            return self._by_id[agent_id]
        except KeyError as error:
            raise UnknownAgentError(agent_id) from error

    def contains(self, agent_id: AgentId) -> bool:
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        return agent_id in self._by_id

    def all(self) -> tuple[AgentDescriptor, ...]:
        return self._descriptors


def _capability_ids(prefix: str, count: int) -> tuple[CapabilityId, ...]:
    return tuple(CapabilityId(f"CAP-{prefix}{index:02d}") for index in range(1, count + 1))


BASELINE_AGENT_REGISTRY: Final = AgentRegistry(
    (
        AgentDescriptor(
            agent_id=AgentId.AG_01,
            canonical_name="AG-01 — Orchestrateur",
            role=AgentRole.ORCHESTRATOR,
            mission=(
                "Intention, plan, routing, délégation, joins, supervision runtime, "
                "replanification, stop et escalade."
            ),
            primary_capability_ids=_capability_ids("O", 6),
            is_orchestrator=True,
        ),
        AgentDescriptor(
            agent_id=AgentId.AG_02,
            canonical_name="AG-02 — Evidence/Retrieval",
            role=AgentRole.EVIDENCE_RETRIEVAL,
            mission=(
                "Recherche, sélection, provenance, couverture, staleness et conflits documentaires."
            ),
            primary_capability_ids=_capability_ids("E", 3),
        ),
        AgentDescriptor(
            agent_id=AgentId.AG_03,
            canonical_name="AG-03 — Generator/Transformer",
            role=AgentRole.GENERATOR_TRANSFORMER,
            mission=(
                "Conception, transformation et correction versionnée de Production candidates."
            ),
            primary_capability_ids=_capability_ids("G", 3),
        ),
        AgentDescriptor(
            agent_id=AgentId.AG_04,
            canonical_name="AG-04 — Reviewer/Critic sémantique",
            role=AgentRole.REVIEWER_CRITIC,
            mission="Review indépendante et findings structurés.",
            primary_capability_ids=_capability_ids("V", 2),
        ),
    )
)
