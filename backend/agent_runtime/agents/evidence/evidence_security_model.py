from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts.security import ContentThreatSignalCode
from backend.shared_kernel._strings import require_non_empty


class EvidenceSecuritySignalCode(StrEnum):
    DUPLICATE_CORROBORATION = "DUPLICATE_CORROBORATION"
    CROSS_SOURCE_DUPLICATE_CONTENT = "CROSS_SOURCE_DUPLICATE_CONTENT"
    VERSION_DIVERGENCE = "VERSION_DIVERGENCE"
    SOURCE_REPORTED_STALE = "SOURCE_REPORTED_STALE"


type EvidenceSignalCode = EvidenceSecuritySignalCode | ContentThreatSignalCode


@dataclass(frozen=True, slots=True)
class EvidenceSecuritySignal:
    code: EvidenceSignalCode
    evidence_ids: tuple[str, ...]
    reason_code: str

    def __post_init__(self) -> None:
        if type(self.code) not in {EvidenceSecuritySignalCode, ContentThreatSignalCode}:
            raise TypeError("code must be an evidence or common content signal code")
        _validate_string_tuple(
            self.evidence_ids,
            "evidence_ids",
            allow_empty=False,
        )
        require_non_empty(self.reason_code, "reason_code")


@dataclass(frozen=True, slots=True)
class EvidenceSecurityAssessment:
    signals: tuple[EvidenceSecuritySignal, ...]
    suspicious_evidence_ids: tuple[str, ...]
    independent_corroboration_groups: tuple[tuple[str, ...], ...]
    document_instructions_authoritative: bool
    external_actions_allowed: bool
    links_followed: bool
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.signals, tuple) or any(
            type(signal) is not EvidenceSecuritySignal for signal in self.signals
        ):
            raise TypeError("signals must contain EvidenceSecuritySignal values")
        signal_keys = tuple(
            (signal.code, signal.evidence_ids, signal.reason_code)
            for signal in self.signals
        )
        if len(signal_keys) != len(set(signal_keys)):
            raise ValueError("signals must be unique")
        _validate_string_tuple(
            self.suspicious_evidence_ids,
            "suspicious_evidence_ids",
        )
        if not isinstance(self.independent_corroboration_groups, tuple):
            raise TypeError("independent_corroboration_groups must be a tuple")
        for group in self.independent_corroboration_groups:
            _validate_string_tuple(
                group,
                "independent corroboration group",
                allow_empty=False,
            )
        if len(self.independent_corroboration_groups) != len(
            set(self.independent_corroboration_groups)
        ):
            raise ValueError("independent corroboration groups must be unique")
        assessed_ids = tuple(
            evidence_id
            for group in self.independent_corroboration_groups
            for evidence_id in group
        )
        if len(assessed_ids) != len(set(assessed_ids)):
            raise ValueError("an evidence id must belong to exactly one group")
        assessed_id_set = set(assessed_ids)
        if any(
            evidence_id not in assessed_id_set
            for signal in self.signals
            for evidence_id in signal.evidence_ids
        ):
            raise ValueError("signal evidence ids must belong to the assessment")
        if any(
            evidence_id not in assessed_id_set
            for evidence_id in self.suspicious_evidence_ids
        ):
            raise ValueError("suspicious evidence ids must belong to the assessment")
        signaled_ids = {
            evidence_id
            for signal in self.signals
            for evidence_id in signal.evidence_ids
        }
        if set(self.suspicious_evidence_ids) != signaled_ids:
            raise ValueError("suspicious evidence ids must match signaled evidence")
        if self.document_instructions_authoritative is not False:
            raise ValueError("document instructions must remain non-authoritative")
        if self.external_actions_allowed is not False:
            raise ValueError("external actions must remain disabled")
        if self.links_followed is not False:
            raise ValueError("links must never be followed")
        _validate_string_tuple(self.limitations, "limitations")


def _validate_string_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool = True,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if not allow_empty and not values:
        raise ValueError(f"{field_name} must not be empty")
    for value in values:
        require_non_empty(value, f"{field_name} item")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be unique")
