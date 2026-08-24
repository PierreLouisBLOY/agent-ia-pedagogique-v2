from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.review.vocabulary import (
    FindingSeverity,
    ReviewDimension,
)
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class Finding:
    """Public, concise review finding with no private reasoning payload."""

    finding_id: str
    dimension: ReviewDimension
    severity: FindingSeverity
    description: str
    target_locator: Mapping[str, object]
    rationale: str
    correction_required: bool
    evidence_refs: tuple[ContractRef, ...] = ()
    confidence: Mapping[str, object] = field(default_factory=dict)
    suggested_action: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.finding_id, "finding_id")
        if not isinstance(self.dimension, ReviewDimension):
            raise TypeError("dimension must be a ReviewDimension")
        if not isinstance(self.severity, FindingSeverity):
            raise TypeError("severity must be a FindingSeverity")
        require_non_empty(self.description, "description")
        require_non_empty(self.rationale, "rationale")
        if not isinstance(self.correction_required, bool):
            raise TypeError("correction_required must be a bool")
        evidence_refs = tuple(self.evidence_refs)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
        object.__setattr__(
            self, "target_locator", freeze_agent_safe_mapping(self.target_locator)
        )
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "confidence", freeze_agent_safe_mapping(self.confidence))
        object.__setattr__(
            self,
            "suggested_action",
            freeze_agent_safe_mapping(self.suggested_action),
        )
