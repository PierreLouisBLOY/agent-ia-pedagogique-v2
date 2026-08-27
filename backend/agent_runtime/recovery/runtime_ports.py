from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import StepSpec, ToolCallRequest, UseCaseRequest
from backend.agent_runtime.recovery.circuit_breaker import CircuitBreakerState
from backend.agent_runtime.recovery.model import EffectLedgerRecord
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


@dataclass(frozen=True, slots=True)
class RecoveryTechnicalBinding:
    """Exact technical binding metadata; it contains no authority decision."""

    target_id: str
    binding_id: str
    reservation_ttl_seconds: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("target_id", "binding_id"):
            value = getattr(self, field_name)
            if type(value) is not str or not _SAFE_IDENTIFIER.fullmatch(value):
                raise ValueError(f"{field_name} must be a safe identifier")
        if self.reservation_ttl_seconds is not None and (
            type(self.reservation_ttl_seconds) is not int
            or self.reservation_ttl_seconds < 1
        ):
            raise ValueError("reservation_ttl_seconds must be >= 1 or None")


@runtime_checkable
class RecoveryRuntimeResolverPort(Protocol):
    """Trusted binding resolution only; implementations grant no permission."""

    def resolve_tool_recovery(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        request: ToolCallRequest,
    ) -> RecoveryTechnicalBinding: ...

    def resolve_application_recovery(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        request: UseCaseRequest,
    ) -> RecoveryTechnicalBinding: ...

    def resolve_agent_recovery(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
    ) -> RecoveryTechnicalBinding: ...


@dataclass(frozen=True, slots=True)
class RecoveryReferences:
    """All recovery references known for one run at one read boundary."""

    effect_records: tuple[EffectLedgerRecord, ...] = ()
    circuit_states: tuple[CircuitBreakerState, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.effect_records, tuple) or any(
            not isinstance(item, EffectLedgerRecord) for item in self.effect_records
        ):
            raise TypeError("effect_records must contain EffectLedgerRecord values")
        if not isinstance(self.circuit_states, tuple) or any(
            not isinstance(item, CircuitBreakerState) for item in self.circuit_states
        ):
            raise TypeError("circuit_states must contain CircuitBreakerState values")
        if len({item.record_id for item in self.effect_records}) != len(
            self.effect_records
        ):
            raise ValueError("effect_records must be unique")
        if len({item.circuit_id for item in self.circuit_states}) != len(
            self.circuit_states
        ):
            raise ValueError("circuit_states must be unique")


@runtime_checkable
class RecoveryReferenceResolverPort(Protocol):
    def resolve_recovery_references(self, *, run_id: str) -> RecoveryReferences: ...
