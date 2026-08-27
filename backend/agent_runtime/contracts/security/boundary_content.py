from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts.common import ContractRef, require_contract_ref
from backend.agent_runtime.contracts.security.content import (
    ContentSecurityAssessment,
    ContentSecurityDisposition,
)
from backend.agent_runtime.contracts.security.security_event import SecurityReasonCode
from backend.agent_runtime.contracts.security.trust import (
    ContentTrustLabel,
    SecurityBoundary,
)


@dataclass(frozen=True, slots=True)
class StructuredContentSecurityAssessment:
    """Data-only assessment for one structured boundary value."""

    content_ref: ContractRef
    label: ContentTrustLabel
    boundary: SecurityBoundary
    disposition: ContentSecurityDisposition
    content_assessments: tuple[ContentSecurityAssessment, ...]
    structural_locations: tuple[str, ...]
    reason_codes: tuple[SecurityReasonCode, ...]

    def __post_init__(self) -> None:
        require_contract_ref(self.content_ref, "content_ref")
        if type(self.label) is not ContentTrustLabel:
            raise TypeError("label must be a ContentTrustLabel")
        if type(self.boundary) is not SecurityBoundary:
            raise TypeError("boundary must be a SecurityBoundary")
        if type(self.disposition) is not ContentSecurityDisposition:
            raise TypeError("disposition must be a ContentSecurityDisposition")
        if type(self.content_assessments) is not tuple or any(
            type(item) is not ContentSecurityAssessment
            for item in self.content_assessments
        ):
            raise TypeError(
                "content_assessments must contain ContentSecurityAssessment values"
            )
        if any(item.label != self.label for item in self.content_assessments):
            raise ValueError("nested assessments must preserve the boundary label")
        assessment_refs = tuple(
            item.content_ref for item in self.content_assessments
        )
        if len(assessment_refs) != len(set(assessment_refs)):
            raise ValueError("nested assessment references must be unique")
        if type(self.structural_locations) is not tuple or any(
            type(location) is not str or not location
            for location in self.structural_locations
        ):
            raise TypeError("structural_locations must contain logical paths")
        if len(self.structural_locations) != len(set(self.structural_locations)):
            raise ValueError("structural_locations must be unique")
        if type(self.reason_codes) is not tuple or any(
            type(code) is not SecurityReasonCode for code in self.reason_codes
        ):
            raise TypeError("reason_codes must contain SecurityReasonCode values")
        has_findings = bool(self.structural_locations) or any(
            item.signals for item in self.content_assessments
        )
        if self.disposition is ContentSecurityDisposition.PASS_AS_DATA:
            if has_findings or self.reason_codes:
                raise ValueError("PASS_AS_DATA cannot carry boundary findings")
        elif not has_findings or not self.reason_codes:
            raise ValueError("non-pass boundary assessment requires findings and reasons")
        if self.structural_locations and self.disposition not in {
            ContentSecurityDisposition.QUARANTINE,
            ContentSecurityDisposition.REJECT_CONTENT,
        }:
            raise ValueError("structural authority findings require containment")
