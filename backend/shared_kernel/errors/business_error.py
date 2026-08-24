from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._safe_data import freeze_safe_mapping
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import TypedEntityRef


@dataclass(frozen=True, slots=True)
class BusinessErrorCode:
    """An open, non-empty business error code."""

    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")


class BusinessErrorDomain(StrEnum):
    CORE = "CORE"
    KNOWLEDGE = "KNOWLEDGE"
    REF = "REF"
    DOC = "DOC"
    RESOURCE = "RESOURCE"
    PROD = "PROD"
    PED = "PED"
    COURSE = "COURSE"
    ANALYSIS = "ANALYSIS"
    CONTEXT = "CONTEXT"
    TASK = "TASK"
    VALIDATION = "VALIDATION"
    QUALITY = "QUALITY"
    LIFECYCLE = "LIFECYCLE"
    AUDIT = "AUDIT"


class BusinessErrorCategory(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    REQUIRED = "REQUIRED"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"
    STATE = "STATE"
    DEPENDENCY = "DEPENDENCY"
    ALIGNMENT = "ALIGNMENT"
    VISIBILITY = "VISIBILITY"
    PROVENANCE = "PROVENANCE"
    VERSION = "VERSION"
    POLICY = "POLICY"
    INDETERMINATE = "INDETERMINATE"
    INVARIANT = "INVARIANT"
    IMMUTABILITY = "IMMUTABILITY"


class BusinessErrorSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


@dataclass(frozen=True, slots=True)
class BusinessError:
    """A presentation-neutral description of a business rule failure."""

    code: BusinessErrorCode
    domain: BusinessErrorDomain
    category: BusinessErrorCategory
    severity: BusinessErrorSeverity
    blocking: bool
    retryable: bool
    message_key: str
    details: Mapping[str, object] | None = None
    subject_ref: TypedEntityRef | None = None
    operation_ref: TypedEntityRef | None = None
    rule_ref: TypedEntityRef | None = None
    cause_ref: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.message_key, "message_key")
        if self.cause_ref is not None:
            require_non_empty(self.cause_ref, "cause_ref")
        if self.details is not None:
            object.__setattr__(self, "details", freeze_safe_mapping(self.details))
