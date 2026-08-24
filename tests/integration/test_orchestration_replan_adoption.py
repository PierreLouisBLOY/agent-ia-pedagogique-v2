from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from backend.agent_runtime.contracts import (
    ExecutorKind,
    ExecutorRef,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.orchestration import (
    CompletionDisposition,
    OrchestrationCoordinator,
    WorkflowCompletionDecision,
)
from backend.agent_runtime.runtime import (
    Plan,
    PlanHistory,
    PlanRevisionCode,
    PlanRevisionEngine,
    PlanRevisionResult,
    RunState,
    StepRuntimeStatus,
    StepState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 14, 0, tzinfo=UTC))


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


def _plan(version: int, *steps: StepSpec, workflow_kind: str = "WF-4") -> Plan:
    return Plan(
        plan_id="plan-1",
        run_id="run-1",
        plan_version=version,
        objective="Complete the stable objective",
        success_criteria={"globally_complete": True},
        workflow_kind=workflow_kind,
        steps=steps,
        stop_conditions={"failure": "stop"},
    )


def _succeeded(step_id: str) -> StepState:
    return StepState(
        step_id,
        StepRuntimeStatus.SUCCEEDED,
        started_at=NOW,
        ended_at=NOW,
        attempt_count=1,
        result_refs=(f"result-{step_id}",),
    )


def _failed(step_id: str, attempts: int = 1) -> StepState:
    return StepState(
        step_id,
        StepRuntimeStatus.FAILED,
        started_at=NOW,
        ended_at=NOW,
        attempt_count=attempts,
        block_reason="failed before replan",
    )


def _replanning_state(
    plan: Plan,
    states: dict[str, StepState] | None = None,
) -> RunState:
    return RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=WorkflowStatus.REPLANNING,
        step_states=states
        or {
            step.step_id: StepState(step.step_id, StepRuntimeStatus.PENDING)
            for step in plan.steps
        },
        started_at=NOW,
        artifact_refs=("artifact-1",),
        error_refs=("error-1",),
        context_snapshot_ref="context-1",
    )


class NeverCompletionEvaluator:
    def evaluate(
        self,
        *,
        plan: Plan,
        run_state: RunState,
    ) -> WorkflowCompletionDecision:
        del plan, run_state
        return WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "DONE")


def _coordinator(
    revision_engine: PlanRevisionEngine | None = None,
) -> OrchestrationCoordinator:
    return OrchestrationCoordinator(
        NeverCompletionEvaluator(),
        revision_engine or PlanRevisionEngine(),
    )


def _codes(result: PlanRevisionResult) -> tuple[PlanRevisionCode, ...]:
    return tuple(issue.code for issue in result.issues)


def test_coordinator_adopts_valid_v2_and_returns_engine_result_unchanged() -> None:
    first = _step("first")
    retryable = _step("retryable")
    current = _plan(1, first, retryable)
    old_success = _succeeded("first")
    run_state = _replanning_state(
        current,
        {"first": old_success, "retryable": _failed("retryable", attempts=2)},
    )
    replacement = replace(
        current,
        plan_version=2,
        steps=(first, retryable, _step("added")),
    )

    result = _coordinator().apply_replan(
        history=PlanHistory((current,)),
        run_state=run_state,
        replacement=replacement,
    )

    assert result.accepted
    assert result.history is not None and result.history.latest is replacement
    assert result.run_state is not None
    assert result.run_state.plan_version == 2
    assert result.run_state.step_states["first"] is old_success
    assert result.reused_step_ids == ("first",)
    assert result.run_state.step_states["retryable"].status is StepRuntimeStatus.PENDING
    assert result.run_state.step_states["retryable"].attempt_count == 2
    assert result.reset_step_ids == ("retryable",)
    assert result.added_step_ids == ("added",)
    assert result.run_state.step_states["added"].status is StepRuntimeStatus.PENDING
    assert result.run_state.artifact_refs == run_state.artifact_refs
    assert result.run_state.error_refs == run_state.error_refs
    assert result.run_state.context_snapshot_ref == run_state.context_snapshot_ref


def test_max_version_seven_remains_rejected_by_revision_engine() -> None:
    first = _plan(1, _step("step-v1"))
    history = PlanHistory(
        tuple(
            first
            if version == 1
            else replace(first, plan_version=version, steps=(_step(f"step-v{version}"),))
            for version in range(1, 7)
        )
    )
    current = history.latest
    result = _coordinator().apply_replan(
        history=history,
        run_state=_replanning_state(current),
        replacement=replace(current, plan_version=7, steps=(_step("step-v7"),)),
    )
    assert not result.accepted
    assert PlanRevisionCode.MAX_PLAN_VERSIONS_EXCEEDED in _codes(result)


def test_no_progress_remains_rejected_by_revision_engine() -> None:
    current = _plan(1, _step("same"))
    result = _coordinator().apply_replan(
        history=PlanHistory((current,)),
        run_state=_replanning_state(current),
        replacement=replace(current, plan_version=2),
    )
    assert not result.accepted
    assert PlanRevisionCode.NO_STRUCTURAL_PROGRESS in _codes(result)


def test_different_workflow_kind_remains_rejected_by_revision_engine() -> None:
    current = _plan(1, _step("old"))
    replacement = _plan(2, _step("new"), workflow_kind="WF-6")
    result = _coordinator().apply_replan(
        history=PlanHistory((current,)),
        run_state=_replanning_state(current),
        replacement=replacement,
    )
    assert not result.accepted
    assert PlanRevisionCode.WORKFLOW_KIND_MISMATCH in _codes(result)


def test_structural_cycle_remains_rejected_by_revision_engine() -> None:
    first = _plan(1, _step("structure-a"))
    second = replace(first, plan_version=2, steps=(_step("structure-b"),))
    result = _coordinator().apply_replan(
        history=PlanHistory((first, second)),
        run_state=_replanning_state(second),
        replacement=replace(first, plan_version=3),
    )
    assert not result.accepted
    assert PlanRevisionCode.STRUCTURAL_CYCLE_DETECTED in _codes(result)


def test_coordinator_calls_revision_engine_exactly_once_even_on_rejection() -> None:
    calls: list[tuple[PlanHistory, RunState, Plan]] = []

    class CountingRevisionEngine(PlanRevisionEngine):
        def revise(
            self,
            *,
            history: PlanHistory,
            run_state: RunState,
            replacement: Plan,
        ) -> PlanRevisionResult:
            calls.append((history, run_state, replacement))
            return super().revise(
                history=history,
                run_state=run_state,
                replacement=replacement,
            )

    current = _plan(1, _step("same"))
    history = PlanHistory((current,))
    run_state = _replanning_state(current)
    rejected = replace(current, plan_version=2)

    result = _coordinator(CountingRevisionEngine()).apply_replan(
        history=history,
        run_state=run_state,
        replacement=rejected,
    )

    assert not result.accepted
    assert calls == [(history, run_state, rejected)]
