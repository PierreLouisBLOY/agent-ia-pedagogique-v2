from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    AGENT_SAFE_DATA_LIMITS,
    ActorKind,
    AgentId,
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_agent_safe_ref,
    require_agent_safe_text,
    require_agent_safe_value,
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
        if self.payload is not None:
            require_agent_safe_value(
                self.payload,
                root_location="agent_result.payload",
            )
        artifact_refs = tuple(self.artifact_refs)
        if len(artifact_refs) > 64:
            raise ValueError("artifact_refs must contain at most 64 items")
        for artifact_ref in artifact_refs:
            require_contract_ref(artifact_ref, "artifact_ref")
            require_agent_safe_ref(artifact_ref, field_name="artifact_ref")
        evidence_refs = tuple(self.evidence_refs)
        if len(evidence_refs) > 64:
            raise ValueError("evidence_refs must contain at most 64 items")
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
            require_agent_safe_ref(evidence_ref, field_name="evidence_ref")
        if len(self.warnings) > 64:
            raise ValueError("warnings must contain at most 64 items")
        warnings = tuple(freeze_agent_safe_mapping(warning) for warning in self.warnings)
        if self.error is not None and not isinstance(self.error, ErrorEnvelope):
            raise TypeError("error must be an ErrorEnvelope")
        if self.error is not None and self.error.step_id != self.meta.step_id:
            raise ValueError("error.step_id must match meta.step_id")
        if self.stop_reason is not None:
            require_non_empty(self.stop_reason, "stop_reason")
            require_agent_safe_text(
                self.stop_reason,
                field_name="stop_reason",
                max_length=1_024,
            )
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
        object.__setattr__(
            self,
            "metrics",
            freeze_agent_safe_mapping(self.metrics, limits=AGENT_SAFE_DATA_LIMITS),
        )

    @property
    def producer_agent(self) -> AgentId:
        """Canonical producer derived from immutable contract metadata."""

        return AgentId(self.meta.actor.actor_id)
