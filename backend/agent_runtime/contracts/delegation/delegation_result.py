from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts.common import AgentId
from backend.agent_runtime.contracts.invocation import AgentResult
from backend.agent_runtime.contracts.planning import DelegationEnvelope
from backend.shared_kernel._strings import require_non_empty

_DELEGABLE_AGENT_IDS = frozenset({AgentId.AG_02, AgentId.AG_03, AgentId.AG_04})


@dataclass(frozen=True, slots=True)
class DelegationResult[TPayload]:
    """Correlate an AgentResult with the delegation that produced it."""

    delegation_id: str
    source_agent: AgentId
    agent_result: AgentResult[TPayload]
    delegation: DelegationEnvelope | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.delegation_id, "delegation_id")
        if self.source_agent not in _DELEGABLE_AGENT_IDS:
            raise ValueError("source_agent must be AG-02, AG-03, or AG-04")
        if not isinstance(self.agent_result, AgentResult):
            raise TypeError("agent_result must be an AgentResult")
        if self.agent_result.producer_agent is not self.source_agent:
            raise ValueError("agent_result producer must match source_agent")
        if self.delegation is not None:
            if not isinstance(self.delegation, DelegationEnvelope):
                raise TypeError("delegation must be a DelegationEnvelope")
            if self.delegation.delegation_id != self.delegation_id:
                raise ValueError("delegation.delegation_id must match delegation_id")
            if self.delegation.target_agent is not self.source_agent:
                raise ValueError("source_agent must match delegation.target_agent")
            if self.agent_result.meta.step_id != self.delegation.source_step.step_id:
                raise ValueError("agent_result step must match delegation source step")

    @property
    def is_delegated(self) -> bool:
        """Distinguish a correlated delegated result from a legitimate direct result."""

        return self.delegation is not None
