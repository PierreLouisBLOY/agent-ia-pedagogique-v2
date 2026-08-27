from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts.common import ContractRef, require_contract_ref


class SecurityBoundary(StrEnum):
    USER_INPUT = "user_input"
    DOCUMENT = "document"
    EVIDENCE = "evidence"
    AGENT = "agent"
    TOOL = "tool"
    APPLICATION = "application"
    GATE = "gate"
    RUNTIME = "runtime"
    RECOVERY = "recovery"
    INFRASTRUCTURE = "infrastructure"


class ContentOrigin(StrEnum):
    USER_INPUT = "user_input"
    DOCUMENT = "document"
    EVIDENCE = "evidence"
    AGENT_OUTPUT = "agent_output"
    TOOL_OUTPUT = "tool_output"
    APPLICATION_OUTPUT = "application_output"
    REVIEW_OUTPUT = "review_output"
    CORRECTION_OUTPUT = "correction_output"
    RUNTIME_DATA = "runtime_data"
    RECOVERY_DATA = "recovery_data"
    INTERNAL_CONTROL = "internal_control"


class ContentRole(StrEnum):
    INSTRUCTION = "instruction"
    DATA = "data"
    EVIDENCE = "evidence"
    RESULT = "result"
    METADATA = "metadata"
    DIAGNOSTIC = "diagnostic"


class ContentTrustClass(StrEnum):
    """Descriptive structural trust; never an authorization decision."""

    UNTRUSTED = "untrusted"
    STRUCTURALLY_VALIDATED = "structurally_validated"


@dataclass(frozen=True, slots=True)
class ContentTrustLabel:
    """Immutable provenance label without authority or promotion semantics."""

    origin: ContentOrigin
    role: ContentRole
    trust_class: ContentTrustClass
    source_ref: ContractRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.origin, ContentOrigin):
            raise TypeError("origin must be a ContentOrigin")
        if not isinstance(self.role, ContentRole):
            raise TypeError("role must be a ContentRole")
        if not isinstance(self.trust_class, ContentTrustClass):
            raise TypeError("trust_class must be a ContentTrustClass")
        if self.source_ref is not None:
            require_contract_ref(self.source_ref, "source_ref")
