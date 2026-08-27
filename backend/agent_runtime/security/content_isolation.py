from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ContractRef,
    ContractSchemaVersion,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.evidence import EvidenceItem, LabeledEvidenceItem
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentSecurityAssessment,
    ContentSecurityDisposition,
    ContentThreatSignal,
    ContentThreatSignalCode,
    ContentTrustClass,
    ContentTrustLabel,
    LabeledContent,
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_THREAT_PATTERNS: Mapping[ContentThreatSignalCode, tuple[str, ...]] = {
    ContentThreatSignalCode.INSTRUCTION_LIKE_CONTENT: (
        "ignore previous instructions",
        "ignore all instructions",
        "disregard prior instructions",
        "ignore les consignes",
        "ignore les règles",
        "ignore les instructions",
        "instructions précédentes",
        "ne tiens pas compte des instructions",
        "system prompt",
        "developer message",
    ),
    ContentThreatSignalCode.PRIVILEGE_ESCALATION_TEXT: (
        "you are admin",
        "administrator privileges",
        "admin privileges",
        "elevated privileges",
        "root access",
        "je suis administrateur",
        "droits administrateur",
        "privilèges élevés",
        "authorize cap-",
        "autorise cap-",
        "grant permission",
        "accorde la permission",
        "contourne les permissions",
        "bypass permissions",
        "sudo ",
    ),
    ContentThreatSignalCode.EXFILTRATION_TEXT: (
        "exfiltrate",
        "reveal secret",
        "show api key",
        "send secrets",
        "steal data",
        "upload credentials",
        "send data to",
        "envoie les secrets",
        "révèle le secret",
        "envoyer les secrets",
        "extraire les données",
        "exfiltrer",
    ),
    ContentThreatSignalCode.TOOL_OR_FILE_ACTION_TEXT: (
        "call this tool",
        "appelle cet outil",
        "read this file",
        "lis ce fichier",
        "open this path",
        "ouvre ce chemin",
        "delete file",
        "execute command",
        "read file",
        "open file",
        "run command",
        "tool call",
        "write file",
        "exécute la commande",
        "lire le fichier",
        "supprimer le fichier",
    ),
    ContentThreatSignalCode.AUTHORITY_CLAIM_TEXT: (
        "already validated",
        "already approved",
        "is canonical",
        "is promoted",
        "approved output",
        "canonical output",
        "safe output",
        "trusted output",
        "validated output",
        "authoritative",
        "officially approved",
        "this content is safe",
        "this is validated",
        "sortie approuvée",
        "sortie canonique",
        "sortie sûre",
        "sortie validée",
        "contenu validé",
        "fait autorité",
        "source officielle",
        "promotion allowed",
        "gate approved",
        "permission granted",
        "review passed",
        "validator passed",
        "déjà validé",
        "déjà approuvé",
    ),
}

_STRUCTURAL_AUTHORITY_KEYS = frozenset(
    {
        "capability",
        "capability_id",
        "gate",
        "gate_decision",
        "handler",
        "owner",
        "permission",
        "permission_scope",
        "policy_facts",
        "provider",
        "route",
        "target",
    }
)


@dataclass(frozen=True, slots=True)
class ContentIsolationContext:
    boundary: SecurityBoundary
    structured_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.boundary) is not SecurityBoundary:
            raise TypeError("boundary must be a SecurityBoundary")
        object.__setattr__(
            self,
            "structured_metadata",
            freeze_agent_safe_mapping(self.structured_metadata),
        )


@dataclass(frozen=True, slots=True)
class InstructionDataBoundaryPolicy:
    """Pure classification policy; it grants no execution authority."""

    def assess(
        self,
        *,
        content: LabeledContent,
        context: ContentIsolationContext,
        signals: tuple[ContentThreatSignal, ...] = (),
    ) -> ContentSecurityAssessment:
        if type(content) is not LabeledContent:
            raise TypeError("content must be a LabeledContent")
        if type(context) is not ContentIsolationContext:
            raise TypeError("context must be a ContentIsolationContext")
        if type(signals) is not tuple or any(
            type(signal) is not ContentThreatSignal for signal in signals
        ):
            raise TypeError("signals must contain ContentThreatSignal values")
        if any(signal.content_ref != content.content_ref for signal in signals):
            raise ValueError("signals must reference the assessed content")

        combined = list(signals)
        role_confusion = _has_role_or_boundary_confusion(content.label, context.boundary)
        if role_confusion:
            combined.append(
                ContentThreatSignal(
                    ContentThreatSignalCode.ROLE_CONFUSION,
                    content.content_ref,
                    "label",
                )
            )

        authority_locations = (
            structural_authority_locations(context.structured_metadata)
            if content.label.origin in {ContentOrigin.DOCUMENT, ContentOrigin.EVIDENCE}
            else ()
        )
        combined.extend(
            ContentThreatSignal(
                ContentThreatSignalCode.AUTHORITY_CLAIM_TEXT,
                content.content_ref,
                location,
            )
            for location in authority_locations
        )
        canonical_signals = tuple(dict.fromkeys(combined))

        codes = {signal.code for signal in canonical_signals}
        if role_confusion or authority_locations:
            disposition = ContentSecurityDisposition.QUARANTINE
        elif ContentThreatSignalCode.UPSTREAM_SECURITY_WARNING in codes:
            disposition = ContentSecurityDisposition.ESCALATE_REVIEW
        elif canonical_signals:
            disposition = ContentSecurityDisposition.ISOLATE_AS_DATA
        else:
            disposition = ContentSecurityDisposition.PASS_AS_DATA

        reason_codes: list[SecurityReasonCode] = []
        if role_confusion:
            reason_codes.append(SecurityReasonCode("CONTENT.ROLE_OR_BOUNDARY_MISMATCH"))
        if authority_locations:
            reason_codes.append(SecurityReasonCode("CONTENT.AUTHORITY_METADATA_PRESENT"))
        if ContentThreatSignalCode.UPSTREAM_SECURITY_WARNING in codes:
            reason_codes.append(SecurityReasonCode("CONTENT.UPSTREAM_SECURITY_WARNING"))
        if canonical_signals and not reason_codes:
            reason_codes.append(SecurityReasonCode("CONTENT.THREAT_SIGNAL_PRESENT"))

        return ContentSecurityAssessment(
            content_ref=content.content_ref,
            label=content.label,
            disposition=disposition,
            signals=canonical_signals,
            reason_codes=tuple(reason_codes),
        )


def scan_content_threats(
    text: str,
    *,
    content_ref: ContractRef,
    logical_location: str,
) -> tuple[ContentThreatSignal, ...]:
    if type(text) is not str:
        raise TypeError("text must be a string")
    require_contract_ref(content_ref, "content_ref")
    normalized = text.casefold()
    codes = [
        code
        for code, patterns in _THREAT_PATTERNS.items()
        if any(pattern in normalized for pattern in patterns)
    ]
    if "http://" in normalized or "https://" in normalized or "www." in normalized:
        codes.append(ContentThreatSignalCode.URL_PRESENT)
    code_set = set(codes)
    return tuple(
        ContentThreatSignal(code, content_ref, logical_location)
        for code in ContentThreatSignalCode
        if code in code_set
    )


def label_evidence_item(item: EvidenceItem) -> LabeledEvidenceItem:
    if type(item) is not EvidenceItem:
        raise TypeError("item must be an EvidenceItem")
    if item.excerpt_or_summary is None:
        raise ValueError("evidence must contain excerpt_or_summary")
    label = ContentTrustLabel(
        origin=ContentOrigin.EVIDENCE,
        role=ContentRole.EVIDENCE,
        trust_class=ContentTrustClass.STRUCTURALLY_VALIDATED,
        source_ref=item.source_ref,
    )
    content = LabeledContent(
        content_id=item.evidence_id,
        text=item.excerpt_or_summary,
        label=label,
        content_ref=item.evidence_id,
    )
    signals = scan_content_threats(
        content.text,
        content_ref=content.content_ref,
        logical_location="evidence.excerpt",
    )
    assessment = InstructionDataBoundaryPolicy().assess(
        content=content,
        context=ContentIsolationContext(
            SecurityBoundary.EVIDENCE,
            {
                "relevance": item.relevance,
                "source_authority": item.authority,
            },
        ),
        signals=signals,
    )
    return LabeledEvidenceItem(item, content, assessment)


def structural_authority_locations(value: object) -> tuple[str, ...]:
    matches: list[str] = []
    _collect_authority_locations(value, ("metadata",), matches)
    return tuple(dict.fromkeys(matches))


def reject_structural_authority_metadata(value: object) -> None:
    if structural_authority_locations(value):
        raise ValueError("structured content contains authority-smuggling fields")


def security_event_from_content_assessment(
    assessment: ContentSecurityAssessment,
    *,
    schema_version: ContractSchemaVersion,
    event_id: str,
    occurred_at: Instant,
    run_id: str,
    correlation_id: CorrelationId,
    step_id: str | None = None,
) -> SecurityEvent | None:
    if type(assessment) is not ContentSecurityAssessment:
        raise TypeError("assessment must be a ContentSecurityAssessment")
    codes = {signal.code for signal in assessment.signals}
    if assessment.disposition in {
        ContentSecurityDisposition.PASS_AS_DATA,
        ContentSecurityDisposition.ISOLATE_AS_DATA,
    }:
        return None
    if ContentThreatSignalCode.ROLE_CONFUSION in codes:
        event_type = SecurityEventType.TRUST_BOUNDARY_VIOLATION
    elif any(
        code.value == "CONTENT.AUTHORITY_METADATA_PRESENT"
        for code in assessment.reason_codes
    ):
        event_type = SecurityEventType.AUTHORITY_SMUGGLING
    else:
        event_type = SecurityEventType.HOSTILE_CONTENT_PROPAGATION
    boundary = _boundary_for_origin(assessment.label.origin)
    severity = (
        SecuritySeverity.HIGH
        if assessment.disposition is ContentSecurityDisposition.QUARANTINE
        else SecuritySeverity.MEDIUM
    )
    return SecurityEvent(
        schema_version=schema_version,
        event_id=event_id,
        event_type=event_type,
        severity=severity,
        boundary=boundary,
        reason_code=assessment.reason_codes[0],
        occurred_at=occurred_at,
        run_id=run_id,
        correlation_id=correlation_id,
        step_id=step_id,
        refs=(assessment.content_ref,),
        content_label=assessment.label,
        metadata={"signal_codes": tuple(code.value for code in sorted(codes))},
    )


def _has_role_or_boundary_confusion(
    label: ContentTrustLabel,
    boundary: SecurityBoundary,
) -> bool:
    expected = {
        ContentOrigin.USER_INPUT: (SecurityBoundary.USER_INPUT, None),
        ContentOrigin.DOCUMENT: (SecurityBoundary.DOCUMENT, ContentRole.DATA),
        ContentOrigin.EVIDENCE: (SecurityBoundary.EVIDENCE, ContentRole.EVIDENCE),
        ContentOrigin.AGENT_OUTPUT: (SecurityBoundary.AGENT, ContentRole.RESULT),
        ContentOrigin.REVIEW_OUTPUT: (SecurityBoundary.AGENT, ContentRole.RESULT),
        ContentOrigin.CORRECTION_OUTPUT: (SecurityBoundary.AGENT, ContentRole.RESULT),
    }.get(label.origin)
    if expected is None:
        return False
    expected_boundary, expected_role = expected
    return boundary is not expected_boundary or (
        expected_role is not None and label.role is not expected_role
    )


def _collect_authority_locations(
    value: object,
    path: tuple[str, ...],
    matches: list[str],
) -> None:
    if isinstance(value, Mapping):
        for index, (key, nested) in enumerate(value.items()):
            normalized = _normalized_key(key)
            segment = normalized if _is_safe_segment(normalized) else f"field_{index}"
            nested_path = (*path, segment)
            if normalized in _STRUCTURAL_AUTHORITY_KEYS:
                matches.append(".".join(nested_path))
            _collect_authority_locations(nested, nested_path, matches)
    elif isinstance(value, tuple):
        for index, nested in enumerate(value):
            _collect_authority_locations(nested, (*path, str(index)), matches)


def _normalized_key(key: str) -> str:
    components: list[str] = []
    current: list[str] = []
    for index, character in enumerate(key):
        if not character.isalnum():
            if current:
                components.append("".join(current).casefold())
                current = []
            continue
        next_character = key[index + 1] if index + 1 < len(key) else ""
        if current and character.isupper() and (
            current[-1].islower()
            or (current[-1].isupper() and next_character.islower())
        ):
            components.append("".join(current).casefold())
            current = []
        current.append(character)
    if current:
        components.append("".join(current).casefold())
    return "_".join(components)


def _is_safe_segment(value: str) -> bool:
    return bool(value) and len(value) <= 64 and all(
        character.isascii() and (character.isalnum() or character == "_")
        for character in value
    )


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
