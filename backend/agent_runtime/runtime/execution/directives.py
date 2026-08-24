from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty


class ExecutionDirectiveCode(StrEnum):
    CONTINUE = "CONTINUE"
    WAITING_GATE = "WAITING_GATE"
    CONDITION_REQUIRED = "CONDITION_REQUIRED"
    PRELAUNCH_DENIED = "PRELAUNCH_DENIED"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    ESCALATED = "ESCALATED"
    STOPPED = "STOPPED"
    PARTIAL_REQUIRES_DECISION = "PARTIAL_REQUIRES_DECISION"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    READY_DEADLINE_EXPIRED = "READY_DEADLINE_EXPIRED"
    RUN_DEADLINE_EXCEEDED = "RUN_DEADLINE_EXCEEDED"


@dataclass(frozen=True, slots=True)
class ExecutionDirective:
    code: ExecutionDirectiveCode
    step_id: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, ExecutionDirectiveCode):
            raise TypeError("code must be an ExecutionDirectiveCode")
        if self.step_id is not None:
            require_non_empty(self.step_id, "step_id")
        if self.code is not ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED:
            if self.step_id is None:
                raise ValueError("step-scoped directives require step_id")
        if self.code is ExecutionDirectiveCode.CONTINUE:
            if self.reason_code is not None:
                raise ValueError("CONTINUE must not have a reason_code")
            return
        if self.reason_code is None:
            raise ValueError("non-CONTINUE directives require reason_code")
        require_non_empty(self.reason_code, "reason_code")
