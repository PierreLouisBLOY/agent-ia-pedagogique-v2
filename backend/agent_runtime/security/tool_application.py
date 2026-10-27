from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from backend.agent_runtime.contracts.common import ContractRef, ContractSchemaVersion
from backend.agent_runtime.contracts.evidence import EvidenceItem, LabeledEvidenceItem
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentSecurityDisposition,
    ContentTrustClass,
    ContentTrustLabel,
    LabeledContent,
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
    StructuredContentSecurityAssessment,
)
from backend.agent_runtime.security.content_isolation import (
    ContentIsolationContext,
    InstructionDataBoundaryPolicy,
    scan_content_threats,
)
from backend.agent_runtime.security.sensitive_values import SensitiveValuePolicy
from backend.agent_runtime.security.structural_keys import structural_key_locations
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_DISPOSITION_RANK = {
    ContentSecurityDisposition.PASS_AS_DATA: 0,
    ContentSecurityDisposition.ISOLATE_AS_DATA: 1,
    ContentSecurityDisposition.ESCALATE_REVIEW: 2,
    ContentSecurityDisposition.QUARANTINE: 3,
    ContentSecurityDisposition.REJECT_CONTENT: 4,
}


def assess_structured_boundary_content(
    value: object,
    *,
    content_ref: ContractRef,
    label: ContentTrustLabel,
    boundary: SecurityBoundary,
    forbidden_keys: Collection[str],
    root_location: str,
) -> tuple[tuple[LabeledContent, ...], StructuredContentSecurityAssessment]:
    if type(label) is not ContentTrustLabel:
        raise TypeError("label must be a ContentTrustLabel")
    if type(boundary) is not SecurityBoundary:
        raise TypeError("boundary must be a SecurityBoundary")

    SensitiveValuePolicy().require_safe(value, root_location=root_location)

    leaves = _string_leaves(value, (root_location,))
    labeled: list[LabeledContent] = []
    assessments = []
    source_boundary = _boundary_for_origin(label.origin)
    for index, (location, text) in enumerate(leaves):
        leaf_ref = f"{content_ref}:text:{index}"
        content = LabeledContent(f"boundary-content-{index}", text, label, leaf_ref)
        signals = scan_content_threats(
            text,
            content_ref=leaf_ref,
            logical_location=location,
        )
        assessment = InstructionDataBoundaryPolicy().assess(
            content=content,
            context=ContentIsolationContext(source_boundary),
            signals=signals,
        )
        labeled.append(content)
        assessments.append(assessment)

    structural_locations = structural_key_locations(
        value,
        forbidden_keys=forbidden_keys,
        root_location=root_location,
    )
    if structural_locations:
        disposition = ContentSecurityDisposition.QUARANTINE
    elif assessments:
        disposition = max(
            (item.disposition for item in assessments),
            key=_DISPOSITION_RANK.__getitem__,
        )
    else:
        disposition = ContentSecurityDisposition.PASS_AS_DATA

    reasons: list[SecurityReasonCode] = []
    if structural_locations:
        reasons.append(SecurityReasonCode("BOUNDARY.AUTHORITY_METADATA_PRESENT"))
    for assessment in assessments:
        for code in assessment.reason_codes:
            if code not in reasons:
                reasons.append(code)

    return tuple(labeled), StructuredContentSecurityAssessment(
        content_ref=content_ref,
        label=label,
        boundary=boundary,
        disposition=disposition,
        content_assessments=tuple(assessments),
        structural_locations=structural_locations,
        reason_codes=tuple(reasons),
    )


def security_event_from_structured_assessment(
    assessment: StructuredContentSecurityAssessment,
    *,
    schema_version: ContractSchemaVersion,
    event_id: str,
    occurred_at: Instant,
    run_id: str,
    correlation_id: CorrelationId,
    step_id: str | None = None,
    hostile_propagation: bool = False,
) -> SecurityEvent | None:
    if type(assessment) is not StructuredContentSecurityAssessment:
        raise TypeError("assessment must be a StructuredContentSecurityAssessment")
    if type(hostile_propagation) is not bool:
        raise TypeError("hostile_propagation must be a bool")
    if assessment.disposition in {
        ContentSecurityDisposition.PASS_AS_DATA,
        ContentSecurityDisposition.ISOLATE_AS_DATA,
    }:
        return None
    if assessment.structural_locations:
        event_type = SecurityEventType.AUTHORITY_SMUGGLING
    elif hostile_propagation:
        event_type = SecurityEventType.HOSTILE_CONTENT_PROPAGATION
    elif assessment.boundary is SecurityBoundary.TOOL:
        event_type = SecurityEventType.TOOL_INJECTION
    elif assessment.boundary is SecurityBoundary.APPLICATION:
        event_type = SecurityEventType.APPLICATION_INJECTION
    else:
        event_type = SecurityEventType.TRUST_BOUNDARY_VIOLATION
    return SecurityEvent(
        schema_version=schema_version,
        event_id=event_id,
        event_type=event_type,
        severity=(
            SecuritySeverity.HIGH
            if assessment.disposition
            in {
                ContentSecurityDisposition.QUARANTINE,
                ContentSecurityDisposition.REJECT_CONTENT,
            }
            else SecuritySeverity.MEDIUM
        ),
        boundary=assessment.boundary,
        reason_code=assessment.reason_codes[0],
        occurred_at=occurred_at,
        run_id=run_id,
        correlation_id=correlation_id,
        step_id=step_id,
        refs=(assessment.content_ref,),
        content_label=assessment.label,
        metadata={
            "finding_count": len(assessment.structural_locations)
            + sum(len(item.signals) for item in assessment.content_assessments)
        },
    )


def _string_leaves(value: object, path: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    if type(value) is str:
        return ((".".join(path), value),) if value else ()
    if isinstance(value, Mapping):
        leaves: list[tuple[str, str]] = []
        for index, (key, nested) in enumerate(value.items()):
            segment = _safe_location_segment(key, index)
            leaves.extend(_string_leaves(nested, (*path, segment)))
        return tuple(leaves)
    if isinstance(value, (list, tuple)):
        return tuple(
            leaf
            for index, nested in enumerate(value)
            for leaf in _string_leaves(nested, (*path, str(index)))
        )
    return ()


def _safe_location_segment(value: str, index: int) -> str:
    normalized = "_".join(
        part for part in value.replace("-", "_").split("_") if part
    )
    if normalized and len(normalized) <= 64 and all(
        character.isascii() and (character.isalnum() or character == "_")
        for character in normalized
    ):
        return normalized
    return f"field_{index}"


def _boundary_for_origin(origin: ContentOrigin) -> SecurityBoundary:
    return {
        ContentOrigin.USER_INPUT: SecurityBoundary.USER_INPUT,
        ContentOrigin.DOCUMENT: SecurityBoundary.DOCUMENT,
        ContentOrigin.EVIDENCE: SecurityBoundary.EVIDENCE,
        ContentOrigin.AGENT_OUTPUT: SecurityBoundary.AGENT,
        ContentOrigin.TOOL_OUTPUT: SecurityBoundary.TOOL,
        ContentOrigin.APPLICATION_OUTPUT: SecurityBoundary.APPLICATION,
        ContentOrigin.REVIEW_OUTPUT: SecurityBoundary.AGENT,
        ContentOrigin.CORRECTION_OUTPUT: SecurityBoundary.AGENT,
        ContentOrigin.RUNTIME_DATA: SecurityBoundary.RUNTIME,
        ContentOrigin.RECOVERY_DATA: SecurityBoundary.RECOVERY,
        ContentOrigin.INTERNAL_CONTROL: SecurityBoundary.INFRASTRUCTURE,
    }[origin]


def label_untrusted_evidence_items(evidence_items: Sequence[EvidenceItem]) -> tuple[LabeledEvidenceItem, ...]:
    """Security projection only; evidence construction/admission stay with AG02/Application."""
    result = []
    for item in evidence_items:
        if type(item) is not EvidenceItem or not item.excerpt_or_summary:
            raise ValueError("UNTRUSTED_EVIDENCE_CONTENT_REQUIRED")
        label = ContentTrustLabel(ContentOrigin.EVIDENCE, ContentRole.EVIDENCE, ContentTrustClass.UNTRUSTED, item.source_ref)
        content = LabeledContent(item.evidence_id, item.excerpt_or_summary, label, item.evidence_id)
        assessment = InstructionDataBoundaryPolicy().assess(content=content,
            context=ContentIsolationContext(SecurityBoundary.EVIDENCE),
            signals=scan_content_threats(item.excerpt_or_summary, content_ref=item.evidence_id, logical_location="p0_evidence"))
        result.append(LabeledEvidenceItem(item, content, assessment))
    return tuple(result)


def label_untrusted_application_inputs(value: Mapping[str, object], *, content_ref: str,
    forbidden_keys: Collection[str], root_location: str) -> tuple[tuple[LabeledContent, ...], StructuredContentSecurityAssessment]:
    label = ContentTrustLabel(ContentOrigin.APPLICATION_OUTPUT, ContentRole.RESULT, ContentTrustClass.UNTRUSTED, content_ref)
    return assess_structured_boundary_content(value, content_ref=content_ref, label=label,
        boundary=SecurityBoundary.APPLICATION, forbidden_keys=forbidden_keys, root_location=root_location)
