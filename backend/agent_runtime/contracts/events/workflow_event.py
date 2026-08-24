from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.shared_kernel._strings import require_non_empty


class WorkflowEventType(StrEnum):
    PLANNED = "planned"
    ROUTED = "routed"
    DELEGATED = "delegated"
    TOOL_CALLED = "tool_called"
    USECASE_CALLED = "usecase_called"
    REVIEWED = "reviewed"
    CORRECTED = "corrected"
    GATED = "gated"
    STOPPED = "stopped"


class WorkflowStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_GATE = "waiting_gate"
    REPLANNING = "replanning"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """Immutable correlated event data with no logging backend behavior."""

    meta: ContractMeta[WorkflowStatus]
    event_id: str
    event_type: WorkflowEventType
    summary: str
    refs: tuple[ContractRef, ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, WorkflowStatus):
            raise TypeError("meta.status must be a WorkflowStatus")
        require_non_empty(self.event_id, "event_id")
        if not isinstance(self.event_type, WorkflowEventType):
            raise TypeError("event_type must be a WorkflowEventType")
        require_non_empty(self.summary, "summary")
        refs = tuple(self.refs)
        for ref in refs:
            require_contract_ref(ref, "ref")
        object.__setattr__(self, "refs", refs)
        object.__setattr__(self, "metrics", freeze_agent_safe_mapping(self.metrics))
