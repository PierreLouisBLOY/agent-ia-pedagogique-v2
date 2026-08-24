from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts import WorkflowStatus
from backend.agent_runtime.runtime.execution import ExecutionDirectiveCode
from backend.agent_runtime.runtime.state import RunState
from backend.shared_kernel._strings import require_non_empty


class CoordinationAction(StrEnum):
    CONTINUE = "CONTINUE"
    WAIT_GATE = "WAIT_GATE"
    WAIT_CONDITION = "WAIT_CONDITION"
    REVIEW_PARTIAL = "REVIEW_PARTIAL"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    STOP = "STOP"
    ESCALATE = "ESCALATE"
    COMPLETE = "COMPLETE"


class CoordinationErrorCode(StrEnum):
    PLAN_RUN_MISMATCH = "PLAN_RUN_MISMATCH"
    CONFLICTING_DECISIVE_DIRECTIVES = "CONFLICTING_DECISIVE_DIRECTIVES"
    INVALID_COMPLETION_DECISION = "INVALID_COMPLETION_DECISION"


class CoordinationError(ValueError):
    code: CoordinationErrorCode

    def __init__(self, code: CoordinationErrorCode, message: str) -> None:
        if not isinstance(code, CoordinationErrorCode):
            raise TypeError("code must be a CoordinationErrorCode")
        require_non_empty(message, "message")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CoordinationDecision:
    action: CoordinationAction
    run_state: RunState
    directive_codes: tuple[ExecutionDirectiveCode, ...]
    affected_step_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.action, CoordinationAction):
            raise TypeError("action must be a CoordinationAction")
        if not isinstance(self.run_state, RunState):
            raise TypeError("run_state must be a RunState")
        if not isinstance(self.directive_codes, tuple):
            raise TypeError("directive_codes must be a tuple")
        if any(
            not isinstance(code, ExecutionDirectiveCode)
            for code in self.directive_codes
        ):
            raise TypeError("directive_codes must contain ExecutionDirectiveCode values")
        if not isinstance(self.affected_step_ids, tuple):
            raise TypeError("affected_step_ids must be a tuple")
        for step_id in self.affected_step_ids:
            require_non_empty(step_id, "affected_step_id")
            if step_id not in self.run_state.step_states:
                raise ValueError("affected_step_ids must belong to run_state")
        if not isinstance(self.reason_codes, tuple):
            raise TypeError("reason_codes must be a tuple")
        for reason_code in self.reason_codes:
            require_non_empty(reason_code, "reason_code")

        object.__setattr__(
            self, "directive_codes", _stable_unique(self.directive_codes)
        )
        object.__setattr__(
            self, "affected_step_ids", _stable_unique(self.affected_step_ids)
        )
        object.__setattr__(self, "reason_codes", _stable_unique(self.reason_codes))

        status = self.run_state.status
        if self.action is CoordinationAction.COMPLETE and status not in {
            WorkflowStatus.SUCCEEDED,
            WorkflowStatus.PARTIAL,
        }:
            raise ValueError("COMPLETE requires a succeeded or partial run")
        if (
            self.action is CoordinationAction.ESCALATE
            and status is not WorkflowStatus.ESCALATED
        ):
            raise ValueError("ESCALATE requires an escalated run")
        if self.action is CoordinationAction.STOP and status not in {
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }:
            raise ValueError("STOP requires a failed or cancelled run")
        if self.action is CoordinationAction.WAIT_GATE and not (
            status is WorkflowStatus.WAITING_GATE
            or ExecutionDirectiveCode.WAITING_GATE in self.directive_codes
        ):
            raise ValueError("WAIT_GATE requires waiting gate state or directive")
        if self.action is CoordinationAction.REPLAN_REQUIRED and not (
            status is WorkflowStatus.REPLANNING
            or ExecutionDirectiveCode.REPLAN_REQUIRED in self.directive_codes
        ):
            raise ValueError("REPLAN_REQUIRED requires replanning state or directive")


def _stable_unique[T](values: tuple[T, ...]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(values))
