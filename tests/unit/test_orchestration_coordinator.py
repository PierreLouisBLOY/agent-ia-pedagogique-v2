from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from backend.agent_runtime.contracts import (
    ExecutorKind,
    ExecutorRef,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.orchestration import (
    CompletionDisposition,
    CoordinationAction,
    CoordinationDecision,
    CoordinationError,
    CoordinationErrorCode,
    OrchestrationCoordinator,
    WorkflowCompletionDecision,
    WorkflowCompletionEvaluator,
)
from backend.agent_runtime.runtime import (
    ExecutionCycleResult,
    ExecutionDirective,
    ExecutionDirectiveCode,
    Plan,
    RunState,
    StepRuntimeStatus,
    StepState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 12, 0, tzinfo=UTC))
STARTED = Instant(NOW.value - timedelta(minutes=10))


def _step(step_id: str) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=StepKind.USE_CASE,
        capability_id=CapabilityId("CAP-R01"),
        executor=ExecutorRef(ExecutorKind.APPLICATION),
        objective=f"Execute {step_id}",
        permission_scope_ref="scope-1",
        output_contract={"type": "result"},
    )


def _plan(*step_ids: str) -> Plan:
    return Plan(
        plan_id="plan-1",
        run_id="run-1",
        plan_version=1,
        objective="Complete the deterministic workflow",
        success_criteria={"complete": True},
        workflow_kind="WF-TEST",
        steps=tuple(_step(step_id) for step_id in step_ids),
        stop_conditions={"failure": "stop"},
    )


def _step_state(step_id: str, status: StepRuntimeStatus) -> StepState:
    if status is StepRuntimeStatus.RUNNING:
        return StepState(step_id, status, started_at=STARTED, attempt_count=1)
    if status in {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.SKIPPED,
        StepRuntimeStatus.CANCELLED,
    }:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=1,
        )
    if status is StepRuntimeStatus.FAILED:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=1,
            block_reason="failed",
        )
    if status is StepRuntimeStatus.BLOCKED:
        return StepState(step_id, status, block_reason="blocked")
    return StepState(step_id, status)


def _run_state(
    plan: Plan,
    *,
    step_statuses: Mapping[str, StepRuntimeStatus] | None = None,
    status: WorkflowStatus = WorkflowStatus.RUNNING,
) -> RunState:
    terminal = status in {
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    }
    stop_required = status in {
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    }
    effective = step_statuses or {
        step.step_id: StepRuntimeStatus.PENDING for step in plan.steps
    }
    return RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=status,
        step_states={
            step.step_id: _step_state(step.step_id, effective[step.step_id])
            for step in plan.steps
        },
        started_at=None if status is WorkflowStatus.PLANNED else STARTED,
        ended_at=NOW if terminal else None,
        stop_reason="terminal" if stop_required else None,
    )


def _directive(
    code: ExecutionDirectiveCode,
    step_id: str | None = "a",
    reason_code: str | None = None,
) -> ExecutionDirective:
    if code is ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED:
        step_id = None
    if code is ExecutionDirectiveCode.CONTINUE:
        reason_code = None
    return ExecutionDirective(
        code=code,
        step_id=step_id,
        reason_code=(
            None
            if code is ExecutionDirectiveCode.CONTINUE
            else reason_code or code.value
        ),
    )


class FakeCompletionEvaluator:
    def __init__(self, decision: object) -> None:
        self.decision = decision
        self.calls: list[tuple[Plan, RunState]] = []

    def evaluate(
        self,
        *,
        plan: Plan,
        run_state: RunState,
    ) -> WorkflowCompletionDecision:
        self.calls.append((plan, run_state))
        return cast(WorkflowCompletionDecision, self.decision)


def _coordinator(
    disposition: CompletionDisposition = CompletionDisposition.SUCCEEDED,
) -> tuple[OrchestrationCoordinator, FakeCompletionEvaluator]:
    evaluator = FakeCompletionEvaluator(
        WorkflowCompletionDecision(disposition, f"COMPLETION_{disposition.value}")
    )
    return OrchestrationCoordinator(evaluator), evaluator


def _coordinate(
    plan: Plan,
    run_state: RunState,
    *directives: ExecutionDirective,
    disposition: CompletionDisposition = CompletionDisposition.SUCCEEDED,
) -> tuple[CoordinationDecision, FakeCompletionEvaluator]:
    coordinator, evaluator = _coordinator(disposition)
    decision = coordinator.coordinate(
        plan=plan,
        cycle=ExecutionCycleResult(run_state=run_state, directives=directives),
        now=NOW,
    )
    return decision, evaluator


def test_coordination_action_values_are_exact() -> None:
    assert [item.value for item in CoordinationAction] == [
        "CONTINUE",
        "WAIT_GATE",
        "WAIT_CONDITION",
        "REVIEW_PARTIAL",
        "RETRY_REQUIRED",
        "REPLAN_REQUIRED",
        "RECONCILIATION_REQUIRED",
        "STOP",
        "ESCALATE",
        "COMPLETE",
    ]


def test_completion_disposition_values_are_exact() -> None:
    assert [item.value for item in CompletionDisposition] == [
        "SUCCEEDED",
        "PARTIAL",
        "REPLAN_REQUIRED",
        "STOP_REQUIRED",
        "ESCALATE_REQUIRED",
    ]


def test_coordination_error_code_values_are_exact() -> None:
    assert [item.value for item in CoordinationErrorCode] == [
        "PLAN_RUN_MISMATCH",
        "CONFLICTING_DECISIVE_DIRECTIVES",
        "INVALID_COMPLETION_DECISION",
    ]


def test_workflow_completion_decision_requires_reason_code() -> None:
    with pytest.raises(ValueError, match="reason_code"):
        WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, " ")


def test_completion_evaluator_protocol_is_runtime_checkable() -> None:
    fake = FakeCompletionEvaluator(
        WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "DONE")
    )
    assert isinstance(fake, WorkflowCompletionEvaluator)


def test_coordination_decision_deduplicates_observations_stably() -> None:
    plan = _plan("a")
    run_state = _run_state(plan)
    decision = CoordinationDecision(
        CoordinationAction.CONTINUE,
        run_state,
        (
            ExecutionDirectiveCode.CONTINUE,
            ExecutionDirectiveCode.PRELAUNCH_DENIED,
            ExecutionDirectiveCode.CONTINUE,
        ),
        ("a", "a"),
        ("FIRST", "SECOND", "FIRST"),
    )
    assert decision.directive_codes == (
        ExecutionDirectiveCode.CONTINUE,
        ExecutionDirectiveCode.PRELAUNCH_DENIED,
    )
    assert decision.affected_step_ids == ("a",)
    assert decision.reason_codes == ("FIRST", "SECOND")
    with pytest.raises(FrozenInstanceError):
        decision.action = CoordinationAction.STOP  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("action", "CONTINUE", "action"),
        ("run_state", object(), "run_state"),
        ("directive_codes", [], "directive_codes"),
        ("affected_step_ids", [], "affected_step_ids"),
        ("reason_codes", [], "reason_codes"),
    ],
)
def test_coordination_decision_requires_strict_types(
    field_name: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, object] = {
        "action": CoordinationAction.CONTINUE,
        "run_state": _run_state(_plan("a")),
        "directive_codes": (),
        "affected_step_ids": (),
        "reason_codes": (),
    }
    values[field_name] = value
    with pytest.raises(TypeError, match=message):
        CoordinationDecision(**values)  # type: ignore[arg-type]


def test_coordination_decision_rejects_unknown_affected_step() -> None:
    with pytest.raises(ValueError, match="belong"):
        CoordinationDecision(
            CoordinationAction.CONTINUE,
            _run_state(_plan("a")),
            (),
            ("unknown",),
            (),
        )


@pytest.mark.parametrize(
    ("action", "status", "message"),
    [
        (CoordinationAction.COMPLETE, WorkflowStatus.RUNNING, "COMPLETE"),
        (CoordinationAction.STOP, WorkflowStatus.RUNNING, "STOP"),
        (CoordinationAction.ESCALATE, WorkflowStatus.FAILED, "ESCALATE"),
        (CoordinationAction.WAIT_GATE, WorkflowStatus.RUNNING, "WAIT_GATE"),
        (CoordinationAction.REPLAN_REQUIRED, WorkflowStatus.RUNNING, "REPLAN"),
    ],
)
def test_coordination_decision_enforces_action_state_invariants(
    action: CoordinationAction,
    status: WorkflowStatus,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CoordinationDecision(action, _run_state(_plan("a"), status=status), (), (), ())


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("run_id", "other-run"),
        ("plan_id", "other-plan"),
        ("plan_version", 2),
        ("workflow_kind", "other-workflow"),
    ],
)
def test_plan_run_identity_mismatch_is_rejected(
    field_name: str,
    new_value: object,
) -> None:
    plan = _plan("a")
    run_state = replace(_run_state(plan), **{field_name: new_value})
    coordinator, _ = _coordinator()
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(run_state),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.PLAN_RUN_MISMATCH


def test_plan_run_step_order_mismatch_is_rejected() -> None:
    plan = _plan("a", "b")
    run_state = _run_state(plan)
    reversed_state = replace(
        run_state,
        step_states={"b": run_state.step_states["b"], "a": run_state.step_states["a"]},
    )
    coordinator, _ = _coordinator()
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(reversed_state),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.PLAN_RUN_MISMATCH


@pytest.mark.parametrize(
    ("status", "expected_action"),
    [
        (WorkflowStatus.SUCCEEDED, CoordinationAction.COMPLETE),
        (WorkflowStatus.PARTIAL, CoordinationAction.COMPLETE),
        (WorkflowStatus.FAILED, CoordinationAction.STOP),
        (WorkflowStatus.CANCELLED, CoordinationAction.STOP),
        (WorkflowStatus.ESCALATED, CoordinationAction.ESCALATE),
    ],
)
def test_terminal_run_has_absolute_priority_and_preserves_snapshot(
    status: WorkflowStatus,
    expected_action: CoordinationAction,
) -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        status=status,
        step_statuses={"a": StepRuntimeStatus.SUCCEEDED},
    )
    decision, evaluator = _coordinate(plan, run_state)
    assert decision.action is expected_action
    assert decision.run_state is run_state
    assert evaluator.calls == []


@pytest.mark.parametrize(
    ("code", "status", "expected_action"),
    [
        (
            ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
            WorkflowStatus.RUNNING,
            CoordinationAction.RECONCILIATION_REQUIRED,
        ),
        (
            ExecutionDirectiveCode.WAITING_GATE,
            WorkflowStatus.WAITING_GATE,
            CoordinationAction.WAIT_GATE,
        ),
        (
            ExecutionDirectiveCode.REPLAN_REQUIRED,
            WorkflowStatus.REPLANNING,
            CoordinationAction.REPLAN_REQUIRED,
        ),
        (
            ExecutionDirectiveCode.RETRY_REQUIRED,
            WorkflowStatus.RUNNING,
            CoordinationAction.RETRY_REQUIRED,
        ),
        (
            ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION,
            WorkflowStatus.RUNNING,
            CoordinationAction.REVIEW_PARTIAL,
        ),
        (
            ExecutionDirectiveCode.CONDITION_REQUIRED,
            WorkflowStatus.RUNNING,
            CoordinationAction.WAIT_CONDITION,
        ),
    ],
)
def test_directive_maps_to_coordination_action_without_mutation(
    code: ExecutionDirectiveCode,
    status: WorkflowStatus,
    expected_action: CoordinationAction,
) -> None:
    plan = _plan("a")
    run_state = _run_state(plan, status=status)
    decision, evaluator = _coordinate(plan, run_state, _directive(code))
    assert decision.action is expected_action
    assert decision.run_state is run_state
    assert evaluator.calls == []


def test_prelaunch_denied_plus_stopped_uses_terminal_stop() -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        status=WorkflowStatus.FAILED,
        step_statuses={"a": StepRuntimeStatus.BLOCKED},
    )
    decision, _ = _coordinate(
        plan,
        run_state,
        _directive(ExecutionDirectiveCode.PRELAUNCH_DENIED),
        _directive(ExecutionDirectiveCode.STOPPED),
    )
    assert decision.action is CoordinationAction.STOP


def test_ready_deadline_plus_replan_is_replan_required() -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        status=WorkflowStatus.REPLANNING,
        step_statuses={"a": StepRuntimeStatus.FAILED},
    )
    decision, _ = _coordinate(
        plan,
        run_state,
        _directive(ExecutionDirectiveCode.READY_DEADLINE_EXPIRED),
        _directive(ExecutionDirectiveCode.REPLAN_REQUIRED),
    )
    assert decision.action is CoordinationAction.REPLAN_REQUIRED


def test_run_deadline_plus_reconciliation_is_reconciliation_required() -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        step_statuses={"a": StepRuntimeStatus.RUNNING},
    )
    decision, _ = _coordinate(
        plan,
        run_state,
        _directive(ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED),
        _directive(ExecutionDirectiveCode.RECONCILIATION_REQUIRED),
    )
    assert decision.action is CoordinationAction.RECONCILIATION_REQUIRED


def test_all_observations_are_preserved_and_deduplicated() -> None:
    plan = _plan("a", "b")
    run_state = _run_state(plan)
    decision, _ = _coordinate(
        plan,
        run_state,
        _directive(ExecutionDirectiveCode.PRELAUNCH_DENIED, "a", "DENIED"),
        _directive(ExecutionDirectiveCode.CONTINUE, "b"),
        _directive(ExecutionDirectiveCode.PRELAUNCH_DENIED, "a", "DENIED"),
    )
    assert decision.directive_codes == (
        ExecutionDirectiveCode.PRELAUNCH_DENIED,
        ExecutionDirectiveCode.CONTINUE,
    )
    assert decision.affected_step_ids == ("a", "b")
    assert decision.reason_codes == ("DENIED",)


@pytest.mark.parametrize(
    ("left", "right", "status"),
    [
        (
            ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
            ExecutionDirectiveCode.RETRY_REQUIRED,
            WorkflowStatus.RUNNING,
        ),
        (
            ExecutionDirectiveCode.RECONCILIATION_REQUIRED,
            ExecutionDirectiveCode.REPLAN_REQUIRED,
            WorkflowStatus.REPLANNING,
        ),
        (
            ExecutionDirectiveCode.WAITING_GATE,
            ExecutionDirectiveCode.RETRY_REQUIRED,
            WorkflowStatus.WAITING_GATE,
        ),
        (
            ExecutionDirectiveCode.WAITING_GATE,
            ExecutionDirectiveCode.REPLAN_REQUIRED,
            WorkflowStatus.WAITING_GATE,
        ),
        (
            ExecutionDirectiveCode.RETRY_REQUIRED,
            ExecutionDirectiveCode.REPLAN_REQUIRED,
            WorkflowStatus.REPLANNING,
        ),
        (
            ExecutionDirectiveCode.STOPPED,
            ExecutionDirectiveCode.ESCALATED,
            WorkflowStatus.RUNNING,
        ),
    ],
)
def test_conflicting_decisive_directives_fail_closed(
    left: ExecutionDirectiveCode,
    right: ExecutionDirectiveCode,
    status: WorkflowStatus,
) -> None:
    plan = _plan("a")
    coordinator, _ = _coordinator()
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(
                _run_state(plan, status=status),
                directives=(_directive(left), _directive(right)),
            ),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.CONFLICTING_DECISIVE_DIRECTIVES


@pytest.mark.parametrize(
    ("terminal_status", "code"),
    [
        (WorkflowStatus.SUCCEEDED, ExecutionDirectiveCode.RETRY_REQUIRED),
        (WorkflowStatus.PARTIAL, ExecutionDirectiveCode.REPLAN_REQUIRED),
        (WorkflowStatus.SUCCEEDED, ExecutionDirectiveCode.STOPPED),
        (WorkflowStatus.PARTIAL, ExecutionDirectiveCode.ESCALATED),
        (WorkflowStatus.FAILED, ExecutionDirectiveCode.WAITING_GATE),
        (WorkflowStatus.FAILED, ExecutionDirectiveCode.ESCALATED),
        (WorkflowStatus.CANCELLED, ExecutionDirectiveCode.RETRY_REQUIRED),
        (WorkflowStatus.ESCALATED, ExecutionDirectiveCode.STOPPED),
    ],
)
def test_terminal_run_rejects_incompatible_directive(
    terminal_status: WorkflowStatus,
    code: ExecutionDirectiveCode,
) -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        status=terminal_status,
        step_statuses={"a": StepRuntimeStatus.SUCCEEDED},
    )
    coordinator, _ = _coordinator()
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(run_state, directives=(_directive(code),)),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.CONFLICTING_DECISIVE_DIRECTIVES


@pytest.mark.parametrize(
    "code",
    [ExecutionDirectiveCode.STOPPED, ExecutionDirectiveCode.ESCALATED],
)
def test_non_terminal_run_rejects_terminal_directive(
    code: ExecutionDirectiveCode,
) -> None:
    plan = _plan("a")
    coordinator, _ = _coordinator()
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(
                _run_state(plan), directives=(_directive(code),)
            ),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.CONFLICTING_DECISIVE_DIRECTIVES


@pytest.mark.parametrize(
    ("code", "count", "expected_action"),
    [
        (
            ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION,
            2,
            CoordinationAction.REVIEW_PARTIAL,
        ),
        (
            ExecutionDirectiveCode.CONDITION_REQUIRED,
            2,
            CoordinationAction.WAIT_CONDITION,
        ),
    ],
)
def test_multiple_independent_advisory_directives_are_allowed(
    code: ExecutionDirectiveCode,
    count: int,
    expected_action: CoordinationAction,
) -> None:
    plan = _plan("a", "b")
    run_state = _run_state(plan)
    directives = tuple(_directive(code, step_id) for step_id in ("a", "b")[:count])
    decision, _ = _coordinate(plan, run_state, *directives)
    assert decision.action is expected_action
    assert decision.affected_step_ids == ("a", "b")


@pytest.mark.parametrize(
    "step_status",
    [
        StepRuntimeStatus.READY,
        StepRuntimeStatus.PENDING,
        StepRuntimeStatus.RUNNING,
    ],
)
def test_non_quiescent_run_continues_without_completion_evaluation(
    step_status: StepRuntimeStatus,
) -> None:
    plan = _plan("a")
    run_state = _run_state(plan, step_statuses={"a": step_status})
    decision, evaluator = _coordinate(plan, run_state)
    assert decision.action is CoordinationAction.CONTINUE
    assert decision.run_state is run_state
    assert evaluator.calls == []


@pytest.mark.parametrize(
    ("disposition", "expected_action", "expected_status", "stop_reason"),
    [
        (
            CompletionDisposition.SUCCEEDED,
            CoordinationAction.COMPLETE,
            WorkflowStatus.SUCCEEDED,
            None,
        ),
        (
            CompletionDisposition.PARTIAL,
            CoordinationAction.COMPLETE,
            WorkflowStatus.PARTIAL,
            None,
        ),
        (
            CompletionDisposition.REPLAN_REQUIRED,
            CoordinationAction.REPLAN_REQUIRED,
            WorkflowStatus.REPLANNING,
            None,
        ),
        (
            CompletionDisposition.STOP_REQUIRED,
            CoordinationAction.STOP,
            WorkflowStatus.FAILED,
            "COMPLETION_STOP_REQUIRED",
        ),
        (
            CompletionDisposition.ESCALATE_REQUIRED,
            CoordinationAction.ESCALATE,
            WorkflowStatus.ESCALATED,
            "COMPLETION_ESCALATE_REQUIRED",
        ),
    ],
)
def test_quiescent_completion_decision_updates_only_run_terminal_fields(
    disposition: CompletionDisposition,
    expected_action: CoordinationAction,
    expected_status: WorkflowStatus,
    stop_reason: str | None,
) -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        step_statuses={"a": StepRuntimeStatus.SUCCEEDED},
    )
    decision, evaluator = _coordinate(
        plan,
        run_state,
        disposition=disposition,
    )
    assert decision.action is expected_action
    assert decision.run_state.status is expected_status
    assert decision.run_state.stop_reason == stop_reason
    assert decision.run_state.started_at is run_state.started_at
    assert decision.run_state.step_states == run_state.step_states
    assert len(evaluator.calls) == 1
    if expected_status is WorkflowStatus.REPLANNING:
        assert decision.run_state.ended_at is None
    else:
        assert decision.run_state.ended_at is NOW


def test_invalid_completion_return_type_fails_closed() -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        step_statuses={"a": StepRuntimeStatus.SUCCEEDED},
    )
    evaluator = FakeCompletionEvaluator(object())
    coordinator = OrchestrationCoordinator(evaluator)
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(run_state),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.INVALID_COMPLETION_DECISION
    assert len(evaluator.calls) == 1


def test_quiescence_does_not_imply_success_without_evaluator_decision() -> None:
    plan = _plan("a")
    run_state = _run_state(
        plan,
        step_statuses={"a": StepRuntimeStatus.SUCCEEDED},
    )
    decision, _ = _coordinate(
        plan,
        run_state,
        disposition=CompletionDisposition.STOP_REQUIRED,
    )
    assert decision.action is CoordinationAction.STOP
    assert decision.run_state.status is WorkflowStatus.FAILED


def test_waiting_and_replanning_states_are_decisive_without_directive() -> None:
    plan = _plan("a")
    waiting, _ = _coordinate(
        plan,
        _run_state(plan, status=WorkflowStatus.WAITING_GATE),
    )
    replanning, _ = _coordinate(
        plan,
        _run_state(plan, status=WorkflowStatus.REPLANNING),
    )
    assert waiting.action is CoordinationAction.WAIT_GATE
    assert replanning.action is CoordinationAction.REPLAN_REQUIRED


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ExecutionDirectiveCode.WAITING_GATE, WorkflowStatus.RUNNING),
        (ExecutionDirectiveCode.REPLAN_REQUIRED, WorkflowStatus.RUNNING),
    ],
)
def test_directive_state_incoherence_fails_closed(
    code: ExecutionDirectiveCode,
    status: WorkflowStatus,
) -> None:
    plan = _plan("a")
    coordinator, _ = _coordinator()
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(
                _run_state(plan, status=status), directives=(_directive(code),)
            ),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.CONFLICTING_DECISIVE_DIRECTIVES


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (WorkflowStatus.WAITING_GATE, ExecutionDirectiveCode.RETRY_REQUIRED),
        (WorkflowStatus.REPLANNING, ExecutionDirectiveCode.RETRY_REQUIRED),
    ],
)
def test_waiting_or_replanning_state_rejects_incompatible_retry(
    status: WorkflowStatus,
    code: ExecutionDirectiveCode,
) -> None:
    plan = _plan("a")
    coordinator, _ = _coordinator()
    with pytest.raises(CoordinationError) as raised:
        coordinator.coordinate(
            plan=plan,
            cycle=ExecutionCycleResult(
                _run_state(plan, status=status), directives=(_directive(code),)
            ),
            now=NOW,
        )
    assert raised.value.code is CoordinationErrorCode.CONFLICTING_DECISIVE_DIRECTIVES
