from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import NoReturn

from backend.agent_runtime.agents.evidence.evidence_security_model import (
    EvidenceSecurityAssessment,
    EvidenceSecuritySignalCode,
)
from backend.agent_runtime.agents.review.review_coordination_model import (
    ResolvedReviewTarget,
)
from backend.agent_runtime.agents.review.review_model import _reject_authority_keys
from backend.agent_runtime.agents.review.review_security_model import (
    EvidenceSecurityByRef,
    LocatorValidationResult,
    ReviewSecurityAssessment,
    ReviewSecurityDisposition,
    ReviewSecurityError,
    ReviewSecurityPolicy,
    ReviewSecuritySignal,
    ReviewSecuritySignalCode,
)
from backend.agent_runtime.contracts import Finding
from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)

_TARGET_PATTERNS: tuple[
    tuple[ReviewSecuritySignalCode, tuple[str, ...]], ...
] = (
    (
        ReviewSecuritySignalCode.TARGET_INSTRUCTION_LIKE_CONTENT,
        (
            "ignore previous instructions",
            "ignore all instructions",
            "ignore les consignes",
            "ignore les règles",
            "system prompt",
            "developer message",
        ),
    ),
    (
        ReviewSecuritySignalCode.TARGET_PRIVILEGE_ESCALATION_TEXT,
        (
            "you are admin",
            "je suis administrateur",
            "authorize cap-",
            "autorise cap-",
            "grant permission",
            "accorde la permission",
        ),
    ),
    (
        ReviewSecuritySignalCode.TARGET_EXFILTRATION_TEXT,
        (
            "reveal secret",
            "show api key",
            "send secrets",
            "envoie les secrets",
            "révèle le secret",
        ),
    ),
    (
        ReviewSecuritySignalCode.TARGET_TOOL_OR_FILE_ACTION_TEXT,
        (
            "call this tool",
            "appelle cet outil",
            "read this file",
            "lis ce fichier",
            "open this path",
            "ouvre ce chemin",
        ),
    ),
    (
        ReviewSecuritySignalCode.TARGET_AUTHORITY_CLAIM,
        (
            "already validated",
            "already approved",
            "is canonical",
            "is promoted",
            "validated",
            "approved",
            "promoted",
            "promotion allowed",
            "gate approved",
            "permission granted",
            "review passed",
            "validator passed",
            "déjà validé",
            "déjà approuvé",
        ),
    ),
)

_EVIDENCE_WARNING_CODES = frozenset(EvidenceSecuritySignalCode)


@dataclass(frozen=True, slots=True)
class ReviewSecurityGuard:
    def assess(
        self,
        *,
        target: ResolvedReviewTarget,
        policy: ReviewSecurityPolicy,
        review_evidence_refs: tuple[ContractRef, ...],
        required_evidence_refs: tuple[ContractRef, ...] = (),
        evidence_security_by_ref: EvidenceSecurityByRef | None = None,
    ) -> ReviewSecurityAssessment:
        _validate_guard_inputs(
            target,
            policy,
            review_evidence_refs,
            required_evidence_refs,
        )
        security_by_ref = freeze_evidence_security_by_ref(
            {} if evidence_security_by_ref is None else evidence_security_by_ref
        )
        evidence_signals = _validated_evidence_security(
            security_by_ref,
            review_evidence_refs,
            required_evidence_refs,
            policy,
        )
        target_signals = _target_signals(target)
        signals = target_signals + evidence_signals
        disposition = _disposition(signals, policy)
        warnings = tuple(
            {
                "code": signal.code.value,
                "evidence_refs": signal.evidence_refs,
                "location_kind": signal.location_kind,
            }
            for signal in signals
            if _signal_disposition(signal, policy)
            is ReviewSecurityDisposition.ALLOW_WITH_WARNINGS
        )
        limitations = (
            (
                {
                    "code": "REVIEW_SECURITY_IS_DESCRIPTIVE_ONLY",
                    "document_instructions_authoritative": False,
                    "external_actions_allowed": False,
                    "links_followed": False,
                },
            )
            if signals
            else ()
        )
        return ReviewSecurityAssessment(
            target_production_ref=target.target_production_ref,
            target_snapshot_fingerprint=target_snapshot_fingerprint(target),
            disposition=disposition,
            signals=signals,
            evidence_refs_assessed=tuple(
                evidence_ref
                for evidence_ref in review_evidence_refs
                if evidence_ref in security_by_ref
            ),
            warnings=warnings,
            limitations=limitations,
        )


def validate_finding_locator(
    target: ResolvedReviewTarget,
    locator: Mapping[str, object],
    *,
    policy: ReviewSecurityPolicy,
) -> LocatorValidationResult:
    _validated_policy(policy)
    if type(target) is not ResolvedReviewTarget or not isinstance(locator, Mapping):
        _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)
    frozen = _authority_free_mapping(locator)
    kind = frozen.get("kind")
    if kind == "text_span":
        return _validate_text_span(target, frozen)
    if kind == "json_path":
        return _validate_json_path(target, frozen)
    if kind == "whole_target":
        if set(frozen) != {"kind"}:
            _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)
        if not policy.allow_whole_target_locator:
            _raise_security(ReviewSecuritySignalCode.LOCATOR_AMBIGUOUS)
        if target.content is not None and target.structured_payload:
            _raise_security(ReviewSecuritySignalCode.LOCATOR_AMBIGUOUS)
        return LocatorValidationResult("whole_target", ("whole_target",))
    _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)


def finding_lineage_fingerprint(finding: Finding) -> str:
    if type(finding) is not Finding:
        _raise_security(ReviewSecuritySignalCode.FINDING_LINEAGE_MISMATCH)
    locator = _authority_free_mapping(finding.target_locator)
    _authority_free_mapping(finding.confidence)
    _authority_free_mapping(finding.suggested_action)
    canonical = (
        finding.finding_id,
        finding.dimension.value,
        finding.severity.value,
        _canonical_value(locator),
        finding.correction_required,
        finding.evidence_refs,
    )
    return sha256(repr(canonical).encode("utf-8")).hexdigest()


def target_snapshot_fingerprint(target: ResolvedReviewTarget) -> str:
    if type(target) is not ResolvedReviewTarget:
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)
    try:
        rebuilt_target = ResolvedReviewTarget(
            target.target_production_ref,
            content=target.content,
            structured_payload=target.structured_payload,
        )
    except (TypeError, ValueError):
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)
    if rebuilt_target != target:
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)
    canonical = (target.content, _canonical_value(target.structured_payload))
    return sha256(repr(canonical).encode("utf-8")).hexdigest()


def freeze_evidence_security_by_ref(
    value: EvidenceSecurityByRef,
) -> EvidenceSecurityByRef:
    if not isinstance(value, Mapping):
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)
    copied: dict[ContractRef, EvidenceSecurityAssessment] = {}
    try:
        for evidence_ref, assessment in value.items():
            require_contract_ref(evidence_ref, "evidence_security_ref")
            if type(assessment) is not EvidenceSecurityAssessment:
                raise TypeError("assessment must be an EvidenceSecurityAssessment")
            _revalidate_evidence_assessment(assessment)
            copied[evidence_ref] = assessment
    except (TypeError, ValueError):
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)
    return MappingProxyType(copied)


def reject_review_authority(value: object) -> None:
    try:
        _reject_authority_keys(value, "review_security_input")
    except (TypeError, ValueError):
        _raise_security(ReviewSecuritySignalCode.AUTHORITY_METADATA_FORBIDDEN)


def reject_activatable_review_metadata(value: object) -> None:
    reject_review_authority(value)
    strings = _string_values(value)
    if any(_contains_url(text) for text in strings) or any(
        _contains_pattern(text, patterns)
        for _, patterns in _TARGET_PATTERNS
        for text in strings
    ):
        _raise_security(ReviewSecuritySignalCode.AUTHORITY_METADATA_FORBIDDEN)


def require_security_output_allowed(
    assessment: ReviewSecurityAssessment,
    policy: ReviewSecurityPolicy,
) -> None:
    if type(assessment) is not ReviewSecurityAssessment:
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)
    _validated_policy(policy)
    if assessment.disposition in {
        ReviewSecurityDisposition.REPAIR_REQUIRED,
        ReviewSecurityDisposition.REJECT,
    }:
        code = next(
            (
                signal.code
                for signal in assessment.signals
                if _DISPOSITION_RANK[_signal_disposition(signal, policy)]
                >= _DISPOSITION_RANK[ReviewSecurityDisposition.REPAIR_REQUIRED]
            ),
            ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH,
        )
        _raise_security(code)


def _validate_text_span(
    target: ResolvedReviewTarget,
    locator: Mapping[str, object],
) -> LocatorValidationResult:
    if set(locator) != {"kind", "start", "end", "quote"}:
        _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)
    start = locator["start"]
    end = locator["end"]
    quote = locator["quote"]
    if (
        type(start) is not int
        or type(end) is not int
        or type(quote) is not str
        or not quote
    ):
        _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)
    content = target.content
    if content is None or not 0 <= start < end <= len(content):
        _raise_security(ReviewSecuritySignalCode.LOCATOR_OUT_OF_TARGET)
    if content[start:end] != quote:
        _raise_security(ReviewSecuritySignalCode.LOCATOR_OUT_OF_TARGET)
    return LocatorValidationResult("text_span", ("text_span", start, end, quote))


def _validate_json_path(
    target: ResolvedReviewTarget,
    locator: Mapping[str, object],
) -> LocatorValidationResult:
    if set(locator) != {"kind", "path"}:
        _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)
    path = locator["path"]
    if type(path) is not tuple or not path:
        _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)
    if any(not _valid_path_segment(segment) for segment in path):
        _raise_security(ReviewSecuritySignalCode.LOCATOR_INVALID)
    current: object = target.structured_payload
    for segment in path:
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
        elif type(current) is tuple and type(segment) is int and 0 <= segment < len(current):
            current = current[segment]
        else:
            _raise_security(ReviewSecuritySignalCode.LOCATOR_OUT_OF_TARGET)
    return LocatorValidationResult("json_path", ("json_path", *path))


def _valid_path_segment(segment: object) -> bool:
    if type(segment) is int:
        return segment >= 0
    if type(segment) is not str or not segment:
        return False
    return not any(marker in segment for marker in ("*", "$", "[", "]", "/", "."))


def _target_signals(target: ResolvedReviewTarget) -> tuple[ReviewSecuritySignal, ...]:
    text_values = (() if target.content is None else (target.content,))
    payload_values = _string_values(target.structured_payload)
    signals: list[ReviewSecuritySignal] = []
    for code, patterns in _TARGET_PATTERNS:
        if any(_contains_pattern(value, patterns) for value in text_values):
            signals.append(ReviewSecuritySignal(code, location_kind="text"))
        if any(_contains_pattern(value, patterns) for value in payload_values):
            signals.append(ReviewSecuritySignal(code, location_kind="payload"))
    if any(_contains_url(value) for value in text_values):
        signals.append(
            ReviewSecuritySignal(
                ReviewSecuritySignalCode.TARGET_URL_PRESENT,
                location_kind="text",
            )
        )
    if any(_contains_url(value) for value in payload_values):
        signals.append(
            ReviewSecuritySignal(
                ReviewSecuritySignalCode.TARGET_URL_PRESENT,
                location_kind="payload",
            )
        )
    try:
        _reject_authority_keys(target.structured_payload, "target_payload")
    except (TypeError, ValueError):
        signals.append(
            ReviewSecuritySignal(
                ReviewSecuritySignalCode.TARGET_AUTHORITY_CLAIM,
                location_kind="payload",
            )
        )
    return tuple(dict.fromkeys(signals))


def _validated_evidence_security(
    security_by_ref: EvidenceSecurityByRef,
    review_refs: tuple[ContractRef, ...],
    required_refs: tuple[ContractRef, ...],
    policy: ReviewSecurityPolicy,
) -> tuple[ReviewSecuritySignal, ...]:
    known = set(review_refs)
    if not set(security_by_ref).issubset(known):
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)
    if policy.require_evidence_security_assessment and not set(required_refs).issubset(
        security_by_ref
    ):
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)
    warning_refs: list[ContractRef] = []
    for evidence_ref in review_refs:
        assessment = security_by_ref.get(evidence_ref)
        if assessment is None:
            continue
        assessed_ids = {
            evidence_id
            for group in assessment.independent_corroboration_groups
            for evidence_id in group
        }
        if not assessed_ids.issubset(known) or evidence_ref not in assessed_ids:
            _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)
        if evidence_ref in required_refs and any(
            signal.code in _EVIDENCE_WARNING_CODES for signal in assessment.signals
        ):
            warning_refs.append(evidence_ref)
    if not warning_refs:
        return ()
    return (
        ReviewSecuritySignal(
            ReviewSecuritySignalCode.EVIDENCE_SECURITY_WARNING_PRESENT,
            tuple(warning_refs),
            "evidence",
        ),
    )


def _revalidate_evidence_assessment(assessment: EvidenceSecurityAssessment) -> None:
    rebuilt = EvidenceSecurityAssessment(
        signals=assessment.signals,
        suspicious_evidence_ids=assessment.suspicious_evidence_ids,
        independent_corroboration_groups=assessment.independent_corroboration_groups,
        document_instructions_authoritative=(
            assessment.document_instructions_authoritative
        ),
        external_actions_allowed=assessment.external_actions_allowed,
        links_followed=assessment.links_followed,
        limitations=assessment.limitations,
    )
    if rebuilt != assessment:
        raise ValueError("evidence security assessment mismatch")


def _validate_guard_inputs(
    target: ResolvedReviewTarget,
    policy: ReviewSecurityPolicy,
    review_refs: tuple[ContractRef, ...],
    required_refs: tuple[ContractRef, ...],
) -> None:
    if type(target) is not ResolvedReviewTarget:
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)
    _validated_policy(policy)
    _validate_ref_tuple(review_refs)
    _validate_ref_tuple(required_refs)
    if not set(required_refs).issubset(review_refs):
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)


def _validated_policy(policy: ReviewSecurityPolicy) -> None:
    if type(policy) is not ReviewSecurityPolicy:
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)
    try:
        rebuilt = ReviewSecurityPolicy(
            require_locator_validation=policy.require_locator_validation,
            require_evidence_security_assessment=(
                policy.require_evidence_security_assessment
            ),
            block_on_target_instruction=policy.block_on_target_instruction,
            block_on_privilege_escalation=policy.block_on_privilege_escalation,
            block_on_exfiltration=policy.block_on_exfiltration,
            block_on_tool_file_action=policy.block_on_tool_file_action,
            allow_urls_as_data=policy.allow_urls_as_data,
            block_on_evidence_security_warning=(
                policy.block_on_evidence_security_warning
            ),
            allow_whole_target_locator=policy.allow_whole_target_locator,
        )
    except (TypeError, ValueError):
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)
    if rebuilt != policy:
        _raise_security(ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH)


def _disposition(
    signals: tuple[ReviewSecuritySignal, ...],
    policy: ReviewSecurityPolicy,
) -> ReviewSecurityDisposition:
    disposition = ReviewSecurityDisposition.ALLOW
    for signal in signals:
        candidate = _signal_disposition(signal, policy)
        if _DISPOSITION_RANK[candidate] > _DISPOSITION_RANK[disposition]:
            disposition = candidate
    return disposition


_DISPOSITION_RANK = {
    ReviewSecurityDisposition.ALLOW: 0,
    ReviewSecurityDisposition.ALLOW_WITH_WARNINGS: 1,
    ReviewSecurityDisposition.REPAIR_REQUIRED: 2,
    ReviewSecurityDisposition.REJECT: 3,
}


def _signal_disposition(
    signal: ReviewSecuritySignal,
    policy: ReviewSecurityPolicy,
) -> ReviewSecurityDisposition:
    code = signal.code
    if code is ReviewSecuritySignalCode.TARGET_PRIVILEGE_ESCALATION_TEXT:
        return (
            ReviewSecurityDisposition.REJECT
            if policy.block_on_privilege_escalation
            else ReviewSecurityDisposition.ALLOW_WITH_WARNINGS
        )
    if code is ReviewSecuritySignalCode.TARGET_EXFILTRATION_TEXT:
        return (
            ReviewSecurityDisposition.REJECT
            if policy.block_on_exfiltration
            else ReviewSecurityDisposition.ALLOW_WITH_WARNINGS
        )
    if code is ReviewSecuritySignalCode.TARGET_TOOL_OR_FILE_ACTION_TEXT:
        return (
            ReviewSecurityDisposition.REJECT
            if policy.block_on_tool_file_action
            else ReviewSecurityDisposition.ALLOW_WITH_WARNINGS
        )
    if code is ReviewSecuritySignalCode.TARGET_INSTRUCTION_LIKE_CONTENT:
        return (
            ReviewSecurityDisposition.REPAIR_REQUIRED
            if policy.block_on_target_instruction
            else ReviewSecurityDisposition.ALLOW_WITH_WARNINGS
        )
    if code is ReviewSecuritySignalCode.TARGET_URL_PRESENT:
        return (
            ReviewSecurityDisposition.ALLOW_WITH_WARNINGS
            if policy.allow_urls_as_data
            else ReviewSecurityDisposition.REPAIR_REQUIRED
        )
    if code is ReviewSecuritySignalCode.EVIDENCE_SECURITY_WARNING_PRESENT:
        return (
            ReviewSecurityDisposition.REPAIR_REQUIRED
            if policy.block_on_evidence_security_warning
            else ReviewSecurityDisposition.ALLOW_WITH_WARNINGS
        )
    if code is ReviewSecuritySignalCode.TARGET_AUTHORITY_CLAIM:
        return ReviewSecurityDisposition.REPAIR_REQUIRED
    return ReviewSecurityDisposition.REJECT


def _validate_ref_tuple(values: tuple[ContractRef, ...]) -> None:
    if type(values) is not tuple:
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)
    try:
        for value in values:
            require_contract_ref(value, "review_evidence_ref")
    except (TypeError, ValueError):
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)
    if len(values) != len(set(values)):
        _raise_security(ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH)


def _authority_free_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        frozen = freeze_agent_safe_mapping(value)
    except (TypeError, ValueError):
        _raise_security(ReviewSecuritySignalCode.AUTHORITY_METADATA_FORBIDDEN)
    reject_review_authority(frozen)
    return frozen


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(
            text
            for key, nested in value.items()
            for text in (key, *_string_values(nested))
        )
    if type(value) is tuple:
        return tuple(text for nested in value for text in _string_values(nested))
    return (value,) if type(value) is str else ()


def _contains_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = text.casefold()
    return any(pattern in normalized for pattern in patterns)


def _contains_url(text: str) -> bool:
    normalized = text.casefold()
    return "http://" in normalized or "https://" in normalized


def _canonical_value(value: object) -> object:
    if isinstance(value, Mapping):
        return tuple(
            (key, _canonical_value(nested))
            for key, nested in sorted(value.items())
        )
    if type(value) is tuple:
        return tuple(_canonical_value(nested) for nested in value)
    return value


def _raise_security(code: ReviewSecuritySignalCode) -> NoReturn:
    raise ReviewSecurityError(code) from None
