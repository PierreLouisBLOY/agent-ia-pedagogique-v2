from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ERROR_SAFE_DATA_LIMITS,
    ContractRef,
    freeze_agent_safe_mapping,
    require_agent_safe_ref,
    require_agent_safe_text,
    require_contract_ref,
)
from backend.shared_kernel._strings import require_non_empty


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    DOMAIN = "domain"
    PERMISSION = "permission"
    GATE = "gate"
    TRANSIENT = "transient"
    PROVIDER = "provider"
    TOOL = "tool"
    BUDGET = "budget"
    CONFLICT = "conflict"
    QUALITY = "quality"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ErrorSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorSource(StrEnum):
    AGENT = "agent"
    APPLICATION = "application"
    TOOL = "tool"
    PROVIDER = "provider"


class EffectState(StrEnum):
    NONE = "none"
    UNKNOWN = "unknown"
    COMMITTED = "committed"
    PARTIAL = "partial"


class RecommendedAction(StrEnum):
    RETRY = "retry"
    REPLAN = "replan"
    ESCALATE = "escalate"
    STOP = "stop"
    INSPECT = "inspect"


@dataclass(frozen=True, slots=True)
class ErrorEnvelope:
    """Structured error description without recovery or retry behavior."""

    error_code: str
    category: ErrorCategory
    source: ErrorSource
    retryable: bool
    severity: ErrorSeverity
    message: str
    step_id: str
    attempt: int
    effect_state: EffectState
    related_refs: tuple[ContractRef, ...] = ()
    recommended_action: RecommendedAction = RecommendedAction.STOP
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.error_code, "error_code")
        if not isinstance(self.category, ErrorCategory):
            raise TypeError("category must be an ErrorCategory")
        if not isinstance(self.source, ErrorSource):
            raise TypeError("source must be an ErrorSource")
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be a bool")
        if not isinstance(self.severity, ErrorSeverity):
            raise TypeError("severity must be an ErrorSeverity")
        require_non_empty(self.message, "message")
        require_agent_safe_text(
            self.message,
            field_name="error_message",
            max_length=1_024,
        )
        require_non_empty(self.step_id, "step_id")
        if not isinstance(self.attempt, int) or isinstance(self.attempt, bool):
            raise TypeError("attempt must be an integer")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if not isinstance(self.effect_state, EffectState):
            raise TypeError("effect_state must be an EffectState")
        if not isinstance(self.recommended_action, RecommendedAction):
            raise TypeError("recommended_action must be a RecommendedAction")
        related_refs = tuple(self.related_refs)
        if len(related_refs) > 16:
            raise ValueError("related_refs must contain at most 16 items")
        for related_ref in related_refs:
            require_contract_ref(related_ref, "related_ref")
            require_agent_safe_ref(related_ref, field_name="related_ref")
        object.__setattr__(self, "related_refs", related_refs)
        object.__setattr__(
            self,
            "details",
            freeze_agent_safe_mapping(self.details, limits=ERROR_SAFE_DATA_LIMITS),
        )
