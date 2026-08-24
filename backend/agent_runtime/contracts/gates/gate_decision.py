from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.gates.gate_request import GateRequest, GateStatus
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class GateDecisionValue(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


_DECISION_STATUSES = {
    GateDecisionValue.APPROVED: GateStatus.APPROVED,
    GateDecisionValue.REJECTED: GateStatus.REJECTED,
    GateDecisionValue.DEFERRED: GateStatus.DEFERRED,
}


@dataclass(frozen=True, slots=True)
class GateDecision:
    """Recorded external decision; this contract never decides a gate."""

    meta: ContractMeta[GateStatus]
    gate_id: str
    decision: GateDecisionValue
    actor: ActorRef
    decided_at: Instant
    decision_ref: ContractRef
    request: GateRequest
    selected_option: Mapping[str, object] | None = None
    comment: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        require_non_empty(self.gate_id, "gate_id")
        if not isinstance(self.request, GateRequest):
            raise TypeError("request must be a GateRequest")
        if self.request.gate_id != self.gate_id:
            raise ValueError("request.gate_id must match gate_id")
        if not isinstance(self.decision, GateDecisionValue):
            raise TypeError("decision must be a GateDecisionValue")
        if self.meta.status is not _DECISION_STATUSES[self.decision]:
            raise ValueError("meta.status must match decision")
        if not isinstance(self.actor, ActorRef):
            raise TypeError("actor must be an ActorRef")
        if self.actor != self.request.required_actor:
            raise ValueError("actor must match request.required_actor")
        if self.meta.actor != self.actor:
            raise ValueError("meta.actor must match actor")
        if self.meta.correlation_id != self.request.meta.correlation_id:
            raise ValueError("meta correlation must match request correlation")
        if self.meta.step_id != self.request.meta.step_id:
            raise ValueError("meta step must match request step")
        if self.actor.kind is ActorKind.AGENT and self.actor.actor_id == AgentId.AG_01.value:
            raise ValueError("AG-01 cannot author a GateDecision")
        if not isinstance(self.decided_at, Instant):
            raise TypeError("decided_at must be an Instant")
        if self.decided_at.value.utcoffset() != timedelta(0):
            raise ValueError("decided_at must be UTC")
        if self.decided_at.value < self.request.meta.created_at.value:
            raise ValueError("decided_at must not precede request creation")
        if (
            self.request.expires_at is not None
            and self.decided_at.value > self.request.expires_at.value
        ):
            raise ValueError("decided_at must not exceed request expiration")
        require_contract_ref(self.decision_ref, "decision_ref")
        if self.selected_option is not None:
            selected_option = freeze_agent_safe_mapping(self.selected_option)
            if self.request.options and not any(
                selected_option == option for option in self.request.options
            ):
                raise ValueError("selected_option must match one request option")
            object.__setattr__(
                self,
                "selected_option",
                selected_option,
            )
        if self.comment is not None:
            require_non_empty(self.comment, "comment")
