from __future__ import annotations

import ast
import tomllib
from collections.abc import Mapping
from dataclasses import fields, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, get_type_hints

import pytest

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    ExecutorKind,
    ExecutorRef,
    FailurePolicy,
    RecommendedAction,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    ExecutionDirectiveCode,
    Plan,
    PlanExecutor,
    PlanHistory,
    PlanRevisionCode,
    PlanRevisionEngine,
    PlanValidationCode,
    PlanValidator,
    PreLaunchDecision,
    PreLaunchDisposition,
    RunState,
    SchedulerStateError,
    StepExecutionResult,
    StepRuntimeStatus,
    StepState,
)
from backend.agent_runtime.runtime.state._workflow_statuses import (
    TERMINAL_WORKFLOW_STATUSES,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"
RUNTIME = AGENT_RUNTIME / "runtime"
NOW = Instant(datetime(2026, 8, 24, 16, 0, tzinfo=UTC))
STARTED = Instant(datetime(2026, 8, 24, 15, 0, tzinfo=UTC))


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(path: Path) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return tuple(modules)


def _step(
    step_id: str,
    *,
    capability: str = "CAP-R01",
    depends_on: tuple[str, ...] = (),
    permission_scope_ref: str | None = "scope-1",
    parallel_group: str | None = None,
    failure_policy: FailurePolicy = FailurePolicy.STOP,
    objective: str | None = None,
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=StepKind.USE_CASE,
        capability_id=CapabilityId(capability),
        executor=ExecutorRef(ExecutorKind.APPLICATION),
        objective=objective or f"Execute {step_id}",
        depends_on=depends_on,
        permission_scope_ref=permission_scope_ref,
        failure_policy=failure_policy,
        output_contract={"type": "result"},
        parallel_group=parallel_group,
    )


def _plan(version: int, *steps: StepSpec) -> Plan:
    return Plan(
        plan_id="plan-1",
        run_id="run-1",
        plan_version=version,
        objective="Complete stable objective",
        success_criteria={"complete": True},
        workflow_kind="opaque-workflow",
        steps=steps,
        stop_conditions={"failure": "stop"},
    )


def _state(
    step_id: str,
    status: StepRuntimeStatus,
    *,
    attempt_count: int = 0,
) -> StepState:
    if status is StepRuntimeStatus.RUNNING:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            attempt_count=attempt_count,
        )
    if status is StepRuntimeStatus.SUCCEEDED:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=attempt_count,
            result_refs=("result-1",),
            metrics={"quality": 1},
        )
    if status is StepRuntimeStatus.FAILED:
        return StepState(
            step_id,
            status,
            started_at=STARTED,
            ended_at=NOW,
            attempt_count=attempt_count,
            block_reason="failed",
        )
    if status is StepRuntimeStatus.BLOCKED:
        return StepState(step_id, status, block_reason="blocked")
    return StepState(step_id, status, attempt_count=attempt_count)


def _run_state(
    plan: Plan,
    states: Mapping[str, StepState],
    *,
    status: WorkflowStatus = WorkflowStatus.PLANNED,
    started_at: Instant | None = None,
) -> RunState:
    return RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=status,
        step_states=states,
        started_at=started_at,
    )


def _error(
    step_id: str,
    *,
    attempt: int = 1,
    retryable: bool = False,
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="CLOSURE_ERROR",
        category=ErrorCategory.TRANSIENT,
        source=ErrorSource.APPLICATION,
        retryable=retryable,
        severity=ErrorSeverity.ERROR,
        message="Safe closure error",
        step_id=step_id,
        attempt=attempt,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.STOP,
    )


class ClosureGuard:
    def __init__(
        self,
        disposition: PreLaunchDisposition = PreLaunchDisposition.ALLOW,
        events: list[str] | None = None,
    ) -> None:
        self.disposition = disposition
        self.events = events
        self.calls: list[str] = []

    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        del plan, run_state, now
        self.calls.append(step.step_id)
        if self.events is not None:
            self.events.append(f"guard:{step.step_id}")
        if self.disposition is PreLaunchDisposition.ALLOW:
            return PreLaunchDecision(self.disposition)
        return PreLaunchDecision(self.disposition, "CLOSURE_DENY")


class ClosureRunner:
    def __init__(
        self,
        result: object = None,
        *,
        raises: bool = False,
        events: list[str] | None = None,
    ) -> None:
        self.result = result
        self.raises = raises
        self.events = events
        self.calls: list[str] = []
        self.attempts: list[int] = []

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        del plan, run_state, now
        self.calls.append(step.step_id)
        self.attempts.append(attempt)
        if self.events is not None:
            self.events.append(f"runner:{step.step_id}")
        if self.raises:
            raise RuntimeError("sensitive runner failure")
        if self.result is None:
            return StepExecutionResult(status=StepRuntimeStatus.SUCCEEDED)
        return cast(StepExecutionResult, self.result)


def _execute(
    plan: Plan,
    run_state: RunState,
    guard: ClosureGuard,
    runner: ClosureRunner,
):
    return PlanExecutor(
        scheduler=DeterministicScheduler(),
        prelaunch_guard=guard,
        runner=runner,
    ).execute_cycle(plan=plan, run_state=run_state, now=NOW)


def _revision_codes(result) -> set[PlanRevisionCode]:
    return {issue.code for issue in result.issues}


def test_runtime_structure_boundaries_and_dependencies_are_closed() -> None:
    zones = {
        path.name
        for path in RUNTIME.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
    )
    imports = {
        module
        for path in _python_files(RUNTIME)
        for module in _imported_modules(path)
    }

    assert zones == {"planning", "state", "scheduling", "execution", "routing"}
    assert not (AGENT_RUNTIME / "planning").exists()
    assert all(not module.startswith(forbidden_prefixes) for module in imports)
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        assert tomllib.load(pyproject_file)["project"]["dependencies"] == []


def test_runtime_contracts_keep_one_state_vocabulary_and_derived_current_ids() -> None:
    class_names = {
        node.name
        for path in _python_files(BACKEND)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert ExecutorKind.RUNTIME.value == "RUNTIME"
    assert "AG-01" not in {item.value for item in ExecutorKind}
    assert StepSpec.__dataclass_params__.frozen
    assert Plan.__dataclass_params__.frozen
    assert "status" not in {item.name for item in fields(StepSpec)}
    assert get_type_hints(RunState)["status"] is WorkflowStatus
    assert "RunStatus" not in class_names
    assert "current_step_id" not in {item.name for item in fields(RunState)}
    assert isinstance(RunState.current_step_ids, property)


@pytest.mark.parametrize(
    "plan, expected_code",
    [
        (
            _plan(
                1,
                _step("left", depends_on=("right",)),
                _step("right", depends_on=("left",)),
            ),
            PlanValidationCode.DEPENDENCY_CYCLE,
        ),
        (
            _plan(1, _step("unscoped", permission_scope_ref=None)),
            PlanValidationCode.MISSING_PERMISSION_SCOPE,
        ),
        (
            _plan(
                1,
                _step("left", parallel_group="branches"),
                _step("right", parallel_group="branches"),
            ),
            PlanValidationCode.MISSING_JOIN_STRATEGY,
        ),
        (
            _plan(1, _step("sensitive", capability="CAP-A02")),
            PlanValidationCode.REQUIRED_GATE_MISSING,
        ),
    ],
)
def test_static_plan_safety_findings_remain_closed(
    plan: Plan,
    expected_code: PlanValidationCode,
) -> None:
    result = PlanValidator().validate(plan)

    assert not result.valid
    assert expected_code in {issue.code for issue in result.issues}


def test_scheduler_makes_root_candidate_ready_without_launching_it() -> None:
    plan = _plan(1, _step("root"))
    decision = DeterministicScheduler().schedule(
        plan=plan,
        run_state=_run_state(
            plan,
            {"root": _state("root", StepRuntimeStatus.PENDING)},
        ),
        now=NOW,
    )

    assert decision.launch_candidate_ids == ("root",)
    assert decision.run_state.step_states["root"].status is StepRuntimeStatus.READY


def test_scheduler_propagates_failed_dependency_blocking_to_fixed_point() -> None:
    plan = _plan(
        1,
        _step("failed"),
        _step("middle", depends_on=("failed",)),
        _step("tail", depends_on=("middle",)),
    )
    decision = DeterministicScheduler().schedule(
        plan=plan,
        run_state=_run_state(
            plan,
            {
                "failed": _state("failed", StepRuntimeStatus.FAILED),
                "middle": _state("middle", StepRuntimeStatus.PENDING),
                "tail": _state("tail", StepRuntimeStatus.PENDING),
            },
        ),
        now=NOW,
    )

    assert decision.run_state.blocked_step_ids == ("middle", "tail")


def test_scheduler_rejects_parallel_overflow_instead_of_masking_it() -> None:
    plan = _plan(1, *(_step(f"step-{index}") for index in range(5)))
    run_state = _run_state(
        plan,
        {
            step.step_id: _state(step.step_id, StepRuntimeStatus.RUNNING)
            for step in plan.steps
        },
        status=WorkflowStatus.RUNNING,
        started_at=STARTED,
    )

    with pytest.raises(SchedulerStateError, match="max_parallel_steps"):
        DeterministicScheduler().schedule(plan=plan, run_state=run_state, now=NOW)


@pytest.mark.parametrize(
    "status",
    [WorkflowStatus.WAITING_GATE, WorkflowStatus.REPLANNING],
)
def test_scheduler_suspended_runs_have_no_candidates(status: WorkflowStatus) -> None:
    plan = _plan(1, _step("root"))
    decision = DeterministicScheduler().schedule(
        plan=plan,
        run_state=_run_state(
            plan,
            {"root": _state("root", StepRuntimeStatus.PENDING)},
            status=status,
        ),
        now=NOW,
    )

    assert decision.launch_candidate_ids == ()


def test_executor_calls_guard_before_runner_and_increments_attempt_once() -> None:
    events: list[str] = []
    plan = _plan(1, _step("root"))
    guard = ClosureGuard(events=events)
    runner = ClosureRunner(events=events)
    result = _execute(
        plan,
        _run_state(plan, {"root": _state("root", StepRuntimeStatus.READY)}),
        guard,
        runner,
    )

    assert events == ["guard:root", "runner:root"]
    assert runner.attempts == [1]
    assert result.run_state.step_states["root"].attempt_count == 1


def test_executor_prelaunch_deny_never_calls_runner() -> None:
    plan = _plan(1, _step("root"))
    guard = ClosureGuard(PreLaunchDisposition.DENY)
    runner = ClosureRunner()
    result = _execute(
        plan,
        _run_state(plan, {"root": _state("root", StepRuntimeStatus.READY)}),
        guard,
        runner,
    )

    assert runner.calls == []
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.BLOCKED


@pytest.mark.parametrize(
    ("runner", "attempt_count", "expected_reason"),
    [
        (
            ClosureRunner(raises=True),
            0,
            "RUNNER_EXCEPTION_EFFECT_UNKNOWN",
        ),
        (
            ClosureRunner({"invalid": "result"}),
            0,
            "RUNNER_RESULT_CONTRACT_INVALID_EFFECT_UNKNOWN",
        ),
        (
            ClosureRunner(
                StepExecutionResult(
                    status=StepRuntimeStatus.FAILED,
                    error=_error("other-step"),
                )
            ),
            0,
            "RUNNER_ERROR_STEP_MISMATCH_EFFECT_UNKNOWN",
        ),
        (
            ClosureRunner(
                StepExecutionResult(
                    status=StepRuntimeStatus.FAILED,
                    error=_error("root", attempt=1),
                )
            ),
            1,
            "RUNNER_ERROR_ATTEMPT_MISMATCH_EFFECT_UNKNOWN",
        ),
    ],
)
def test_post_runner_uncertainty_always_reconciles_without_replay(
    runner: ClosureRunner,
    attempt_count: int,
    expected_reason: str,
) -> None:
    plan = _plan(1, _step("root"), _step("second"))
    result = _execute(
        plan,
        _run_state(
            plan,
            {
                "root": _state(
                    "root",
                    StepRuntimeStatus.READY,
                    attempt_count=attempt_count,
                ),
                "second": _state("second", StepRuntimeStatus.READY),
            },
        ),
        ClosureGuard(),
        runner,
    )

    assert runner.calls == ["root"]
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.RUNNING
    assert result.completed_step_ids == ()
    assert result.directives[0].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert result.directives[0].reason_code == expected_reason


def test_terminal_run_snapshot_is_strict_noop() -> None:
    plan = _plan(1, _step("root"))
    terminal = RunState(
        run_id=plan.run_id,
        correlation_id=CorrelationId("corr-1"),
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=WorkflowStatus.FAILED,
        step_states={"root": _state("root", StepRuntimeStatus.PENDING)},
        ended_at=NOW,
        stop_reason="terminal",
    )

    result = _execute(plan, terminal, ClosureGuard(), ClosureRunner())

    assert result.run_state is terminal
    assert result.run_state.step_states["root"].status is StepRuntimeStatus.PENDING


def test_retry_failure_policy_emits_directive_without_automatic_retry() -> None:
    plan = _plan(1, _step("root", failure_policy=FailurePolicy.RETRY))
    runner = ClosureRunner(
        StepExecutionResult(
            status=StepRuntimeStatus.FAILED,
            error=_error("root", retryable=True),
        )
    )
    result = _execute(
        plan,
        _run_state(plan, {"root": _state("root", StepRuntimeStatus.READY)}),
        ClosureGuard(),
        runner,
    )

    assert runner.calls == ["root"]
    assert result.directives[0].code is ExecutionDirectiveCode.RETRY_REQUIRED


def test_revision_reuses_success_and_returns_pending_without_launch() -> None:
    current = _plan(1, _step("root"))
    succeeded = _state("root", StepRuntimeStatus.SUCCEEDED, attempt_count=1)
    replacement = replace(
        current,
        plan_version=2,
        steps=(*current.steps, _step("added")),
    )
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(
            current,
            {"root": succeeded},
            status=WorkflowStatus.REPLANNING,
            started_at=STARTED,
        ),
        replacement=replacement,
    )

    assert result.accepted and result.run_state is not None
    assert result.history is not None and result.history.latest is replacement
    assert result.run_state.step_states["root"] is succeeded
    assert result.run_state.step_states["added"].status is StepRuntimeStatus.PENDING
    assert result.run_state.ready_step_ids == ()


def test_revision_resets_failed_lineage_to_pending_with_attempt_preserved() -> None:
    current = _plan(1, _step("root"))
    replacement = replace(
        current,
        plan_version=2,
        steps=(*current.steps, _step("added")),
    )
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(
            current,
            {"root": _state("root", StepRuntimeStatus.FAILED, attempt_count=2)},
            status=WorkflowStatus.REPLANNING,
            started_at=STARTED,
        ),
        replacement=replacement,
    )

    assert result.accepted and result.run_state is not None
    reset = result.run_state.step_states["root"]
    assert reset.status is StepRuntimeStatus.PENDING
    assert reset.attempt_count == 2


def _history(last_version: int) -> PlanHistory:
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


def test_revision_refuses_version_seven_from_policy_hard_limit() -> None:
    history = _history(6)
    current = history.latest
    result = PlanRevisionEngine().revise(
        history=history,
        run_state=_run_state(
            current,
            {"step-v6": _state("step-v6", StepRuntimeStatus.PENDING)},
            status=WorkflowStatus.REPLANNING,
            started_at=STARTED,
        ),
        replacement=replace(current, plan_version=7, steps=(_step("step-v7"),)),
    )

    assert PlanRevisionCode.MAX_PLAN_VERSIONS_EXCEEDED in _revision_codes(result)


@pytest.mark.parametrize(
    ("field_name", "new_value", "expected_code"),
    [
        ("objective", "Drift", PlanRevisionCode.OBJECTIVE_MISMATCH),
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
def test_revision_refuses_goal_drift(
    field_name: str,
    new_value: object,
    expected_code: PlanRevisionCode,
) -> None:
    current = _plan(1, _step("root"))
    replacement = replace(
        current,
        plan_version=2,
        steps=(*current.steps, _step("added")),
        **{field_name: new_value},
    )
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(
            current,
            {"root": _state("root", StepRuntimeStatus.PENDING)},
            status=WorkflowStatus.REPLANNING,
            started_at=STARTED,
        ),
        replacement=replacement,
    )

    assert expected_code in _revision_codes(result)


def test_revision_refuses_step_id_execution_identity_redefinition() -> None:
    current = _plan(1, _step("root"))
    replacement = replace(
        current,
        plan_version=2,
        steps=(_step("root", objective="Changed meaning"), _step("added")),
    )
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(
            current,
            {"root": _state("root", StepRuntimeStatus.PENDING)},
            status=WorkflowStatus.REPLANNING,
            started_at=STARTED,
        ),
        replacement=replacement,
    )

    assert PlanRevisionCode.STEP_ID_REDEFINED in _revision_codes(result)


def test_revision_refuses_no_structural_progress() -> None:
    current = _plan(1, _step("root"))
    result = PlanRevisionEngine().revise(
        history=PlanHistory((current,)),
        run_state=_run_state(
            current,
            {"root": _state("root", StepRuntimeStatus.PENDING)},
            status=WorkflowStatus.REPLANNING,
            started_at=STARTED,
        ),
        replacement=replace(current, plan_version=2),
    )

    assert PlanRevisionCode.NO_STRUCTURAL_PROGRESS in _revision_codes(result)


def test_revision_refuses_structural_cycle_a_b_a() -> None:
    first = _plan(1, _step("structure-a"))
    second = replace(first, plan_version=2, steps=(_step("structure-b"),))
    result = PlanRevisionEngine().revise(
        history=PlanHistory((first, second)),
        run_state=_run_state(
            second,
            {"structure-b": _state("structure-b", StepRuntimeStatus.PENDING)},
            status=WorkflowStatus.REPLANNING,
            started_at=STARTED,
        ),
        replacement=replace(first, plan_version=3),
    )

    assert PlanRevisionCode.STRUCTURAL_CYCLE_DETECTED in _revision_codes(result)


def test_d_to_e_boundary_keeps_external_replacement_and_validator() -> None:
    executor_source = (
        RUNTIME / "execution" / "executor.py"
    ).read_text(encoding="utf-8")
    revision_source = (
        RUNTIME / "planning" / "revision.py"
    ).read_text(encoding="utf-8")

    assert "PlanRevisionEngine" not in executor_source
    assert "Plan(" not in executor_source
    assert "self.validator.validate(replacement)" in revision_source
    assert "Plan(" not in revision_source


def test_terminal_workflow_statuses_have_one_internal_runtime_source() -> None:
    run_state_source = (
        RUNTIME / "state" / "run_state.py"
    ).read_text(encoding="utf-8")
    executor_source = (
        RUNTIME / "execution" / "executor.py"
    ).read_text(encoding="utf-8")

    assert TERMINAL_WORKFLOW_STATUSES == frozenset(
        {
            WorkflowStatus.SUCCEEDED,
            WorkflowStatus.PARTIAL,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.ESCALATED,
        }
    )
    assert "TERMINAL_WORKFLOW_STATUSES" in run_state_source
    assert "TERMINAL_WORKFLOW_STATUSES" in executor_source
    assert "_RUN_TERMINAL_STATUSES" not in executor_source
