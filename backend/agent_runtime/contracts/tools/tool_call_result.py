from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.errors import ErrorEnvelope
from backend.agent_runtime.contracts.invocation import AgentResultStatus
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    """Data-only tool result whose output is not evidence by default."""

    meta: ContractMeta[AgentResultStatus]
    tool_id: str
    output: Mapping[str, object] | None = None
    artifacts: tuple[ContractRef, ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)
    error: ErrorEnvelope | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, AgentResultStatus):
            raise TypeError("meta.status must be an AgentResultStatus")
        require_non_empty(self.tool_id, "tool_id")
        if self.output is not None:
            object.__setattr__(self, "output", freeze_agent_safe_mapping(self.output))
        artifacts = tuple(self.artifacts)
        for artifact in artifacts:
            require_contract_ref(artifact, "artifact")
        if self.error is not None:
            if not isinstance(self.error, ErrorEnvelope):
                raise TypeError("error must be an ErrorEnvelope")
            if self.error.step_id != self.meta.step_id:
                raise ValueError("error.step_id must match meta.step_id")
        if self.meta.status is AgentResultStatus.FAILED and self.error is None:
            raise ValueError("failed tool result requires an error")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "metrics", freeze_agent_safe_mapping(self.metrics))
