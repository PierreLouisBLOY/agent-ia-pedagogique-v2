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
from backend.agent_runtime.contracts.review.finding import Finding
from backend.shared_kernel._strings import require_non_empty


class ReviewStatus(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Independent assessment; it is neither validation nor promotion."""

    meta: ContractMeta[ReviewStatus]
    review_id: str
    target_production_ref: ContractRef
    findings: tuple[Finding, ...]
    overall_assessment: Mapping[str, object]
    correction_required: bool
    confidence: Mapping[str, object] = field(default_factory=dict)
    limitations: tuple[Mapping[str, object], ...] = ()
    warnings: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, ReviewStatus):
            raise TypeError("meta.status must be a ReviewStatus")
        require_non_empty(self.review_id, "review_id")
        require_contract_ref(self.target_production_ref, "target_production_ref")
        findings = tuple(self.findings)
        if any(not isinstance(item, Finding) for item in findings):
            raise TypeError("findings must contain Finding values")
        finding_ids = [item.finding_id for item in findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("findings must have unique finding_id values")
        if not isinstance(self.correction_required, bool):
            raise TypeError("correction_required must be a bool")
        limitations = tuple(freeze_agent_safe_mapping(item) for item in self.limitations)
        warnings = tuple(freeze_agent_safe_mapping(item) for item in self.warnings)
        object.__setattr__(self, "findings", findings)
        object.__setattr__(
            self,
            "overall_assessment",
            freeze_agent_safe_mapping(self.overall_assessment),
        )
        object.__setattr__(self, "confidence", freeze_agent_safe_mapping(self.confidence))
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "warnings", warnings)
