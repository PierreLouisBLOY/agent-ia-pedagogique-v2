from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState
from backend.shared_kernel._strings import require_non_empty


class CompletionDisposition(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    STOP_REQUIRED = "STOP_REQUIRED"
    ESCALATE_REQUIRED = "ESCALATE_REQUIRED"


@dataclass(frozen=True, slots=True)
class WorkflowCompletionDecision:
    disposition: CompletionDisposition
    reason_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, CompletionDisposition):
            raise TypeError("disposition must be a CompletionDisposition")
        require_non_empty(self.reason_code, "reason_code")


@runtime_checkable
class WorkflowCompletionEvaluator(Protocol):
    def evaluate(
        self,
        *,
        plan: Plan,
        run_state: RunState,
    ) -> WorkflowCompletionDecision:
        ...
