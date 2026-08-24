from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from typing import cast

import pytest

from backend.agent_runtime.contracts import (
    BudgetSpec,
    ExecutorKind,
    ExecutorRef,
    FailurePolicy,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.runtime import (
    Plan,
    PlanHistory,
    PlanRevisionCode,
    PlanRevisionEngine,
    PlanRevisionIssue,
    PlanRevisionResult,
    RunState,
    StepRuntimeStatus,
    StepState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 14, 0, tzinfo=UTC))
STARTED = Instant(datetime(2026, 8, 24, 13, 0, tzinfo=UTC))


def _step(
    step_id: str,
    *,
    capability: str = "CAP-R01",
    input_refs: tuple[str, ...] = (),
    depends_on: tuple[str, ...] = (),
    permission_scope_ref: str = "scope-1",
    budget: BudgetSpec | None = None,
    failure_policy: FailurePolicy = FailurePolicy.STOP,
    objective: str | None = None,
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=StepKind.USE_CASE,
        capability_id=CapabilityId(capability),
        executor=ExecutorRef(ExecutorKind.APPLICATION),
        objective=objective or f"Execute {step_id}",
        input_refs=input_refs,
        depends_on=depends_on,
        permission_scope_ref=permission_scope_ref,
        budget=budget,
        success_criteria={"done": True},
        failure_policy=failure_policy,
        output_contract={"type": "result"},
    )


def _plan(
    version: int,
    *steps: StepSpec,
    run_id: str = "run-1",
    plan_id: str = "plan-1",
    workflow_kind: str = "opaque-workflow",
    objective: str = "Complete stable objective",
    success_criteria: object = None,
    stop_conditions: object = None,
    budget_envelope: BudgetSpec | None = None,
) -> Plan:
    return Plan(
        plan_id=plan_id,
        run_id=run_id,
        plan_version=version,
        objective=objective,
        success_criteria=(
            {"complete": True}
            if success_criteria is None
            else cast(dict[str, object], success_criteria)
        ),
        workflow_kind=workflow_kind,
        steps=steps,
        budget_envelope=budget_envelope,
        stop_conditions=(
            {"failure": "stop"}
            if stop_conditions is None
            else cast(dict[str, object], stop_conditions)
        ),
    )


def _state(
    step_id: str,
    status: StepRuntimeStatus = StepRuntimeStatus.PENDING,
    *,
    attempt_count: int = 0,
) -> StepState:
    if status is StepRuntimeStatus.RUNNING:
        return StepState(
            step_id=step_id,
            status=status,
            started_at=STARTED,
            attempt_count=attempt_count,
        )
    if status in {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.SKIPPED,
        StepRuntimeStatus.CANCELLED,
    }:
        return StepState(
            step_id=step_id,
            status=status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=attempt_count,
            result_refs=("result-1",) if status is StepRuntimeStatus.SUCCEEDED else (),
            metrics={"quality": 1} if status is StepRuntimeStatus.SUCCEEDED else {},
        )
    if status is StepRuntimeStatus.FAILED:
        return StepState(
            step_id=step_id,
            status=status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=attempt_count,
            block_reason="execution failed",
        )
    if status is StepRuntimeStatus.BLOCKED:
        return StepState(
            step_id=step_id,
            status=status,
            attempt_count=attempt_count,
            block_reason="blocked",
        )
    return StepState(
        step_id=step_id,
        status=status,
        attempt_count=attempt_count,
    )


def _run_state(
    plan: Plan,
    *,
    statuses: dict[str, StepRuntimeStatus] | None = None,
    attempts: dict[str, int] | None = None,
    status: WorkflowStatus = WorkflowStatus.REPLANNING,
    started_at: Instant | None = STARTED,
    plan_version: int | None = None,
) -> RunState:
    effective_statuses = statuses or {}
    effective_attempts = attempts or {}
    return RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version if plan_version is None else plan_version,
        status=status,
        step_states={
            step.step_id: _state(
                step.step_id,
                effective_statuses.get(step.step_id, StepRuntimeStatus.PENDING),
                attempt_count=effective_attempts.get(step.step_id, 0),
            )
            for step in plan.steps
        },
        artifact_refs=("artifact-1",),
        error_refs=("error-1",),
        context_snapshot_ref="context-1",
        started_at=started_at,
    )


def _codes(result: PlanRevisionResult) -> tuple[PlanRevisionCode, ...]:
    return tuple(issue.code for issue in result.issues)


def _progressing_replacement(current: Plan, version: int | None = None) -> Plan:
    return replace(
        current,
        plan_version=current.plan_version + 1 if version is None else version,
        steps=(*current.steps, _step(f"added-v{version or current.plan_version + 1}")),
    )


def test_plan_revision_codes_are_exact() -> None:
    assert [item.value for item in PlanRevisionCode] == [
        "RUN_NOT_REPLANNING",
        "RUN_HAS_ACTIVE_STEP",
        "CURRENT_PLAN_MISMATCH",
        "VERSION_NOT_SEQUENTIAL",
        "MAX_PLAN_VERSIONS_EXCEEDED",
        "RUN_ID_MISMATCH",
        "PLAN_ID_MISMATCH",
        "WORKFLOW_KIND_MISMATCH",
        "OBJECTIVE_MISMATCH",
        "SUCCESS_CRITERIA_MISMATCH",
        "STOP_CONDITIONS_MISMATCH",
        "REPLACEMENT_PLAN_INVALID",
        "STEP_ID_REDEFINED",
        "NO_STRUCTURAL_PROGRESS",
        "STRUCTURAL_CYCLE_DETECTED",
    ]


def test_plan_revision_engine_requires_exact_contract_types() -> None:
    current = _plan(1, _step("root"))
    engine = PlanRevisionEngine()
    with pytest.raises(TypeError, match="history"):
        engine.revise(
            history=cast(PlanHistory, object()),
            run_state=_run_state(current),
            replacement=_progressing_replacement(current),
        )
    with pytest.raises(TypeError, match="run_state"):
        engine.revise(
            history=PlanHistory((current,)),
            run_state=cast(RunState, object()),
            replacement=_progressing_replacement(current),
        )
    with pytest.raises(TypeError, match="replacement"):
        engine.revise(
            history=PlanHistory((current,)),
            run_state=_run_state(current),
            replacement=cast(Plan, object()),
        )


def test_revision_issue_requires_safe_typed_values() -> None:
    with pytest.raises(TypeError, match="PlanRevisionCode"):
        PlanRevisionIssue(cast(PlanRevisionCode, "INVALID"), "message")
    with pytest.raises(ValueError, match="message"):
        PlanRevisionIssue(PlanRevisionCode.RUN_NOT_REPLANNING, " ")


def test_plan_history_requires_non_empty_tuple() -> None:
    with pytest.raises(ValueError, match="empty"):
        PlanHistory(())
    with pytest.raises(TypeError, match="tuple"):
        PlanHistory(cast(tuple[Plan, ...], []))


def test_plan_history_rejects_non_plan_values() -> None:
    with pytest.raises(TypeError, match="Plan"):
        PlanHistory(cast(tuple[Plan, ...], (object(),)))


@pytest.mark.parametrize(
    ("field_name", "new_value", "message"),
    [
        ("run_id", "other-run", "run_id"),
        ("plan_id", "other-plan", "plan_id"),
        ("workflow_kind", "other-workflow", "workflow_kind"),
    ],
)
def test_plan_history_rejects_identity_mismatch(
    field_name: str,
    new_value: str,
    message: str,
) -> None:
    first = _plan(1, _step("v1"))
    second = replace(first, plan_version=2, **{field_name: new_value})

    with pytest.raises(ValueError, match=message):
        PlanHistory((first, second))


def test_plan_history_rejects_non_contiguous_or_non_one_start() -> None:
    first = _plan(1, _step("v1"))
    with pytest.raises(ValueError, match="contiguous"):
        PlanHistory((first, replace(first, plan_version=3)))
    with pytest.raises(ValueError, match="version 1"):
        PlanHistory((replace(first, plan_version=2),))


def test_plan_history_append_is_immutable_and_latest_is_correct() -> None:
    first = _plan(1, _step("v1"))
    second = replace(first, plan_version=2, steps=(_step("v2"),))
    history = PlanHistory((first,))

    appended = history.append(second)

    assert history.plans == (first,)
    assert appended.plans == (first, second)
    assert appended.latest is second
    with pytest.raises(FrozenInstanceError):
        appended.plans = ()  # type: ignore[misc]


def test_revision_rejects_run_not_replanning() -> None:
    current = _plan(1, _step("root"))
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current, status=WorkflowStatus.RUNNING),
        replacement=_progressing_replacement(current),
    )

    assert PlanRevisionCode.RUN_NOT_REPLANNING in _codes(result)


def test_revision_rejects_active_running_step() -> None:
    current = _plan(1, _step("root"))
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(
            current,
            statuses={"root": StepRuntimeStatus.RUNNING},
        ),
        replacement=_progressing_replacement(current),
    )

    assert PlanRevisionCode.RUN_HAS_ACTIVE_STEP in _codes(result)


def test_revision_rejects_current_run_state_mismatch() -> None:
    current = _plan(1, _step("root"))
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current, plan_version=2),
        replacement=_progressing_replacement(current),
    )

    assert PlanRevisionCode.CURRENT_PLAN_MISMATCH in _codes(result)


def test_revision_requires_sequential_version() -> None:
    current = _plan(1, _step("root"))
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=_progressing_replacement(current, version=3),
    )

    assert PlanRevisionCode.VERSION_NOT_SEQUENTIAL in _codes(result)


def _versioned_history(last_version: int) -> PlanHistory:
    first = _plan(1, _step("step-v1"))
    return PlanHistory(
        tuple(
            first
            if version == 1
            else replace(
                first,
                plan_version=version,
                steps=(_step(f"step-v{version}"),),
            )
            for version in range(1, last_version + 1)
        )
    )


def test_version_six_is_accepted_after_version_five() -> None:
    history = _versioned_history(5)
    current = history.latest
    replacement = replace(current, plan_version=6, steps=(_step("step-v6"),))

    result = PlanRevisionEngine().revise(
        history=history,
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert result.accepted
    assert result.history is not None and result.history.latest.plan_version == 6


def test_version_seven_is_rejected_by_hard_limit() -> None:
    history = _versioned_history(6)
    current = history.latest
    replacement = replace(current, plan_version=7, steps=(_step("step-v7"),))

    result = PlanRevisionEngine().revise(
        history=history,
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert PlanRevisionCode.MAX_PLAN_VERSIONS_EXCEEDED in _codes(result)
    assert result.history is None


@pytest.mark.parametrize(
    ("field_name", "new_value", "expected_code"),
    [
        ("run_id", "other-run", PlanRevisionCode.RUN_ID_MISMATCH),
        ("plan_id", "other-plan", PlanRevisionCode.PLAN_ID_MISMATCH),
        (
            "workflow_kind",
            "other-workflow",
            PlanRevisionCode.WORKFLOW_KIND_MISMATCH,
        ),
        ("objective", "Drifted objective", PlanRevisionCode.OBJECTIVE_MISMATCH),
        (
            "success_criteria",
            {"easier": True},
            PlanRevisionCode.SUCCESS_CRITERIA_MISMATCH,
        ),
        (
            "stop_conditions",
            {"failure": "ignore"},
            PlanRevisionCode.STOP_CONDITIONS_MISMATCH,
        ),
    ],
)
def test_revision_rejects_goal_drift(
    field_name: str,
    new_value: object,
    expected_code: PlanRevisionCode,
) -> None:
    current = _plan(1, _step("root"))
    replacement = replace(
        _progressing_replacement(current),
        **{field_name: new_value},
    )

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert expected_code in _codes(result)


def test_invalid_replacement_dag_is_rejected_by_plan_validator() -> None:
    current = _plan(1, _step("root"))
    replacement = replace(
        current,
        plan_version=2,
        steps=(_step("new", depends_on=("missing",)),),
    )

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert PlanRevisionCode.REPLACEMENT_PLAN_INVALID in _codes(result)
    invalid_issue = next(
        issue
        for issue in result.issues
        if issue.code is PlanRevisionCode.REPLACEMENT_PLAN_INVALID
    )
    assert "UNKNOWN_DEPENDENCY" in invalid_issue.message


@pytest.mark.parametrize(
    "replacement_step",
    [
        _step("root", capability="CAP-R02"),
        _step("root", input_refs=("other-input",)),
        _step("root", depends_on=("dependency",)),
    ],
)
def test_same_step_id_cannot_redefine_execution_identity(
    replacement_step: StepSpec,
) -> None:
    current_steps = (
        _step("dependency"),
        _step("root", depends_on=("dependency",))
        if replacement_step.depends_on == ()
        else _step("root"),
    )
    current = _plan(1, *current_steps)
    replacement = replace(
        current,
        plan_version=2,
        steps=(_step("dependency"), replacement_step, _step("added")),
    )

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert PlanRevisionCode.STEP_ID_REDEFINED in _codes(result)


@pytest.mark.parametrize(
    "changed_step",
    [
        _step("root", permission_scope_ref="scope-2"),
        _step("root", budget=BudgetSpec(max_tokens=20)),
        _step("root", failure_policy=FailurePolicy.REPLAN),
    ],
)
def test_control_knob_change_does_not_redefine_step_id(
    changed_step: StepSpec,
) -> None:
    current = _plan(1, _step("root"))
    replacement = replace(current, plan_version=2, steps=(changed_step,))

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert PlanRevisionCode.STEP_ID_REDEFINED not in _codes(result)


def test_succeeded_step_state_is_reused_completely() -> None:
    current = _plan(1, _step("root"))
    old_state = _state("root", StepRuntimeStatus.SUCCEEDED, attempt_count=2)
    run_state = replace(_run_state(current), step_states={"root": old_state})

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=run_state,
        replacement=_progressing_replacement(current),
    )

    assert result.accepted and result.run_state is not None
    assert result.run_state.step_states["root"] is old_state
    assert result.reused_step_ids == ("root",)


@pytest.mark.parametrize(
    "status",
    [
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.SKIPPED,
        StepRuntimeStatus.FAILED,
        StepRuntimeStatus.READY,
        StepRuntimeStatus.PENDING,
        StepRuntimeStatus.BLOCKED,
        StepRuntimeStatus.CANCELLED,
    ],
)
def test_non_succeeded_existing_step_is_reset_with_attempt_lineage(
    status: StepRuntimeStatus,
) -> None:
    current = _plan(1, _step("root"))
    run_state = _run_state(
        current,
        statuses={"root": status},
        attempts={"root": 2},
    )

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=run_state,
        replacement=_progressing_replacement(current),
    )

    assert result.accepted and result.run_state is not None
    state = result.run_state.step_states["root"]
    assert state.status is StepRuntimeStatus.PENDING
    assert state.attempt_count == 2
    assert state.started_at is None and state.ended_at is None
    assert state.result_refs == () and dict(state.metrics) == {}
    assert state.context_slice_ref is None and state.parent_step_id is None
    assert result.reset_step_ids == ("root",)


def test_added_removed_and_state_order_follow_replacement() -> None:
    current = _plan(1, _step("old"), _step("keep"))
    replacement = replace(
        current,
        plan_version=2,
        steps=(_step("new-first"), _step("keep")),
    )

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert result.accepted and result.run_state is not None
    assert tuple(result.run_state.step_states) == ("new-first", "keep")
    assert result.run_state.step_states["new-first"].attempt_count == 0
    assert result.added_step_ids == ("new-first",)
    assert result.removed_step_ids == ("old",)
    assert "old" not in result.run_state.step_states


@pytest.mark.parametrize(
    ("started_at", "expected_status"),
    [
        (None, WorkflowStatus.PLANNED),
        (STARTED, WorkflowStatus.RUNNING),
    ],
)
def test_accepted_revision_resumes_without_calculating_ready(
    started_at: Instant | None,
    expected_status: WorkflowStatus,
) -> None:
    current = _plan(1, _step("root"))
    run_state = _run_state(current, started_at=started_at)

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=run_state,
        replacement=_progressing_replacement(current),
    )

    assert result.accepted and result.run_state is not None
    assert result.run_state.status is expected_status
    assert result.run_state.started_at == started_at
    assert result.run_state.ready_step_ids == ()
    assert result.run_state.artifact_refs == run_state.artifact_refs
    assert result.run_state.error_refs == run_state.error_refs
    assert result.run_state.context_snapshot_ref == run_state.context_snapshot_ref


@pytest.mark.parametrize(
    "changed_step",
    [
        _step("root"),
        _step("root", budget=BudgetSpec(max_tokens=20)),
        _step("root", permission_scope_ref="scope-2"),
        _step("root", failure_policy=FailurePolicy.REPLAN),
    ],
)
def test_control_only_revision_has_no_structural_progress(
    changed_step: StepSpec,
) -> None:
    current = _plan(1, _step("root"))
    replacement = replace(current, plan_version=2, steps=(changed_step,))

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert PlanRevisionCode.NO_STRUCTURAL_PROGRESS in _codes(result)


def test_new_step_id_with_changed_inputs_is_structural_progress() -> None:
    current = _plan(1, _step("old", input_refs=("input-a",)))
    replacement = replace(
        current,
        plan_version=2,
        steps=(_step("new", input_refs=("input-b",)),),
    )

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert result.accepted


def test_new_topology_is_structural_progress() -> None:
    current = _plan(1, _step("old"))
    replacement = replace(
        current,
        plan_version=2,
        steps=(_step("first"), _step("second", depends_on=("first",))),
    )

    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=replacement,
    )

    assert result.accepted


def test_return_to_previous_structure_is_rejected_as_cycle() -> None:
    first = _plan(1, _step("structure-a"))
    second = replace(first, plan_version=2, steps=(_step("structure-b"),))
    proposed = replace(first, plan_version=3)

    result = PlanRevisionEngine().revise(
        history=PlanHistory((first, second)),
        run_state=_run_state(second),
        replacement=proposed,
    )

    assert PlanRevisionCode.STRUCTURAL_CYCLE_DETECTED in _codes(result)
    assert PlanRevisionCode.NO_STRUCTURAL_PROGRESS not in _codes(result)


def test_revision_result_acceptance_invariants() -> None:
    issue = PlanRevisionIssue(PlanRevisionCode.RUN_NOT_REPLANNING, "not replanning")
    with pytest.raises(ValueError, match="issues"):
        PlanRevisionResult(accepted=True, issues=(issue,))
    with pytest.raises(ValueError, match="history"):
        PlanRevisionResult(accepted=True, issues=())
    with pytest.raises(ValueError, match="requires issues"):
        PlanRevisionResult(accepted=False, issues=())


def test_revision_result_rejected_has_no_adopted_state() -> None:
    issue = PlanRevisionIssue(PlanRevisionCode.RUN_NOT_REPLANNING, "not replanning")
    result = PlanRevisionResult(accepted=False, issues=(issue,))

    assert result.history is None and result.run_state is None


def test_revision_result_classification_invariants() -> None:
    current = _plan(1, _step("root"))
    accepted = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(current),
        replacement=_progressing_replacement(current),
    )
    assert accepted.history is not None and accepted.run_state is not None

    with pytest.raises(ValueError, match="disjoint"):
        PlanRevisionResult(
            accepted=True,
            issues=(),
            history=accepted.history,
            run_state=accepted.run_state,
            reused_step_ids=("root",),
            reset_step_ids=("root",),
        )
    with pytest.raises(ValueError, match="removed"):
        PlanRevisionResult(
            accepted=True,
            issues=(),
            history=accepted.history,
            run_state=accepted.run_state,
            removed_step_ids=("root",),
        )
