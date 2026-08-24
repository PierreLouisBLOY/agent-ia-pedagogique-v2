from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta

from backend.agent_runtime.contracts.common.actor import ActorRef
from backend.agent_runtime.contracts.common.safe_data import freeze_agent_safe_mapping
from backend.agent_runtime.contracts.common.schema_version import ContractSchemaVersion
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class ContractMeta[TStatus]:
    """Common immutable metadata for agent runtime contracts."""

    schema_version: ContractSchemaVersion
    run_id: str
    step_id: str
    parent_step_id: str | None
    correlation_id: CorrelationId
    created_at: Instant
    actor: ActorRef
    status: TStatus
    trace_flags: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, ContractSchemaVersion):
            raise TypeError("schema_version must be a ContractSchemaVersion")
        require_non_empty(self.run_id, "run_id")
        require_non_empty(self.step_id, "step_id")
        if self.parent_step_id is not None:
            require_non_empty(self.parent_step_id, "parent_step_id")
            if self.parent_step_id == self.step_id:
                raise ValueError("parent_step_id must not equal step_id")
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        if not isinstance(self.created_at, Instant):
            raise TypeError("created_at must be an Instant")
        if self.created_at.value.utcoffset() != timedelta(0):
            raise ValueError("created_at must be UTC")
        if not isinstance(self.actor, ActorRef):
            raise TypeError("actor must be an ActorRef")
        object.__setattr__(
            self,
            "trace_flags",
            freeze_agent_safe_mapping(self.trace_flags),
        )
