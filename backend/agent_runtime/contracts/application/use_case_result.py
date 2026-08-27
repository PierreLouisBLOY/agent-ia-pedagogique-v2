from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.errors import ErrorEnvelope
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentTrustClass,
    ContentTrustLabel,
    LabeledContent,
    SecurityBoundary,
    StructuredContentSecurityAssessment,
)
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class UseCaseResult[TData, TValidationResult]:
    """Agent-runtime view of an ApplicationOutcome without masking domain errors."""

    meta: ContractMeta[OutcomeStatus]
    use_case_id: str
    outcome: ApplicationOutcome[TData, TValidationResult]
    result_ref: ContractRef | None = None
    domain_events: tuple[ContractRef | Mapping[str, object], ...] = ()
    error: ErrorEnvelope | None = None
    content_label: ContentTrustLabel | None = None
    labeled_content: tuple[LabeledContent, ...] = ()
    security_assessments: tuple[StructuredContentSecurityAssessment, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, OutcomeStatus):
            raise TypeError("meta.status must be an OutcomeStatus")
        require_non_empty(self.use_case_id, "use_case_id")
        if not isinstance(self.outcome, ApplicationOutcome):
            raise TypeError("outcome must be an ApplicationOutcome")
        if self.meta.status is not self.outcome.outcome_status:
            raise ValueError("meta.status must match outcome.outcome_status")
        if self.meta.correlation_id != self.outcome.correlation_id:
            raise ValueError("outcome correlation must match meta correlation")
        if self.result_ref is not None:
            require_contract_ref(self.result_ref, "result_ref")
        domain_events: list[ContractRef | Mapping[str, object]] = []
        for event in self.domain_events:
            if isinstance(event, Mapping):
                domain_events.append(freeze_agent_safe_mapping(event))
            else:
                require_contract_ref(event, "domain_event")
                domain_events.append(event)
        if self.error is not None:
            if not isinstance(self.error, ErrorEnvelope):
                raise TypeError("error must be an ErrorEnvelope")
            if self.error.step_id != self.meta.step_id:
                raise ValueError("error.step_id must match meta.step_id")
        expected_ref = f"application-result:{self.use_case_id}:{self.meta.step_id}"
        content_label = self.content_label or ContentTrustLabel(
            origin=ContentOrigin.APPLICATION_OUTPUT,
            role=ContentRole.RESULT,
            trust_class=ContentTrustClass.UNTRUSTED,
            source_ref=expected_ref,
        )
        if (
            type(content_label) is ContentTrustLabel
            and content_label.origin is ContentOrigin.APPLICATION_OUTPUT
            and content_label.role is ContentRole.RESULT
            and content_label.trust_class is ContentTrustClass.UNTRUSTED
            and isinstance(content_label.source_ref, str)
            and content_label.source_ref.startswith("application-result:")
            and not self.labeled_content
            and not self.security_assessments
        ):
            content_label = ContentTrustLabel(
                origin=ContentOrigin.APPLICATION_OUTPUT,
                role=ContentRole.RESULT,
                trust_class=ContentTrustClass.UNTRUSTED,
                source_ref=expected_ref,
            )
        if type(content_label) is not ContentTrustLabel:
            raise TypeError("content_label must be a ContentTrustLabel")
        if (
            content_label.origin is not ContentOrigin.APPLICATION_OUTPUT
            or content_label.role is not ContentRole.RESULT
            or content_label.trust_class is not ContentTrustClass.UNTRUSTED
            or content_label.source_ref != expected_ref
        ):
            raise ValueError(
                "content_label must preserve untrusted Application provenance"
            )
        labeled_content = tuple(self.labeled_content)
        if any(type(item) is not LabeledContent for item in labeled_content):
            raise TypeError("labeled_content must contain LabeledContent values")
        if any(item.label != content_label for item in labeled_content):
            raise ValueError("labeled_content must preserve the Application label")
        if len({item.content_ref for item in labeled_content}) != len(labeled_content):
            raise ValueError("labeled_content references must be unique")
        assessments = tuple(self.security_assessments)
        if any(
            type(item) is not StructuredContentSecurityAssessment
            for item in assessments
        ):
            raise TypeError("security_assessments contain an invalid type")
        if any(
            item.label != content_label
            or item.boundary is not SecurityBoundary.APPLICATION
            for item in assessments
        ):
            raise ValueError("security assessments must preserve Application lineage")
        assessed_refs = {
            nested.content_ref
            for assessment in assessments
            for nested in assessment.content_assessments
        }
        if assessed_refs != {item.content_ref for item in labeled_content}:
            raise ValueError("security assessments must cover labeled Application content")
        object.__setattr__(self, "domain_events", tuple(domain_events))
        object.__setattr__(self, "content_label", content_label)
        object.__setattr__(self, "labeled_content", labeled_content)
        object.__setattr__(self, "security_assessments", assessments)
