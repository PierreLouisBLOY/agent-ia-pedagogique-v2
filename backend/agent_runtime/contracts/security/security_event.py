from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ContractRef,
    ContractSchemaVersion,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.security.trust import (
    ContentTrustLabel,
    SecurityBoundary,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_MAX_REFS = 16
_MAX_METADATA_KEYS = 32
_FORBIDDEN_RAW_METADATA_KEYS = frozenset(
    {
        "application_output",
        "content",
        "credential",
        "credentials",
        "description",
        "document",
        "idempotency_key",
        "message",
        "payload",
        "prompt",
        "provider_response",
        "raw_document",
        "raw_content",
        "raw_idempotency_key",
        "raw_payload",
        "raw_prompt",
        "summary",
        "tool_output",
        "tool_payload",
    }
)


class SecurityEventType(StrEnum):
    DIRECT_PROMPT_INJECTION = "direct_prompt_injection"
    INDIRECT_CONTENT_INJECTION = "indirect_content_injection"
    TOOL_INJECTION = "tool_injection"
    APPLICATION_INJECTION = "application_injection"
    AGENT_HANDOFF_VIOLATION = "agent_handoff_violation"
    AUTHORITY_SMUGGLING = "authority_smuggling"
    SECRET_EXFILTRATION_ATTEMPT = "secret_exfiltration_attempt"
    SECRET_EXPOSURE = "secret_exposure"
    HOSTILE_CONTENT_PROPAGATION = "hostile_content_propagation"
    TRUST_BOUNDARY_VIOLATION = "trust_boundary_violation"
    INPUT_LIMIT_EXCEEDED = "input_limit_exceeded"


class SecuritySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class SecurityReasonCode:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("value must be a string")
        if not _is_reason_code(self.value):
            raise ValueError("value must be a safe closed security reason code")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """Minimal immutable security fact; no raw content or authority decision."""

    schema_version: ContractSchemaVersion
    event_id: str
    event_type: SecurityEventType
    severity: SecuritySeverity
    boundary: SecurityBoundary
    reason_code: SecurityReasonCode
    occurred_at: Instant
    run_id: str
    correlation_id: CorrelationId
    step_id: str | None = None
    refs: tuple[ContractRef, ...] = ()
    content_label: ContentTrustLabel | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, ContractSchemaVersion):
            raise TypeError("schema_version must be a ContractSchemaVersion")
        _require_safe_identifier(self.event_id, "event_id")
        if not isinstance(self.event_type, SecurityEventType):
            raise TypeError("event_type must be a SecurityEventType")
        if not isinstance(self.severity, SecuritySeverity):
            raise TypeError("severity must be a SecuritySeverity")
        if not isinstance(self.boundary, SecurityBoundary):
            raise TypeError("boundary must be a SecurityBoundary")
        if not isinstance(self.reason_code, SecurityReasonCode):
            raise TypeError("reason_code must be a SecurityReasonCode")
        if not isinstance(self.occurred_at, Instant):
            raise TypeError("occurred_at must be an Instant")
        if self.occurred_at.value.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be UTC")
        _require_safe_identifier(self.run_id, "run_id")
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        if self.step_id is not None:
            _require_safe_identifier(self.step_id, "step_id")
        if self.content_label is not None and not isinstance(
            self.content_label, ContentTrustLabel
        ):
            raise TypeError("content_label must be a ContentTrustLabel")

        if not isinstance(self.refs, tuple):
            raise TypeError("refs must be an immutable tuple")
        if len(self.refs) > _MAX_REFS:
            raise ValueError(f"refs must contain at most {_MAX_REFS} items")
        for ref in self.refs:
            _require_security_ref(ref)
        if len(set(self.refs)) != len(self.refs):
            raise ValueError("refs must be unique")

        safe_metadata = freeze_agent_safe_mapping(self.metadata)
        if len(safe_metadata) > _MAX_METADATA_KEYS:
            raise ValueError(
                f"metadata must contain at most {_MAX_METADATA_KEYS} top-level keys"
            )
        _reject_raw_event_data_keys(safe_metadata)
        object.__setattr__(self, "metadata", safe_metadata)


def _require_safe_identifier(value: str, field_name: str) -> None:
    require_non_empty(value, field_name)
    if not _is_safe_opaque_value(value, max_length=128):
        raise ValueError(f"{field_name} must be a bounded opaque safe identifier")


def _require_security_ref(value: ContractRef) -> None:
    require_contract_ref(value, "ref")
    if isinstance(value, str) and not _is_safe_opaque_value(value, max_length=256):
        raise ValueError("security event string refs must be bounded opaque identifiers")


def _reject_raw_event_data_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key.casefold() in _FORBIDDEN_RAW_METADATA_KEYS:
                raise ValueError(f"raw event data key is forbidden: {key}")
            _reject_raw_event_data_keys(item)
    elif isinstance(value, tuple):
        for item in value:
            _reject_raw_event_data_keys(item)


def _is_reason_code(value: str) -> bool:
    return bool(
        1 <= len(value) <= 128
        and "A" <= value[0] <= "Z"
        and all(
            "A" <= character <= "Z"
            or "0" <= character <= "9"
            or character in "_.-"
            for character in value[1:]
        )
    )


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
