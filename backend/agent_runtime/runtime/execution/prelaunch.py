from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import SecurityEvent, StepSpec
from backend.agent_runtime.contracts.common import require_agent_safe_text
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState
from backend.agent_runtime.security.runtime_composition import (
    RuntimeSecurityAssessment,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class PreLaunchDisposition(StrEnum):
    ALLOW = "ALLOW"
    WAITING_GATE = "WAITING_GATE"
    DENY = "DENY"
    CONDITION_REQUIRED = "CONDITION_REQUIRED"


@dataclass(frozen=True, slots=True)
class PreLaunchDecision:
    disposition: PreLaunchDisposition
    reason_code: str | None = None
    security_assessment: RuntimeSecurityAssessment | None = None
    security_events: tuple[SecurityEvent, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, PreLaunchDisposition):
            raise TypeError("disposition must be a PreLaunchDisposition")
        if self.security_assessment is not None and not isinstance(
            self.security_assessment, RuntimeSecurityAssessment
        ):
            raise TypeError("security_assessment must be RuntimeSecurityAssessment")
        if type(self.security_events) is not tuple or any(
            type(event) is not SecurityEvent for event in self.security_events
        ):
            raise TypeError("security_events must contain SecurityEvent values")
        if len(self.security_events) > 1:
            raise ValueError("a boundary decision carries at most one security event")
        if self.disposition is PreLaunchDisposition.ALLOW:
            if self.reason_code is not None:
                raise ValueError("ALLOW must not have a reason_code")
            if (
                self.security_assessment is not None
                and not self.security_assessment.launchable
            ):
                raise ValueError("ALLOW requires a launchable security assessment")
            if self.security_events:
                raise ValueError("ALLOW must not carry security failure events")
            return
        if self.reason_code is None:
            raise ValueError("non-ALLOW decisions require reason_code")
        require_non_empty(self.reason_code, "reason_code")
        require_agent_safe_text(
            self.reason_code, field_name="reason_code", max_length=256
        )
        if (
            self.security_assessment is not None
            and self.security_assessment.launchable
        ):
            raise ValueError("security refusal must not be launchable")


@runtime_checkable
class PreLaunchGuard(Protocol):
    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision: ...
