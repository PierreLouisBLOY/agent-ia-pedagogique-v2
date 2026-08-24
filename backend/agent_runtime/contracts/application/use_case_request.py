from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.core_contracts.invocation import UseCaseContext
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class UseCaseRequest:
    """Intent to call an Application inbound port; no handler is invoked here."""

    meta: ContractMeta[InvocationStatus]
    use_case_id: str
    payload: Mapping[str, object]
    actor_context: UseCaseContext
    precondition_refs: tuple[ContractRef, ...] = ()
    idempotency_key: str | None = None
    requested_effect: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        require_non_empty(self.use_case_id, "use_case_id")
        if not isinstance(self.actor_context, UseCaseContext):
            raise TypeError("actor_context must be a UseCaseContext")
        if self.actor_context.correlation_id != self.meta.correlation_id:
            raise ValueError("actor_context correlation must match meta correlation")
        if self.actor_context.context_snapshot is not None:
            freeze_agent_safe_mapping(self.actor_context.context_snapshot)
        precondition_refs = tuple(self.precondition_refs)
        for precondition_ref in precondition_refs:
            require_contract_ref(precondition_ref, "precondition_ref")
        if self.idempotency_key is not None:
            require_non_empty(self.idempotency_key, "idempotency_key")
        object.__setattr__(self, "payload", freeze_agent_safe_mapping(self.payload))
        object.__setattr__(self, "precondition_refs", precondition_refs)
        object.__setattr__(
            self, "requested_effect", freeze_agent_safe_mapping(self.requested_effect)
        )
