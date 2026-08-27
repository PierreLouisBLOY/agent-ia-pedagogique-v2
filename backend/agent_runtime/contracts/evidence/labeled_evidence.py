from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts.evidence.evidence_item import EvidenceItem
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentSecurityAssessment,
    LabeledContent,
)


@dataclass(frozen=True, slots=True)
class LabeledEvidenceItem:
    evidence_item: EvidenceItem
    content: LabeledContent
    security_assessment: ContentSecurityAssessment

    def __post_init__(self) -> None:
        if type(self.evidence_item) is not EvidenceItem:
            raise TypeError("evidence_item must be an EvidenceItem")
        if type(self.content) is not LabeledContent:
            raise TypeError("content must be a LabeledContent")
        if type(self.security_assessment) is not ContentSecurityAssessment:
            raise TypeError("security_assessment must be a ContentSecurityAssessment")
        if self.evidence_item.excerpt_or_summary is None:
            raise ValueError("labeled evidence requires excerpt_or_summary")
        if self.content.text != self.evidence_item.excerpt_or_summary:
            raise ValueError("labeled content must preserve the evidence text")
        if self.content.content_ref != self.evidence_item.evidence_id:
            raise ValueError("labeled content must reference the evidence id")
        label = self.content.label
        if label.origin is not ContentOrigin.EVIDENCE:
            raise ValueError("labeled evidence origin must remain EVIDENCE")
        if label.role is not ContentRole.EVIDENCE:
            raise ValueError("labeled evidence role must remain EVIDENCE")
        if label.source_ref != self.evidence_item.source_ref:
            raise ValueError("labeled evidence must preserve the source reference")
        if self.security_assessment.content_ref != self.content.content_ref:
            raise ValueError("security assessment must reference the labeled evidence")
        if self.security_assessment.label != label:
            raise ValueError("security assessment must preserve the content label")
