from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ActorKind,
    AgentId,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.planning.step_spec import StepKind, StepSpec
from backend.agent_runtime.contracts.policy import PermissionScope
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant

_DELEGABLE_AGENT_IDS = frozenset({AgentId.AG_02, AgentId.AG_03, AgentId.AG_04})


@dataclass(frozen=True, slots=True)
class DelegationEnvelope:
    """Specialized delegation data derived from a source agent StepSpec."""

    delegation_id: str
    source_step: StepSpec
    target_agent: AgentId
    context_slice: Mapping[str, object]
    evidence_refs: tuple[ContractRef, ...]
    constraints: Mapping[str, object]
    permission_scope: PermissionScope
    deadline: Instant | None = None
    trace_context: Mapping[str, object] = field(default_factory=dict)
    source_agent: AgentId = AgentId.AG_01
    delegation_depth: int = 1

    def __post_init__(self) -> None:
        require_non_empty(self.delegation_id, "delegation_id")
        if not isinstance(self.source_step, StepSpec):
            raise TypeError("source_step must be a StepSpec")
        if self.target_agent not in _DELEGABLE_AGENT_IDS:
            raise ValueError("target_agent must be AG-02, AG-03, or AG-04")
        if self.source_step.kind is not StepKind.AGENT:
            raise ValueError("source_step.kind must be agent")
        if self.source_step.executor.agent_id is not self.target_agent:
            raise ValueError("source_step.executor must match target_agent")
        if self.source_step.capability_id is None:
            raise ValueError("source_step.capability_id is required")
        if self.source_agent is not AgentId.AG_01:
            raise ValueError("source_agent must be AG-01")
        if type(self.delegation_depth) is not int:
            raise TypeError("delegation_depth must be an integer")
        if self.delegation_depth != 1:
            raise ValueError("specialist delegation depth must be exactly 1")
        evidence_refs = tuple(self.evidence_refs)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
        if not isinstance(self.permission_scope, PermissionScope):
            raise TypeError("permission_scope must be a PermissionScope")
        if self.permission_scope.principal.kind is not ActorKind.AGENT:
            raise ValueError("permission_scope.principal must be an agent")
        if self.permission_scope.principal.actor_id != self.target_agent.value:
            raise ValueError("permission_scope.principal must match target_agent")
        if self.permission_scope.capability_ids != (self.source_step.capability_id,):
            raise ValueError("permission_scope must contain exactly the delegated capability")
        if self.permission_scope.delegable:
            raise ValueError("delegated permission_scope must not be redelegable")
        if self.deadline is not None and not isinstance(self.deadline, Instant):
            raise TypeError("deadline must be an Instant")
        object.__setattr__(
            self,
            "context_slice",
            freeze_agent_safe_mapping(self.context_slice),
        )
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "constraints", freeze_agent_safe_mapping(self.constraints))
        object.__setattr__(
            self,
            "trace_context",
            freeze_agent_safe_mapping(self.trace_context),
        )
