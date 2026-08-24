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
from backend.agent_runtime.contracts.review.vocabulary import (
    OverallAssessment,
    ReviewDimension,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef


class ReviewStatus(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Independent assessment; it is neither validation nor promotion."""

    meta: ContractMeta[ReviewStatus]
    review_id: str
    target_production_ref: ObjectVersionRef
    findings: tuple[Finding, ...]
    overall_assessment: OverallAssessment
    correction_required: bool
    coverage: tuple[ReviewDimension, ...]
    evidence_refs_used: tuple[ContractRef, ...]
    confidence: Mapping[str, object] = field(default_factory=dict)
    limitations: tuple[Mapping[str, object], ...] = ()
    warnings: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, ReviewStatus):
            raise TypeError("meta.status must be a ReviewStatus")
        require_non_empty(self.review_id, "review_id")
        if not isinstance(self.target_production_ref, ObjectVersionRef):
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        findings = tuple(self.findings)
        if any(not isinstance(item, Finding) for item in findings):
            raise TypeError("findings must contain Finding values")
        finding_ids = [item.finding_id for item in findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("findings must have unique finding_id values")
        if not isinstance(self.overall_assessment, OverallAssessment):
            raise TypeError("overall_assessment must be an OverallAssessment")
        if not isinstance(self.correction_required, bool):
            raise TypeError("correction_required must be a bool")
        coverage = tuple(self.coverage)
        if any(not isinstance(item, ReviewDimension) for item in coverage):
            raise TypeError("coverage must contain ReviewDimension values")
        if len(coverage) != len(set(coverage)):
            raise ValueError("coverage must contain unique dimensions")
        if self.meta.status is ReviewStatus.COMPLETED and not coverage:
            raise ValueError("completed review requires non-empty coverage")
        if any(finding.dimension not in coverage for finding in findings):
            raise ValueError("every finding dimension must be included in coverage")
        finding_requires_correction = any(
            finding.correction_required for finding in findings
        )
        if finding_requires_correction and not self.correction_required:
            raise ValueError("finding correction requirement must be reflected by result")
        if (
            self.overall_assessment is OverallAssessment.CORRECTION_REQUIRED
            and not self.correction_required
        ):
            raise ValueError("correction_required assessment requires correction")
        if self.overall_assessment is OverallAssessment.ACCEPTABLE and (
            self.correction_required or finding_requires_correction
        ):
            raise ValueError("acceptable assessment cannot require correction")
        if (
            self.meta.status is ReviewStatus.INCOMPLETE
            and self.overall_assessment is OverallAssessment.ACCEPTABLE
        ):
            raise ValueError("incomplete review cannot be assessed as acceptable")
        evidence_refs_used = tuple(self.evidence_refs_used)
        for evidence_ref in evidence_refs_used:
            require_contract_ref(evidence_ref, "evidence_ref_used")
        limitations = tuple(freeze_agent_safe_mapping(item) for item in self.limitations)
        warnings = tuple(freeze_agent_safe_mapping(item) for item in self.warnings)
        object.__setattr__(self, "findings", findings)
        object.__setattr__(self, "coverage", coverage)
        object.__setattr__(self, "evidence_refs_used", evidence_refs_used)
        object.__setattr__(self, "confidence", freeze_agent_safe_mapping(self.confidence))
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "warnings", warnings)
