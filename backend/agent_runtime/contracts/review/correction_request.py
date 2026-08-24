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
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class CorrectionRequest:
    """Version-oriented request for a new transformation of a production."""

    meta: ContractMeta[InvocationStatus]
    target_production_ref: ContractRef
    review_ref: ContractRef
    finding_ids: tuple[str, ...] = ()
    preserve_constraints: Mapping[str, object] = field(default_factory=dict)
    allowed_changes: Mapping[str, object] = field(default_factory=dict)
    forbidden_changes: Mapping[str, object] = field(default_factory=dict)
    expected_delta: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        require_contract_ref(self.target_production_ref, "target_production_ref")
        require_contract_ref(self.review_ref, "review_ref")
        finding_ids = tuple(self.finding_ids)
        for finding_id in finding_ids:
            require_non_empty(finding_id, "finding_id")
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding_ids must be unique")
        object.__setattr__(self, "finding_ids", finding_ids)
        object.__setattr__(
            self,
            "preserve_constraints",
            freeze_agent_safe_mapping(self.preserve_constraints),
        )
        object.__setattr__(
            self, "allowed_changes", freeze_agent_safe_mapping(self.allowed_changes)
        )
        object.__setattr__(
            self, "forbidden_changes", freeze_agent_safe_mapping(self.forbidden_changes)
        )
        object.__setattr__(
            self, "expected_delta", freeze_agent_safe_mapping(self.expected_delta)
        )
