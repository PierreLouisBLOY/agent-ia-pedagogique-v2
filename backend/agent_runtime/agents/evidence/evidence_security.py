from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.agents.evidence.evidence_security_model import (
    EvidenceSecurityAssessment,
    EvidenceSecuritySignal,
    EvidenceSecuritySignalCode,
)
from backend.agent_runtime.contracts.evidence import EvidenceItem, EvidenceSet

_CONTENT_PATTERNS: tuple[
    tuple[EvidenceSecuritySignalCode, tuple[str, ...]], ...
] = (
    (
        EvidenceSecuritySignalCode.INSTRUCTION_LIKE_CONTENT,
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
        EvidenceSecuritySignalCode.PRIVILEGE_ESCALATION_TEXT,
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
        EvidenceSecuritySignalCode.EXFILTRATION_TEXT,
        (
            "reveal secret",
            "show api key",
            "send secrets",
            "envoie les secrets",
            "révèle le secret",
        ),
    ),
    (
        EvidenceSecuritySignalCode.TOOL_OR_FILE_ACTION_TEXT,
        (
            "call this tool",
            "appelle cet outil",
            "read this file",
            "lis ce fichier",
            "open this path",
            "ouvre ce chemin",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class EvidenceSecurityScanner:
    def assess(self, *, evidence_set: EvidenceSet) -> EvidenceSecurityAssessment:
        if type(evidence_set) is not EvidenceSet:
            raise TypeError("evidence_set must be an EvidenceSet")
        items = evidence_set.evidence_items
        evidence_ids = tuple(item.evidence_id for item in items)
        signals: list[EvidenceSecuritySignal] = []

        for code, patterns in _CONTENT_PATTERNS:
            matching_ids = tuple(
                item.evidence_id
                for item in items
                if _contains_pattern(item.excerpt_or_summary, patterns)
            )
            _append_signal(
                signals,
                code=code,
                evidence_ids=matching_ids,
                reason_code="CLOSED_PATTERN_MATCH",
            )

        url_ids = tuple(
            item.evidence_id
            for item in items
            if _contains_url_marker(item.excerpt_or_summary)
        )
        _append_signal(
            signals,
            code=EvidenceSecuritySignalCode.URL_PRESENT,
            evidence_ids=url_ids,
            reason_code="HTTP_URL_MARKER_PRESENT",
        )

        unattributed_warning_limitations = _append_upstream_warning_signals(
            signals,
            evidence_set.limitations,
            evidence_ids,
        )
        _append_stale_signals(signals, evidence_set.limitations, evidence_ids)
        _append_version_conflict_signals(
            signals,
            evidence_set.conflicts,
            evidence_ids,
        )

        corroboration_groups = _corroboration_groups(items)
        for group in corroboration_groups:
            if len(group) > 1:
                _append_signal(
                    signals,
                    code=EvidenceSecuritySignalCode.DUPLICATE_CORROBORATION,
                    evidence_ids=group,
                    reason_code="SAME_SOURCE_LOCATOR_VERSION",
                )
        for duplicate_ids in _cross_source_duplicate_groups(items):
            _append_signal(
                signals,
                code=EvidenceSecuritySignalCode.CROSS_SOURCE_DUPLICATE_CONTENT,
                evidence_ids=duplicate_ids,
                reason_code="EXACT_CONTENT_AND_VERSION_MATCH",
            )

        suspicious_set = {
            evidence_id for signal in signals for evidence_id in signal.evidence_ids
        }
        suspicious_ids = tuple(
            evidence_id for evidence_id in evidence_ids if evidence_id in suspicious_set
        )
        return EvidenceSecurityAssessment(
            signals=tuple(signals),
            suspicious_evidence_ids=suspicious_ids,
            independent_corroboration_groups=corroboration_groups,
            document_instructions_authoritative=False,
            external_actions_allowed=False,
            links_followed=False,
            limitations=(
                "SECURITY_SIGNALS_ARE_INDICATORS_ONLY",
                "DOCUMENT_INSTRUCTIONS_NON_AUTHORITATIVE",
                "EXTERNAL_ACTIONS_DISABLED",
                "LINKS_NOT_FOLLOWED",
                *unattributed_warning_limitations,
            ),
        )


def _contains_pattern(text: str | None, patterns: tuple[str, ...]) -> bool:
    if text is None:
        return False
    normalized = text.casefold()
    return any(pattern in normalized for pattern in patterns)


def _contains_url_marker(text: str | None) -> bool:
    if text is None:
        return False
    normalized = text.casefold()
    return "http://" in normalized or "https://" in normalized


def _append_signal(
    signals: list[EvidenceSecuritySignal],
    *,
    code: EvidenceSecuritySignalCode,
    evidence_ids: tuple[str, ...],
    reason_code: str,
) -> None:
    if not evidence_ids:
        return
    signal = EvidenceSecuritySignal(code, evidence_ids, reason_code)
    if signal not in signals:
        signals.append(signal)


def _limitation_code(limitation: Mapping[str, object]) -> str | None:
    code = limitation.get("code")
    return code if isinstance(code, str) and code else None


def _attributed_ids(
    limitation: Mapping[str, object],
    known_ids: tuple[str, ...],
) -> tuple[str, ...]:
    evidence_id = limitation.get("evidence_id")
    raw_ids = limitation.get("evidence_ids")
    if isinstance(evidence_id, str):
        requested = (evidence_id,)
    elif isinstance(raw_ids, tuple) and all(
        isinstance(item, str) for item in raw_ids
    ):
        requested = raw_ids
    else:
        return ()
    requested_set = set(requested)
    if not requested_set.issubset(known_ids):
        return ()
    return tuple(item for item in known_ids if item in requested_set)


def _append_upstream_warning_signals(
    signals: list[EvidenceSecuritySignal],
    limitations: tuple[Mapping[str, object], ...],
    evidence_ids: tuple[str, ...],
) -> tuple[str, ...]:
    unattributed_limitations: list[str] = []
    for limitation in limitations:
        code = _limitation_code(limitation)
        if code is None or not code.startswith("SECURITY_WARNING:"):
            continue
        warning_code = code.removeprefix("SECURITY_WARNING:")
        if not warning_code:
            continue
        attributed = _attributed_ids(limitation, evidence_ids)
        if attributed:
            _append_signal(
                signals,
                code=EvidenceSecuritySignalCode.UPSTREAM_SECURITY_WARNING,
                evidence_ids=attributed,
                reason_code=warning_code,
            )
            continue
        global_limitation = (
            f"UNATTRIBUTED_UPSTREAM_SECURITY_WARNING:{warning_code}"
        )
        if global_limitation not in unattributed_limitations:
            unattributed_limitations.append(global_limitation)
    return tuple(unattributed_limitations)


def _append_stale_signals(
    signals: list[EvidenceSecuritySignal],
    limitations: tuple[Mapping[str, object], ...],
    evidence_ids: tuple[str, ...],
) -> None:
    for limitation in limitations:
        if _limitation_code(limitation) != "SOURCE_REPORTED_STALE":
            continue
        attributed = _attributed_ids(limitation, evidence_ids)
        _append_signal(
            signals,
            code=EvidenceSecuritySignalCode.SOURCE_REPORTED_STALE,
            evidence_ids=attributed,
            reason_code="UPSTREAM_SOURCE_REPORTED_STALE",
        )


def _append_version_conflict_signals(
    signals: list[EvidenceSecuritySignal],
    conflicts: tuple[Mapping[str, object], ...],
    evidence_ids: tuple[str, ...],
) -> None:
    for conflict in conflicts:
        if conflict.get("type") != "VERSION_DIVERGENCE":
            continue
        raw_ids = conflict.get("evidence_ids")
        if not isinstance(raw_ids, tuple):
            continue
        raw_id_set = {item for item in raw_ids if isinstance(item, str)}
        attributed = tuple(item for item in evidence_ids if item in raw_id_set)
        _append_signal(
            signals,
            code=EvidenceSecuritySignalCode.VERSION_DIVERGENCE,
            evidence_ids=attributed,
            reason_code="EVIDENCE_SET_VERSION_DIVERGENCE",
        )


def _corroboration_groups(
    items: tuple[EvidenceItem, ...],
) -> tuple[tuple[str, ...], ...]:
    groups: list[list[str]] = []
    group_index_by_origin: dict[tuple[object, str, str | None], int] = {}
    for item in items:
        origin = (item.source_ref, item.locator, item.checksum_or_version)
        index = group_index_by_origin.get(origin)
        if index is None:
            group_index_by_origin[origin] = len(groups)
            groups.append([item.evidence_id])
        else:
            groups[index].append(item.evidence_id)
    return tuple(tuple(group) for group in groups)


def _cross_source_duplicate_groups(
    items: tuple[EvidenceItem, ...],
) -> tuple[tuple[str, ...], ...]:
    matches: list[tuple[str, ...]] = []
    for index, first in enumerate(items):
        if first.excerpt_or_summary is None or first.checksum_or_version is None:
            continue
        for second in items[index + 1 :]:
            if (
                first.source_ref != second.source_ref
                and first.excerpt_or_summary == second.excerpt_or_summary
                and first.checksum_or_version == second.checksum_or_version
            ):
                matches.append((first.evidence_id, second.evidence_id))
    return tuple(matches)
