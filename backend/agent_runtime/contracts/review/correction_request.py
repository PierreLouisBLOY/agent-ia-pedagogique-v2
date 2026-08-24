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
from backend.shared_kernel.references import ObjectVersionRef


@dataclass(frozen=True, slots=True)
class CorrectionRequest:
    """Version-oriented request for a new transformation of a production."""

    meta: ContractMeta[InvocationStatus]
    target_production_ref: ObjectVersionRef
    review_ref: ContractRef
    finding_ids: tuple[str, ...] = ()
    evidence_refs: tuple[ContractRef, ...] = ()
    preserve_constraints: Mapping[str, object] = field(default_factory=dict)
    allowed_changes: Mapping[str, object] = field(default_factory=dict)
    forbidden_changes: Mapping[str, object] = field(default_factory=dict)
    expected_delta: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        if not isinstance(self.target_production_ref, ObjectVersionRef):
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        require_contract_ref(self.review_ref, "review_ref")
        finding_ids = tuple(self.finding_ids)
        if not finding_ids:
            raise ValueError("finding_ids must not be empty")
        for finding_id in finding_ids:
            require_non_empty(finding_id, "finding_id")
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding_ids must be unique")
        evidence_refs = tuple(self.evidence_refs)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
        object.__setattr__(self, "finding_ids", finding_ids)
        object.__setattr__(self, "evidence_refs", evidence_refs)
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
