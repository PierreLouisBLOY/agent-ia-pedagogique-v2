from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ActorKind,
    AgentId,
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.errors import ErrorEnvelope
from backend.shared_kernel._strings import require_non_empty


class AgentResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class AgentResult[TPayload]:
    """Provider-neutral result contract for one agent invocation."""

    meta: ContractMeta[AgentResultStatus]
    invocation_id: str
    payload: TPayload | None = None
    artifact_refs: tuple[ContractRef, ...] = ()
    evidence_refs: tuple[ContractRef, ...] = ()
    warnings: tuple[Mapping[str, object], ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)
    error: ErrorEnvelope | None = None
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, AgentResultStatus):
            raise TypeError("meta.status must be an AgentResultStatus")
        if self.meta.actor.kind is not ActorKind.AGENT:
            raise ValueError("agent result producer must be an agent")
        try:
            AgentId(self.meta.actor.actor_id)
        except ValueError as error:
            raise ValueError("agent result producer must be a canonical agent") from error
        require_non_empty(self.invocation_id, "invocation_id")
        artifact_refs = tuple(self.artifact_refs)
        for artifact_ref in artifact_refs:
            require_contract_ref(artifact_ref, "artifact_ref")
        evidence_refs = tuple(self.evidence_refs)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
        warnings = tuple(freeze_agent_safe_mapping(warning) for warning in self.warnings)
        if self.error is not None and not isinstance(self.error, ErrorEnvelope):
            raise TypeError("error must be an ErrorEnvelope")
        if self.error is not None and self.error.step_id != self.meta.step_id:
            raise ValueError("error.step_id must match meta.step_id")
        if self.stop_reason is not None:
            require_non_empty(self.stop_reason, "stop_reason")
        if self.meta.status is AgentResultStatus.FAILED and (
            self.error is None and self.stop_reason is None
        ):
            raise ValueError("failed result requires error or stop_reason")
        if self.meta.status in {
            AgentResultStatus.CANCELLED,
            AgentResultStatus.ESCALATED,
        } and self.stop_reason is None:
            raise ValueError("cancelled or escalated result requires stop_reason")
        object.__setattr__(self, "artifact_refs", artifact_refs)
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "metrics", freeze_agent_safe_mapping(self.metrics))

    @property
    def producer_agent(self) -> AgentId:
        """Canonical producer derived from immutable contract metadata."""

        return AgentId(self.meta.actor.actor_id)
