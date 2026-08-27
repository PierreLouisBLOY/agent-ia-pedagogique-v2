from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts.delegation import DelegationResult
from backend.agent_runtime.contracts.invocation import AgentInvocation
from backend.agent_runtime.contracts.security.boundary_content import (
    StructuredContentSecurityAssessment,
)
from backend.agent_runtime.contracts.security.content import LabeledContent
from backend.agent_runtime.contracts.security.trust import ContentTrustLabel


@dataclass(frozen=True, slots=True)
class ValidatedAgentHandoff[TPayload]:
    """A data-only handoff proven at the AG-01/specialist trust boundary.

    Validation is structural and security-oriented. It is never a business
    validation, permission, gate decision, promotion, or execution command.
    """

    invocation: AgentInvocation
    result: DelegationResult[TPayload]
    output_label: ContentTrustLabel
    context_content: tuple[LabeledContent, ...]
    output_content: tuple[LabeledContent, ...]
    context_assessment: StructuredContentSecurityAssessment
    output_assessment: StructuredContentSecurityAssessment

    def __post_init__(self) -> None:
        if type(self.invocation) is not AgentInvocation:
            raise TypeError("invocation must be an AgentInvocation")
        if not isinstance(self.result, DelegationResult):
            raise TypeError("result must be a DelegationResult")
        if type(self.output_label) is not ContentTrustLabel:
            raise TypeError("output_label must be a ContentTrustLabel")
        if type(self.context_content) is not tuple or any(
            type(item) is not LabeledContent for item in self.context_content
        ):
            raise TypeError("context_content must contain LabeledContent values")
        if type(self.output_content) is not tuple or any(
            type(item) is not LabeledContent for item in self.output_content
        ):
            raise TypeError("output_content must contain LabeledContent values")
        if type(self.context_assessment) is not StructuredContentSecurityAssessment:
            raise TypeError(
                "context_assessment must be a StructuredContentSecurityAssessment"
            )
        if type(self.output_assessment) is not StructuredContentSecurityAssessment:
            raise TypeError(
                "output_assessment must be a StructuredContentSecurityAssessment"
            )
        if self.output_assessment.label != self.output_label:
            raise ValueError("output assessment must preserve output provenance")
