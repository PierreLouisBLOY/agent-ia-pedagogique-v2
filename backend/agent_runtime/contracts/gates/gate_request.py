from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ActorRef,
    ContractMeta,
    freeze_agent_safe_mapping,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class GateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class GateRequest:
    """Pending request for a decision by an external authority."""

    meta: ContractMeta[GateStatus]
    gate_id: str
    gate_type: str
    reason: str
    options: tuple[Mapping[str, object], ...]
    required_actor: ActorRef
    context_summary: Mapping[str, object] = field(default_factory=dict)
    expires_at: Instant | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if self.meta.status is not GateStatus.PENDING:
            raise ValueError("GateRequest meta.status must be pending")
        require_non_empty(self.gate_id, "gate_id")
        require_non_empty(self.gate_type, "gate_type")
        require_non_empty(self.reason, "reason")
        if not isinstance(self.required_actor, ActorRef):
            raise TypeError("required_actor must be an ActorRef")
        if self.expires_at is not None and not isinstance(self.expires_at, Instant):
            raise TypeError("expires_at must be an Instant")
        options = tuple(freeze_agent_safe_mapping(option) for option in self.options)
        object.__setattr__(self, "options", options)
        object.__setattr__(
            self, "context_summary", freeze_agent_safe_mapping(self.context_summary)
        )
