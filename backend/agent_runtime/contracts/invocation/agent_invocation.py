from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts.common import AgentId, ContractMeta
from backend.agent_runtime.contracts.planning import DelegationEnvelope, StepKind, StepSpec
from backend.agent_runtime.contracts.policy import AutonomyLevel, RuntimeMode
from backend.shared_kernel._strings import require_non_empty


class InvocationStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class AgentInvocation:
    """Concrete runtime attempt that composes StepSpec and DelegationEnvelope."""

    meta: ContractMeta[InvocationStatus]
    invocation_id: str
    source_step: StepSpec
    delegation: DelegationEnvelope | None
    agent_id: AgentId
    attempt: int
    autonomy_level: AutonomyLevel
    runtime_mode: RuntimeMode

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        require_non_empty(self.invocation_id, "invocation_id")
        if not isinstance(self.source_step, StepSpec):
            raise TypeError("source_step must be a StepSpec")
        if self.delegation is not None:
            if not isinstance(self.delegation, DelegationEnvelope):
                raise TypeError("delegation must be a DelegationEnvelope")
            if self.delegation.target_agent is not self.agent_id:
                raise ValueError("agent_id must match delegation.target_agent")
            if self.delegation.source_step != self.source_step:
                raise ValueError("delegation.source_step must match source_step")
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(self.attempt, int) or isinstance(self.attempt, bool):
            raise TypeError("attempt must be an integer")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if not isinstance(self.autonomy_level, AutonomyLevel):
            raise TypeError("autonomy_level must be an AutonomyLevel")
        if not isinstance(self.runtime_mode, RuntimeMode):
            raise TypeError("runtime_mode must be a RuntimeMode")
        if self.source_step.kind is StepKind.AGENT and self.source_step.executor.agent_id is not None:
            if self.source_step.executor.agent_id is not self.agent_id:
                raise ValueError("agent_id must match source_step.executor")
