from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts.common import ContractRef, require_contract_ref
from backend.agent_runtime.contracts.security.security_event import SecurityReasonCode
from backend.agent_runtime.contracts.security.trust import ContentTrustLabel
from backend.shared_kernel._strings import require_non_empty


class ContentThreatSignalCode(StrEnum):
    INSTRUCTION_LIKE_CONTENT = "INSTRUCTION_LIKE_CONTENT"
    PRIVILEGE_ESCALATION_TEXT = "PRIVILEGE_ESCALATION_TEXT"
    EXFILTRATION_TEXT = "EXFILTRATION_TEXT"
    TOOL_OR_FILE_ACTION_TEXT = "TOOL_OR_FILE_ACTION_TEXT"
    URL_PRESENT = "URL_PRESENT"
    AUTHORITY_CLAIM_TEXT = "AUTHORITY_CLAIM_TEXT"
    UPSTREAM_SECURITY_WARNING = "UPSTREAM_SECURITY_WARNING"
    ROLE_CONFUSION = "ROLE_CONFUSION"


@dataclass(frozen=True, slots=True)
class ContentThreatSignal:
    code: ContentThreatSignalCode
    content_ref: ContractRef
    logical_location: str

    def __post_init__(self) -> None:
        if type(self.code) is not ContentThreatSignalCode:
            raise TypeError("code must be a ContentThreatSignalCode")
        require_contract_ref(self.content_ref, "content_ref")
        _require_safe_logical_location(self.logical_location)


@dataclass(frozen=True, slots=True)
class LabeledContent:
    """Working content whose provenance is descriptive and non-authoritative."""

    content_id: str
    text: str
    label: ContentTrustLabel
    content_ref: ContractRef

    def __post_init__(self) -> None:
        _require_safe_identifier(self.content_id, "content_id")
        require_non_empty(self.text, "text")
        if type(self.label) is not ContentTrustLabel:
            raise TypeError("label must be a ContentTrustLabel")
        require_contract_ref(self.content_ref, "content_ref")


class ContentSecurityDisposition(StrEnum):
    PASS_AS_DATA = "PASS_AS_DATA"
    ISOLATE_AS_DATA = "ISOLATE_AS_DATA"
    QUARANTINE = "QUARANTINE"
    REJECT_CONTENT = "REJECT_CONTENT"
    ESCALATE_REVIEW = "ESCALATE_REVIEW"


@dataclass(frozen=True, slots=True)
class ContentSecurityAssessment:
    content_ref: ContractRef
    label: ContentTrustLabel
    disposition: ContentSecurityDisposition
    signals: tuple[ContentThreatSignal, ...]
    reason_codes: tuple[SecurityReasonCode, ...]

    def __post_init__(self) -> None:
        require_contract_ref(self.content_ref, "content_ref")
        if type(self.label) is not ContentTrustLabel:
            raise TypeError("label must be a ContentTrustLabel")
        if type(self.disposition) is not ContentSecurityDisposition:
            raise TypeError("disposition must be a ContentSecurityDisposition")
        if type(self.signals) is not tuple or any(
            type(signal) is not ContentThreatSignal for signal in self.signals
        ):
            raise TypeError("signals must contain ContentThreatSignal values")
        if len(self.signals) != len(set(self.signals)):
            raise ValueError("signals must be unique")
        if any(signal.content_ref != self.content_ref for signal in self.signals):
            raise ValueError("signals must reference the assessed content")
        if type(self.reason_codes) is not tuple or any(
            type(code) is not SecurityReasonCode for code in self.reason_codes
        ):
            raise TypeError("reason_codes must contain SecurityReasonCode values")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason_codes must be unique")
        if self.disposition is ContentSecurityDisposition.PASS_AS_DATA and (
            self.signals or self.reason_codes
        ):
            raise ValueError("PASS_AS_DATA cannot carry security findings")
        if (
            self.disposition is not ContentSecurityDisposition.PASS_AS_DATA
            and not self.signals
        ):
            raise ValueError("non-pass disposition requires at least one signal")
        if not self.signals and self.reason_codes:
            raise ValueError("reason codes require at least one signal")
        if self.signals and not self.reason_codes:
            raise ValueError("signals require at least one reason code")


def _require_safe_identifier(value: str, field_name: str) -> None:
    require_non_empty(value, field_name)
    if not _is_safe_opaque_value(value, max_length=128):
        raise ValueError(f"{field_name} must be a bounded opaque safe identifier")


def _require_safe_logical_location(value: str) -> None:
    require_non_empty(value, "logical_location")
    if not _is_safe_opaque_value(value, max_length=512):
        raise ValueError("logical_location must be a bounded logical identifier")


def _is_safe_opaque_value(value: str, *, max_length: int) -> bool:
    return bool(
        1 <= len(value) <= max_length
        and _is_ascii_alphanumeric(value[0])
        and all(
            _is_ascii_alphanumeric(character) or character in "._:-"
            for character in value[1:]
        )
    )


def _is_ascii_alphanumeric(character: str) -> bool:
    return (
        "A" <= character <= "Z"
        or "a" <= character <= "z"
        or "0" <= character <= "9"
    )
