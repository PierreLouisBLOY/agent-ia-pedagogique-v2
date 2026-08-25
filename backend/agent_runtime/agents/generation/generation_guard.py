from __future__ import annotations

import re
from collections.abc import Iterator, Mapping

from backend.agent_runtime.agents.generation.generation_coordination_model import (
    PreparedGenerationCall,
)
from backend.agent_runtime.agents.generation.generation_guard_model import (
    GenerationGuardAssessment,
    GenerationGuardDisposition,
    GenerationGuardError,
    GenerationGuardIssueCode,
    GenerationGuardRequest,
    GenerationRepairKind,
    GenerationRepairProposal,
    GenerationSecuritySignal,
    GenerationSecuritySignalCode,
    validate_generation_guard_request,
)
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationPortResultStatus,
)

_SECURITY_PATTERNS: Mapping[GenerationSecuritySignalCode, tuple[str, ...]] = {
    GenerationSecuritySignalCode.INSTRUCTION_LIKE_CONTENT: (
        "ignore previous instructions",
        "ignore all instructions",
        "disregard prior instructions",
        "system prompt",
        "ignore les instructions",
        "instructions précédentes",
        "ne tiens pas compte des instructions",
    ),
    GenerationSecuritySignalCode.PRIVILEGE_ESCALATION_TEXT: (
        "administrator privileges",
        "admin privileges",
        "elevated privileges",
        "root access",
        "droits administrateur",
        "privilèges élevés",
        "contourne les permissions",
        "bypass permissions",
        "sudo ",
    ),
    GenerationSecuritySignalCode.EXFILTRATION_TEXT: (
        "exfiltrate",
        "send secrets",
        "steal data",
        "upload credentials",
        "send data to",
        "exfiltrer",
        "envoyer les secrets",
        "extraire les données",
    ),
    GenerationSecuritySignalCode.TOOL_OR_FILE_ACTION_TEXT: (
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
    GenerationSecuritySignalCode.AUTHORITY_CLAIM_TEXT: (
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
    ),
}
_URL_PATTERN = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
_SAFE_LOCATION_SEGMENT = re.compile(r"[A-Za-z0-9_-]{1,64}")
_REJECT_ISSUES = frozenset(
    {
        GenerationGuardIssueCode.PREPARED_LINEAGE_MISMATCH,
        GenerationGuardIssueCode.TECHNICAL_RESULT_MISMATCH,
        GenerationGuardIssueCode.CLAIM_EVIDENCE_OUT_OF_SCOPE,
        GenerationGuardIssueCode.DUPLICATE_CLAIM_ID,
        GenerationGuardIssueCode.UNEXPECTED_PAYLOAD_KEY,
    }
)
_REPAIR_ISSUES = frozenset(
    {
        GenerationGuardIssueCode.STRUCTURED_PAYLOAD_REQUIRED,
        GenerationGuardIssueCode.REQUIRED_PAYLOAD_KEY_MISSING,
        GenerationGuardIssueCode.EXPECTED_SECTION_CONTAINER_MISSING,
        GenerationGuardIssueCode.EXPECTED_SECTION_MISSING,
    }
)
_ISSUE_ORDER = {value: index for index, value in enumerate(GenerationGuardIssueCode)}
_SIGNAL_ORDER = {
    value: index for index, value in enumerate(GenerationSecuritySignalCode)
}


class GenerationOutputGuard:
    __slots__ = ()

    def assess(
        self,
        *,
        request: GenerationGuardRequest,
    ) -> GenerationGuardAssessment:
        if type(request) is not GenerationGuardRequest:
            raise TypeError("request must be a GenerationGuardRequest")
        validate_generation_guard_request(request)
        return _build_generation_guard_assessment(request)


def validate_generation_guard_assessment(
    assessment: GenerationGuardAssessment,
) -> None:
    if type(assessment) is not GenerationGuardAssessment:
        raise TypeError("assessment must be a GenerationGuardAssessment")
    validate_generation_guard_request(assessment.request)
    expected = _build_generation_guard_assessment(assessment.request)
    if assessment != expected:
        raise GenerationGuardError(
            GenerationGuardIssueCode.TECHNICAL_RESULT_MISMATCH,
            "generation guard assessment does not match deterministic recomputation",
        )


def generation_guard_security_warnings(
    assessment: GenerationGuardAssessment,
) -> tuple[Mapping[str, object], ...]:
    validate_generation_guard_assessment(assessment)
    return tuple(
        {
            "code": signal.code.value,
            "origin": "AG03_OUTPUT_GUARD",
            "location": signal.location,
        }
        for signal in assessment.security_signals
    )


def _build_generation_guard_assessment(
    request: GenerationGuardRequest,
) -> GenerationGuardAssessment:
    technical = request.technical_result
    policy = request.policy
    issues: set[GenerationGuardIssueCode] = set()

    claim_ids = tuple(item.claim_id for item in request.claim_attributions)
    if len(claim_ids) != len(set(claim_ids)):
        issues.add(GenerationGuardIssueCode.DUPLICATE_CLAIM_ID)
    used_evidence = set(technical.evidence_refs_used)
    if any(
        not set(attribution.evidence_refs).issubset(used_evidence)
        for attribution in request.claim_attributions
    ):
        issues.add(GenerationGuardIssueCode.CLAIM_EVIDENCE_OUT_OF_SCOPE)

    if policy.grounding_required and not technical.evidence_refs_used:
        issues.add(GenerationGuardIssueCode.GROUNDING_REQUIRED_NO_EVIDENCE)

    payload = technical.structured_payload
    if policy.require_structured_payload and not payload:
        issues.add(GenerationGuardIssueCode.STRUCTURED_PAYLOAD_REQUIRED)
    if any(key not in payload for key in policy.required_payload_keys):
        issues.add(GenerationGuardIssueCode.REQUIRED_PAYLOAD_KEY_MISSING)
    if policy.allowed_payload_keys is not None and any(
        key not in policy.allowed_payload_keys for key in payload
    ):
        issues.add(GenerationGuardIssueCode.UNEXPECTED_PAYLOAD_KEY)
    if (
        policy.section_container_key is not None
        and type(request.prepared) is PreparedGenerationCall
        and request.prepared.canonical_request.expected_sections
    ):
        section_container = payload.get(policy.section_container_key)
        if not isinstance(section_container, Mapping):
            issues.add(
                GenerationGuardIssueCode.EXPECTED_SECTION_CONTAINER_MISSING
            )
        elif any(
            section not in section_container
            for section in request.prepared.canonical_request.expected_sections
        ):
            issues.add(GenerationGuardIssueCode.EXPECTED_SECTION_MISSING)

    security_signals = _scan_security_signals(technical.content, payload)
    disposition = _disposition_for(
        issues,
        technical.status,
        has_security_signals=bool(security_signals),
    )
    ordered_issues = tuple(sorted(issues, key=_ISSUE_ORDER.__getitem__))
    repair_proposal = (
        GenerationRepairProposal(
            kind=GenerationRepairKind.STRUCTURE_REPAIR,
            issue_codes=ordered_issues,
        )
        if disposition is GenerationGuardDisposition.REPAIR_REQUIRED
        else None
    )
    return GenerationGuardAssessment(
        request=request,
        disposition=disposition,
        issue_codes=ordered_issues,
        security_signals=security_signals,
        repair_proposal=repair_proposal,
    )


def _disposition_for(
    issues: set[GenerationGuardIssueCode],
    status: GenerationPortResultStatus,
    *,
    has_security_signals: bool,
) -> GenerationGuardDisposition:
    if issues.intersection(_REJECT_ISSUES):
        return GenerationGuardDisposition.REJECT
    if (
        status
        in {
            GenerationPortResultStatus.REFUSED,
            GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
        }
        or GenerationGuardIssueCode.GROUNDING_REQUIRED_NO_EVIDENCE in issues
    ):
        return GenerationGuardDisposition.ABSTAIN
    if issues.intersection(_REPAIR_ISSUES):
        return GenerationGuardDisposition.REPAIR_REQUIRED
    if status is GenerationPortResultStatus.PARTIAL or has_security_signals:
        return GenerationGuardDisposition.ALLOW_WITH_WARNINGS
    return GenerationGuardDisposition.ALLOW


def _scan_security_signals(
    content: str | None,
    structured_payload: Mapping[str, object],
) -> tuple[GenerationSecuritySignal, ...]:
    signals: set[GenerationSecuritySignal] = set()
    leaves: list[tuple[str, str]] = []
    if content is not None:
        leaves.append(("content", content))
    leaves.extend(_string_leaves(structured_payload, ("structured_payload",)))
    for location, value in leaves:
        folded = value.casefold()
        for code, patterns in _SECURITY_PATTERNS.items():
            if any(pattern in folded for pattern in patterns):
                signals.add(GenerationSecuritySignal(code, location))
        if _URL_PATTERN.findall(value):
            signals.add(
                GenerationSecuritySignal(
                    GenerationSecuritySignalCode.URL_PRESENT,
                    location,
                )
            )
    return tuple(
        sorted(
            signals,
            key=lambda signal: (_SIGNAL_ORDER[signal.code], signal.location),
        )
    )


def _string_leaves(
    value: object,
    path: tuple[str, ...],
) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield (_bounded_location(path), value)
    elif isinstance(value, Mapping):
        for index, (key, nested) in enumerate(sorted(value.items())):
            segment = key if _SAFE_LOCATION_SEGMENT.fullmatch(key) else f"field_{index}"
            yield from _string_leaves(nested, (*path, segment))
    elif isinstance(value, tuple):
        for index, nested in enumerate(value):
            yield from _string_leaves(nested, (*path, str(index)))


def _bounded_location(path: tuple[str, ...]) -> str:
    location = ".".join(path)
    if len(location) <= 512:
        return location
    return f"structured_payload.deep.{len(path)}"
