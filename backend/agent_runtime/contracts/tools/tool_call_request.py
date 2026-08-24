from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts.common import ContractMeta, freeze_agent_safe_mapping
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.agent_runtime.contracts.policy import PermissionScope
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    """Controlled tool-call intent that conveys no execution authority by itself."""

    meta: ContractMeta[InvocationStatus]
    tool_id: str
    capability_id: CapabilityId
    arguments: Mapping[str, object]
    permission_scope: PermissionScope
    timeout: int | float | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        require_non_empty(self.tool_id, "tool_id")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(self.permission_scope, PermissionScope):
            raise TypeError("permission_scope must be a PermissionScope")
        if self.timeout is not None:
            if not isinstance(self.timeout, (int, float)) or isinstance(self.timeout, bool):
                raise TypeError("timeout must be a number")
            if self.timeout < 0:
                raise ValueError("timeout must be >= 0")
        if self.idempotency_key is not None:
            require_non_empty(self.idempotency_key, "idempotency_key")
        object.__setattr__(self, "arguments", freeze_agent_safe_mapping(self.arguments))
