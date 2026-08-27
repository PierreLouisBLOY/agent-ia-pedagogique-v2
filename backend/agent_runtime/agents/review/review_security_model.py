from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.agents.evidence.evidence_security_model import (
    EvidenceSecurityAssessment,
)
from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.security import ContentThreatSignalCode
from backend.shared_kernel.references import ObjectVersionRef


class ReviewSecuritySignalCode(StrEnum):
    LOCATOR_INVALID = "LOCATOR_INVALID"
    LOCATOR_OUT_OF_TARGET = "LOCATOR_OUT_OF_TARGET"
    LOCATOR_AMBIGUOUS = "LOCATOR_AMBIGUOUS"
    EVIDENCE_SECURITY_WARNING_PRESENT = "EVIDENCE_SECURITY_WARNING_PRESENT"
    EVIDENCE_SECURITY_SCOPE_MISMATCH = "EVIDENCE_SECURITY_SCOPE_MISMATCH"
    FINDING_LINEAGE_MISMATCH = "FINDING_LINEAGE_MISMATCH"
    ASSESSMENT_LINEAGE_MISMATCH = "ASSESSMENT_LINEAGE_MISMATCH"
    AUTHORITY_METADATA_FORBIDDEN = "AUTHORITY_METADATA_FORBIDDEN"


type ReviewSignalCode = ReviewSecuritySignalCode | ContentThreatSignalCode


class ReviewSecurityDisposition(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_WARNINGS = "ALLOW_WITH_WARNINGS"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    REJECT = "REJECT"


_SAFE_REASONS: Mapping[ReviewSignalCode, str] = {
    ContentThreatSignalCode.INSTRUCTION_LIKE_CONTENT: (
        "review target contains instruction-like data disallowed by policy"
    ),
    ContentThreatSignalCode.PRIVILEGE_ESCALATION_TEXT: (
        "review target contains privilege-escalation data"
    ),
    ContentThreatSignalCode.EXFILTRATION_TEXT: (
        "review target contains exfiltration-like data"
    ),
    ContentThreatSignalCode.TOOL_OR_FILE_ACTION_TEXT: (
        "review target contains tool or file action data"
    ),
    ContentThreatSignalCode.URL_PRESENT: (
        "review target contains URL data disallowed by policy"
    ),
    ContentThreatSignalCode.AUTHORITY_CLAIM_TEXT: (
        "review target contains a non-authoritative authority claim"
    ),
    ContentThreatSignalCode.UPSTREAM_SECURITY_WARNING: (
        "review target carries an upstream security warning"
    ),
    ContentThreatSignalCode.ROLE_CONFUSION: (
        "review target role conflicts with its content boundary"
    ),
    ReviewSecuritySignalCode.LOCATOR_INVALID: (
        "finding locator does not match the closed review locator schema"
    ),
    ReviewSecuritySignalCode.LOCATOR_OUT_OF_TARGET: (
        "finding locator does not resolve inside the exact review target"
    ),
    ReviewSecuritySignalCode.LOCATOR_AMBIGUOUS: (
        "finding locator is ambiguous for the exact review target"
    ),
    ReviewSecuritySignalCode.EVIDENCE_SECURITY_WARNING_PRESENT: (
        "review evidence carries a security warning disallowed by policy"
    ),
    ReviewSecuritySignalCode.EVIDENCE_SECURITY_SCOPE_MISMATCH: (
        "evidence security assessment does not match review evidence scope"
    ),
    ReviewSecuritySignalCode.FINDING_LINEAGE_MISMATCH: (
        "finding lineage does not match the source review"
    ),
    ReviewSecuritySignalCode.ASSESSMENT_LINEAGE_MISMATCH: (
        "security assessment lineage does not match the review target"
    ),
    ReviewSecuritySignalCode.AUTHORITY_METADATA_FORBIDDEN: (
        "review data contains forbidden authority metadata"
    ),
}


class ReviewSecurityError(ValueError):
    code: ReviewSignalCode
    safe_reason: str

    def __init__(self, code: ReviewSignalCode) -> None:
        if type(code) not in {ReviewSecuritySignalCode, ContentThreatSignalCode}:
            raise TypeError("code must be a review or common content signal code")
        self.code = code
        self.safe_reason = _SAFE_REASONS[code]
        super().__init__(self.safe_reason)


@dataclass(frozen=True, slots=True)
class ReviewSecurityPolicy:
    require_locator_validation: bool = True
    require_evidence_security_assessment: bool = False
    block_on_target_instruction: bool = False
    block_on_privilege_escalation: bool = False
    block_on_exfiltration: bool = False
    block_on_tool_file_action: bool = False
    allow_urls_as_data: bool = True
    block_on_evidence_security_warning: bool = False
    allow_whole_target_locator: bool = False

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (
                self.require_locator_validation,
                self.require_evidence_security_assessment,
                self.block_on_target_instruction,
                self.block_on_privilege_escalation,
                self.block_on_exfiltration,
                self.block_on_tool_file_action,
                self.allow_urls_as_data,
                self.block_on_evidence_security_warning,
                self.allow_whole_target_locator,
            )
        ):
            raise TypeError("review security policy values must be bool")


@dataclass(frozen=True, slots=True)
class LocatorValidationResult:
    kind: str
    normalized_locator: tuple[object, ...]

    def __post_init__(self) -> None:
        if self.kind not in {"text_span", "json_path", "whole_target"}:
            raise ValueError("locator result kind must be closed")
        if type(self.normalized_locator) is not tuple or not self.normalized_locator:
            raise ValueError("normalized_locator must be a non-empty tuple")


@dataclass(frozen=True, slots=True)
class ReviewSecuritySignal:
    code: ReviewSignalCode
    evidence_refs: tuple[ContractRef, ...] = ()
    location_kind: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) not in {ReviewSecuritySignalCode, ContentThreatSignalCode}:
            raise TypeError("code must be a review or common content signal code")
        if type(self.evidence_refs) is not tuple:
            raise TypeError("evidence_refs must be a tuple")
        for evidence_ref in self.evidence_refs:
            require_contract_ref(evidence_ref, "security_evidence_ref")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique")
        if self.location_kind not in {None, "text", "payload", "evidence"}:
            raise ValueError("location_kind must be a closed safe locator")


@dataclass(frozen=True, slots=True)
class ReviewSecurityAssessment:
    target_production_ref: ObjectVersionRef
    target_snapshot_fingerprint: str
    disposition: ReviewSecurityDisposition
    signals: tuple[ReviewSecuritySignal, ...]
    evidence_refs_assessed: tuple[ContractRef, ...]
    warnings: tuple[Mapping[str, object], ...]
    limitations: tuple[Mapping[str, object], ...]
    document_instructions_authoritative: bool = False
    external_actions_allowed: bool = False
    links_followed: bool = False

    def __post_init__(self) -> None:
        if type(self.target_production_ref) is not ObjectVersionRef:
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        if type(self.target_snapshot_fingerprint) is not str or not self.target_snapshot_fingerprint:
            raise ValueError("target_snapshot_fingerprint must be non-empty")
        if type(self.disposition) is not ReviewSecurityDisposition:
            raise TypeError("disposition must be a ReviewSecurityDisposition")
        if type(self.signals) is not tuple or any(
            type(signal) is not ReviewSecuritySignal for signal in self.signals
        ):
            raise TypeError("signals must contain ReviewSecuritySignal values")
        if len(self.signals) != len(set(self.signals)):
            raise ValueError("signals must be unique")
        if type(self.evidence_refs_assessed) is not tuple or len(
            self.evidence_refs_assessed
        ) != len(set(self.evidence_refs_assessed)):
            raise ValueError("evidence_refs_assessed must be a unique tuple")
        for evidence_ref in self.evidence_refs_assessed:
            require_contract_ref(evidence_ref, "assessed_evidence_ref")
        if type(self.warnings) is not tuple or type(self.limitations) is not tuple:
            raise TypeError("security diagnostics must be tuples")
        if any(not isinstance(item, Mapping) for item in self.warnings + self.limitations):
            raise TypeError("security diagnostics must contain mappings")
        if self.document_instructions_authoritative is not False:
            raise ValueError("document instructions must remain non-authoritative")
        if self.external_actions_allowed is not False:
            raise ValueError("external actions must remain disabled")
        if self.links_followed is not False:
            raise ValueError("links must never be followed")
        object.__setattr__(
            self,
            "warnings",
            tuple(freeze_agent_safe_mapping(item) for item in self.warnings),
        )
        object.__setattr__(
            self,
            "limitations",
            tuple(freeze_agent_safe_mapping(item) for item in self.limitations),
        )


EvidenceSecurityByRef = Mapping[ContractRef, EvidenceSecurityAssessment]
