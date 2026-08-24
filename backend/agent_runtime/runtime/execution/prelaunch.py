from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import StepSpec
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState
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

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, PreLaunchDisposition):
            raise TypeError("disposition must be a PreLaunchDisposition")
        if self.disposition is PreLaunchDisposition.ALLOW:
            if self.reason_code is not None:
                raise ValueError("ALLOW must not have a reason_code")
            return
        if self.reason_code is None:
            raise ValueError("non-ALLOW decisions require reason_code")
        require_non_empty(self.reason_code, "reason_code")


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
