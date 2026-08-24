from __future__ import annotations

from dataclasses import dataclass, replace

from backend.agent_runtime.contracts import WorkflowStatus
from backend.agent_runtime.orchestration.coordination.completion import (
    CompletionDisposition,
    WorkflowCompletionDecision,
    WorkflowCompletionEvaluator,
)
from backend.agent_runtime.orchestration.coordination.model import (
    CoordinationAction,
    CoordinationDecision,
    CoordinationError,
    CoordinationErrorCode,
)
from backend.agent_runtime.runtime.execution import (
    ExecutionCycleResult,
    ExecutionDirectiveCode,
)
from backend.agent_runtime.runtime.planning import (
    Plan,
    PlanHistory,
    PlanRevisionEngine,
    PlanRevisionResult,
)
from backend.agent_runtime.runtime.state import RunState
from backend.agent_runtime.runtime.state._workflow_statuses import (
    TERMINAL_WORKFLOW_STATUSES,
)
from backend.shared_kernel.time import Instant

_BLOCKING_CODES = frozenset(
    {
        ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
        ExecutionDirectiveCode.WAITING_GATE,
        ExecutionDirectiveCode.REPLAN_REQUIRED,
        ExecutionDirectiveCode.RETRY_REQUIRED,
    }
)
_TERMINAL_INCOMPATIBLE_CODES = frozenset(
    {
        ExecutionDirectiveCode.RETRY_REQUIRED,
        ExecutionDirectiveCode.REPLAN_REQUIRED,
        ExecutionDirectiveCode.WAITING_GATE,
    }
)
_PRIORITY: tuple[tuple[ExecutionDirectiveCode, CoordinationAction], ...] = (
    (
        ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
        CoordinationAction.RECONCILIATION_REQUIRED,
    ),
    (ExecutionDirectiveCode.WAITING_GATE, CoordinationAction.WAIT_GATE),
    (ExecutionDirectiveCode.REPLAN_REQUIRED, CoordinationAction.REPLAN_REQUIRED),
    (ExecutionDirectiveCode.RETRY_REQUIRED, CoordinationAction.RETRY_REQUIRED),
    (
        ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION,
        CoordinationAction.REVIEW_PARTIAL,
    ),
    (ExecutionDirectiveCode.CONDITION_REQUIRED, CoordinationAction.WAIT_CONDITION),
)


@dataclass(frozen=True, slots=True)
class OrchestrationCoordinator:
    completion_evaluator: WorkflowCompletionEvaluator
    revision_engine: PlanRevisionEngine = PlanRevisionEngine()

    def __post_init__(self) -> None:
        if not isinstance(self.completion_evaluator, WorkflowCompletionEvaluator):
            raise TypeError(
                "completion_evaluator must implement WorkflowCompletionEvaluator"
            )
        if not isinstance(self.revision_engine, PlanRevisionEngine):
            raise TypeError("revision_engine must be a PlanRevisionEngine")

    def coordinate(
        self,
        *,
        plan: Plan,
        cycle: ExecutionCycleResult,
        now: Instant,
    ) -> CoordinationDecision:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(cycle, ExecutionCycleResult):
            raise TypeError("cycle must be an ExecutionCycleResult")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")

        run_state = cycle.run_state
        _require_matching_plan(plan, run_state)
        directive_codes, affected_step_ids, reason_codes = _observations(cycle)
        code_set = frozenset(directive_codes)
        _require_coherent_directives(run_state, code_set)

        if run_state.status in TERMINAL_WORKFLOW_STATUSES:
            return CoordinationDecision(
                action=_terminal_action(run_state.status),
                run_state=run_state,
                directive_codes=directive_codes,
                affected_step_ids=affected_step_ids,
                reason_codes=reason_codes,
            )

        for directive_code, action in _PRIORITY:
            if directive_code in code_set:
                return CoordinationDecision(
                    action=action,
                    run_state=run_state,
                    directive_codes=directive_codes,
                    affected_step_ids=affected_step_ids,
                    reason_codes=reason_codes,
                )

        if run_state.status is WorkflowStatus.WAITING_GATE:
            return CoordinationDecision(
                action=CoordinationAction.WAIT_GATE,
                run_state=run_state,
                directive_codes=directive_codes,
                affected_step_ids=affected_step_ids,
                reason_codes=reason_codes,
            )
        if run_state.status is WorkflowStatus.REPLANNING:
            return CoordinationDecision(
                action=CoordinationAction.REPLAN_REQUIRED,
                run_state=run_state,
                directive_codes=directive_codes,
                affected_step_ids=affected_step_ids,
                reason_codes=reason_codes,
            )

        if (
            run_state.current_step_ids
            or run_state.ready_step_ids
            or run_state.pending_step_ids
        ):
            return CoordinationDecision(
                action=CoordinationAction.CONTINUE,
                run_state=run_state,
                directive_codes=directive_codes,
                affected_step_ids=affected_step_ids,
                reason_codes=reason_codes,
            )

        completion = self.completion_evaluator.evaluate(
            plan=plan,
            run_state=run_state,
        )
        if not isinstance(completion, WorkflowCompletionDecision):
            raise CoordinationError(
                CoordinationErrorCode.INVALID_COMPLETION_DECISION,
                "completion evaluator returned an invalid decision type",
            )
        return _apply_completion(
            run_state=run_state,
            completion=completion,
            now=now,
            directive_codes=directive_codes,
            affected_step_ids=affected_step_ids,
            reason_codes=reason_codes,
        )

    def apply_replan(
        self,
        *,
        history: PlanHistory,
        run_state: RunState,
        replacement: Plan,
    ) -> PlanRevisionResult:
        if not isinstance(history, PlanHistory):
            raise TypeError("history must be a PlanHistory")
        if not isinstance(run_state, RunState):
            raise TypeError("run_state must be a RunState")
        if not isinstance(replacement, Plan):
            raise TypeError("replacement must be a Plan")
        return self.revision_engine.revise(
            history=history,
            run_state=run_state,
            replacement=replacement,
        )


def _require_matching_plan(plan: Plan, run_state: RunState) -> None:
    matches = bool(
        run_state.run_id == plan.run_id
        and run_state.plan_id == plan.plan_id
        and run_state.plan_version == plan.plan_version
        and run_state.workflow_kind == plan.workflow_kind
        and tuple(run_state.step_states)
        == tuple(step.step_id for step in plan.steps)
    )
    if not matches:
        raise CoordinationError(
            CoordinationErrorCode.PLAN_RUN_MISMATCH,
            "plan and run state identities or step order differ",
        )


def _observations(
    cycle: ExecutionCycleResult,
) -> tuple[
    tuple[ExecutionDirectiveCode, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    directive_codes = tuple(dict.fromkeys(item.code for item in cycle.directives))
    affected_step_ids = tuple(
        dict.fromkeys(
            item.step_id for item in cycle.directives if item.step_id is not None
        )
    )
    reason_codes = tuple(
        dict.fromkeys(
            item.reason_code
            for item in cycle.directives
            if item.reason_code is not None
        )
    )
    return directive_codes, affected_step_ids, reason_codes


def _require_coherent_directives(
    run_state: RunState,
    code_set: frozenset[ExecutionDirectiveCode],
) -> None:
    blocking = code_set.intersection(_BLOCKING_CODES)
    if len(blocking) > 1:
        _raise_directive_conflict()
    if {
        ExecutionDirectiveCode.STOPPED,
        ExecutionDirectiveCode.ESCALATED,
    }.issubset(code_set):
        _raise_directive_conflict()

    if run_state.status in TERMINAL_WORKFLOW_STATUSES:
        if code_set.intersection(_TERMINAL_INCOMPATIBLE_CODES):
            _raise_directive_conflict()
        if (
            run_state.status in {WorkflowStatus.SUCCEEDED, WorkflowStatus.PARTIAL}
            and ExecutionDirectiveCode.RECONCILIATION_REQUIRED in code_set
        ):
            _raise_directive_conflict()
        if run_state.status in {WorkflowStatus.SUCCEEDED, WorkflowStatus.PARTIAL} and (
            code_set.intersection(
                {ExecutionDirectiveCode.STOPPED, ExecutionDirectiveCode.ESCALATED}
            )
        ):
            _raise_directive_conflict()
        if run_state.status in {WorkflowStatus.FAILED, WorkflowStatus.CANCELLED} and (
            ExecutionDirectiveCode.ESCALATED in code_set
        ):
            _raise_directive_conflict()
        if run_state.status is WorkflowStatus.ESCALATED and (
            ExecutionDirectiveCode.STOPPED in code_set
        ):
            _raise_directive_conflict()
        return

    if code_set.intersection(
        {ExecutionDirectiveCode.STOPPED, ExecutionDirectiveCode.ESCALATED}
    ):
        _raise_directive_conflict()
    if (
        ExecutionDirectiveCode.WAITING_GATE in code_set
        and run_state.status is not WorkflowStatus.WAITING_GATE
    ):
        _raise_directive_conflict()
    if (
        ExecutionDirectiveCode.REPLAN_REQUIRED in code_set
        and run_state.status is not WorkflowStatus.REPLANNING
    ):
        _raise_directive_conflict()
    if run_state.status is WorkflowStatus.WAITING_GATE and code_set.intersection(
        {ExecutionDirectiveCode.RETRY_REQUIRED, ExecutionDirectiveCode.REPLAN_REQUIRED}
    ):
        _raise_directive_conflict()
    if run_state.status is WorkflowStatus.REPLANNING and code_set.intersection(
        {ExecutionDirectiveCode.RETRY_REQUIRED, ExecutionDirectiveCode.WAITING_GATE}
    ):
        _raise_directive_conflict()


def _raise_directive_conflict() -> None:
    raise CoordinationError(
        CoordinationErrorCode.CONFLICTING_DECISIVE_DIRECTIVES,
        "cycle contains incompatible decisive directives or state",
    )


def _terminal_action(status: WorkflowStatus) -> CoordinationAction:
    if status in {WorkflowStatus.SUCCEEDED, WorkflowStatus.PARTIAL}:
        return CoordinationAction.COMPLETE
    if status is WorkflowStatus.ESCALATED:
        return CoordinationAction.ESCALATE
    return CoordinationAction.STOP


def _apply_completion(
    *,
    run_state: RunState,
    completion: WorkflowCompletionDecision,
    now: Instant,
    directive_codes: tuple[ExecutionDirectiveCode, ...],
    affected_step_ids: tuple[str, ...],
    reason_codes: tuple[str, ...],
) -> CoordinationDecision:
    disposition = completion.disposition
    completion_reason_codes = tuple(
        dict.fromkeys((*reason_codes, completion.reason_code))
    )
    if disposition is CompletionDisposition.SUCCEEDED:
        action = CoordinationAction.COMPLETE
        updated_state = replace(
            run_state,
            status=WorkflowStatus.SUCCEEDED,
            ended_at=now,
            stop_reason=None,
        )
    elif disposition is CompletionDisposition.PARTIAL:
        action = CoordinationAction.COMPLETE
        updated_state = replace(
            run_state,
            status=WorkflowStatus.PARTIAL,
            ended_at=now,
            stop_reason=None,
        )
    elif disposition is CompletionDisposition.REPLAN_REQUIRED:
        action = CoordinationAction.REPLAN_REQUIRED
        updated_state = replace(
            run_state,
            status=WorkflowStatus.REPLANNING,
            ended_at=None,
            stop_reason=None,
        )
    elif disposition is CompletionDisposition.STOP_REQUIRED:
        action = CoordinationAction.STOP
        updated_state = replace(
            run_state,
            status=WorkflowStatus.FAILED,
            ended_at=now,
            stop_reason=completion.reason_code,
        )
    elif disposition is CompletionDisposition.ESCALATE_REQUIRED:
        action = CoordinationAction.ESCALATE
        updated_state = replace(
            run_state,
            status=WorkflowStatus.ESCALATED,
            ended_at=now,
            stop_reason=completion.reason_code,
        )
    else:
        raise CoordinationError(
            CoordinationErrorCode.INVALID_COMPLETION_DECISION,
            "completion decision has an unsupported disposition",
        )
    return CoordinationDecision(
        action=action,
        run_state=updated_state,
        directive_codes=directive_codes,
        affected_step_ids=affected_step_ids,
        reason_codes=completion_reason_codes,
    )
