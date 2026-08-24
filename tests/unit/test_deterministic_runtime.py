from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    AgentId,
    BudgetSpec,
    ExecutorKind,
    ExecutorRef,
    StepKind,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.runtime import (
    InvalidInitialPlanError,
    Plan,
    PlanValidationCode,
    PlanValidator,
    RunState,
    StepRuntimeStatus,
    StepState,
    initialize_run_state,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 24, 12, 5, tzinfo=UTC))
EARLIER = Instant(datetime(2026, 8, 24, 11, 55, tzinfo=UTC))


def _step(
    step_id: str = "read",
    *,
    kind: StepKind = StepKind.USE_CASE,
    executor: ExecutorKind = ExecutorKind.APPLICATION,
    capability: str | None = "CAP-R01",
    depends_on: tuple[str, ...] = (),
    parallel_group: str | None = None,
    budget: BudgetSpec | None = None,
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=kind,
        capability_id=CapabilityId(capability) if capability is not None else None,
        executor=ExecutorRef(executor),
        objective=f"Execute {step_id}",
        depends_on=depends_on,
        parallel_group=parallel_group,
        budget=budget,
        output_contract={"type": "result"},
    )


def _plan(
    *steps: StepSpec,
    plan_version: int = 1,
    created_by: AgentId = AgentId.AG_01,
    stop_conditions: Mapping[str, object] | None = None,
    budget_envelope: BudgetSpec | None = None,
) -> Plan:
    return Plan(
        plan_id="plan-1",
        run_id="run-1",
        plan_version=plan_version,
        objective="Produce a deterministic result",
        success_criteria={"accepted": True},
        workflow_kind="opaque-workflow",
        steps=steps or (_step(),),
        gate_refs=("gate-contract",),
        budget_envelope=budget_envelope,
        risk_profile={"level": {"code": "R1"}},
        assumptions={"locale": "fr-FR"},
        stop_conditions=stop_conditions if stop_conditions is not None else {"on_failure": "stop"},
        created_by=created_by,
    )


def _issue_codes(plan: Plan) -> tuple[PlanValidationCode, ...]:
    return tuple(issue.code for issue in PlanValidator().validate(plan).issues)


def _state(step_id: str, status: StepRuntimeStatus) -> StepState:
    if status is StepRuntimeStatus.RUNNING:
        return StepState(step_id=step_id, status=status, started_at=NOW)
    if status in {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.CANCELLED,
        StepRuntimeStatus.SKIPPED,
    }:
        return StepState(step_id=step_id, status=status, ended_at=LATER)
    if status is StepRuntimeStatus.FAILED:
        return StepState(
            step_id=step_id,
            status=status,
            ended_at=LATER,
            error_ref="error-1",
        )
    if status is StepRuntimeStatus.BLOCKED:
        return StepState(step_id=step_id, status=status, block_reason="dependency blocked")
    return StepState(step_id=step_id, status=status)


def _run_state(
    *,
    status: WorkflowStatus = WorkflowStatus.PLANNED,
    step_states: Mapping[str, StepState] | None = None,
    started_at: Instant | None = None,
    ended_at: Instant | None = None,
    stop_reason: str | None = None,
) -> RunState:
    return RunState(
        run_id="run-1",
        correlation_id=CorrelationId("corr-1"),
        workflow_kind="opaque-workflow",
        plan_id="plan-1",
        plan_version=1,
        status=status,
        step_states=step_states or {"read": _state("read", StepRuntimeStatus.PENDING)},
        started_at=started_at,
        ended_at=ended_at,
        stop_reason=stop_reason,
    )


def test_executor_kind_includes_exact_specialized_and_runtime_executors() -> None:
    assert [item.value for item in ExecutorKind] == [
        "AG-02",
        "AG-03",
        "AG-04",
        "APPLICATION",
        "UTILITY",
        "RUNTIME",
    ]


def test_runtime_executor_has_no_agent_id() -> None:
    assert ExecutorRef(ExecutorKind.RUNTIME).agent_id is None


def test_ag01_is_not_a_specialized_executor() -> None:
    assert "AG-01" not in {item.value for item in ExecutorKind}


def test_plan_is_nominally_immutable() -> None:
    plan = _plan()

    with pytest.raises(FrozenInstanceError):
        plan.plan_id = "other"  # type: ignore[misc]


def test_plan_rejects_bool_version() -> None:
    with pytest.raises(TypeError):
        _plan(plan_version=True)  # type: ignore[arg-type]


def test_plan_rejects_version_zero() -> None:
    with pytest.raises(ValueError):
        _plan(plan_version=0)


def test_plan_rejects_non_ag01_creator() -> None:
    with pytest.raises(ValueError):
        _plan(created_by=AgentId.AG_02)


def test_plan_rejects_empty_steps() -> None:
    with pytest.raises(ValueError):
        Plan(
            plan_id="plan-1",
            run_id="run-1",
            plan_version=1,
            objective="objective",
            success_criteria={},
            workflow_kind="opaque",
            steps=(),
            stop_conditions={"failure": "stop"},
        )


def test_plan_rejects_empty_stop_conditions() -> None:
    with pytest.raises(ValueError):
        _plan(stop_conditions={})


def test_plan_mappings_are_deeply_frozen() -> None:
    plan = _plan()

    with pytest.raises(TypeError):
        plan.risk_profile["other"] = "R2"  # type: ignore[index]
    nested = plan.risk_profile["level"]
    assert isinstance(nested, Mapping)
    with pytest.raises(TypeError):
        nested["code"] = "R2"  # type: ignore[index]


def test_step_runtime_status_has_exact_baseline_values() -> None:
    assert [item.value for item in StepRuntimeStatus] == [
        "pending",
        "ready",
        "running",
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "blocked",
        "skipped",
    ]


@pytest.mark.parametrize("status", [StepRuntimeStatus.PENDING, StepRuntimeStatus.READY])
def test_not_started_step_rejects_timestamps(status: StepRuntimeStatus) -> None:
    with pytest.raises(ValueError):
        StepState(step_id="step", status=status, started_at=NOW)


def test_running_step_requires_started_at() -> None:
    with pytest.raises(ValueError):
        StepState(step_id="step", status=StepRuntimeStatus.RUNNING)


@pytest.mark.parametrize(
    "status",
    [
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.FAILED,
        StepRuntimeStatus.CANCELLED,
        StepRuntimeStatus.SKIPPED,
    ],
)
def test_terminal_step_requires_ended_at(status: StepRuntimeStatus) -> None:
    kwargs = {"error_ref": "error-1"} if status is StepRuntimeStatus.FAILED else {}
    with pytest.raises(ValueError):
        StepState(step_id="step", status=status, **kwargs)


def test_failed_step_requires_error_or_block_reason() -> None:
    with pytest.raises(ValueError):
        StepState(step_id="step", status=StepRuntimeStatus.FAILED, ended_at=LATER)


def test_step_rejects_end_before_start() -> None:
    with pytest.raises(ValueError):
        StepState(
            step_id="step",
            status=StepRuntimeStatus.SUCCEEDED,
            started_at=NOW,
            ended_at=EARLIER,
        )


def test_step_metrics_are_deeply_frozen() -> None:
    state = StepState(
        step_id="step",
        status=StepRuntimeStatus.PENDING,
        metrics={"counts": {"items": 2}},
    )

    with pytest.raises(TypeError):
        state.metrics["new"] = 1  # type: ignore[index]
    counts = state.metrics["counts"]
    assert isinstance(counts, Mapping)
    with pytest.raises(TypeError):
        counts["items"] = 3  # type: ignore[index]


def test_run_state_reuses_workflow_status() -> None:
    state = _run_state()
    assert state.status is WorkflowStatus.PLANNED
    assert type(state.status) is WorkflowStatus


def test_run_state_rejects_mapping_key_step_id_mismatch() -> None:
    with pytest.raises(ValueError):
        _run_state(step_states={"other": _state("step", StepRuntimeStatus.PENDING)})


def test_planned_run_rejects_started_at() -> None:
    with pytest.raises(ValueError):
        _run_state(started_at=NOW)


@pytest.mark.parametrize(
    "status",
    [WorkflowStatus.RUNNING, WorkflowStatus.WAITING_GATE, WorkflowStatus.REPLANNING],
)
def test_active_run_requires_started_at(status: WorkflowStatus) -> None:
    with pytest.raises(ValueError):
        _run_state(status=status)


@pytest.mark.parametrize(
    "status",
    [
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    ],
)
def test_terminal_run_requires_ended_at(status: WorkflowStatus) -> None:
    stop_reason = "stopped" if status in {
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    } else None
    with pytest.raises(ValueError):
        _run_state(status=status, stop_reason=stop_reason)


@pytest.mark.parametrize(
    "status",
    [WorkflowStatus.FAILED, WorkflowStatus.CANCELLED, WorkflowStatus.ESCALATED],
)
def test_abnormal_terminal_run_requires_stop_reason(status: WorkflowStatus) -> None:
    with pytest.raises(ValueError):
        _run_state(status=status, ended_at=LATER)


def test_current_step_ids_support_parallel_running_steps() -> None:
    state = _run_state(
        status=WorkflowStatus.RUNNING,
        started_at=NOW,
        step_states={
            "first": _state("first", StepRuntimeStatus.RUNNING),
            "second": _state("second", StepRuntimeStatus.RUNNING),
        },
    )

    assert state.current_step_ids == ("first", "second")


def test_run_state_derived_properties_preserve_mapping_order() -> None:
    state = _run_state(
        step_states={
            "pending": _state("pending", StepRuntimeStatus.PENDING),
            "ready": _state("ready", StepRuntimeStatus.READY),
            "blocked": _state("blocked", StepRuntimeStatus.BLOCKED),
            "succeeded": _state("succeeded", StepRuntimeStatus.SUCCEEDED),
            "partial": _state("partial", StepRuntimeStatus.PARTIAL),
            "skipped": _state("skipped", StepRuntimeStatus.SKIPPED),
        }
    )

    assert state.pending_step_ids == ("pending",)
    assert state.ready_step_ids == ("ready",)
    assert state.blocked_step_ids == ("blocked",)
    assert state.completed_step_ids == ("succeeded", "partial", "skipped")


def test_run_state_has_no_singular_current_step_storage() -> None:
    assert "current_step_id" not in {item.name for item in fields(RunState)}
    assert not hasattr(_run_state(), "current_step_id")


def test_initialize_run_state_validates_and_keeps_all_steps_pending() -> None:
    plan = _plan(
        _step("first"),
        _step("second", depends_on=("first",)),
    )

    state = initialize_run_state(plan, CorrelationId("corr-1"))

    assert state.status is WorkflowStatus.PLANNED
    assert state.pending_step_ids == ("first", "second")
    assert state.ready_step_ids == ()
    assert state.started_at is None


def test_initialize_run_state_rejects_invalid_plan() -> None:
    plan = _plan(_step("step", depends_on=("missing",)))

    with pytest.raises(InvalidInitialPlanError, match="UNKNOWN_DEPENDENCY"):
        initialize_run_state(plan, CorrelationId("corr-1"))


def test_plan_validator_accepts_nominal_dag() -> None:
    plan = _plan(
        _step("read"),
        _step(
            "generate",
            kind=StepKind.AGENT,
            executor=ExecutorKind.AG_03,
            capability="CAP-G01",
            depends_on=("read",),
        ),
        _step(
            "join",
            kind=StepKind.JOIN,
            executor=ExecutorKind.RUNTIME,
            capability="CAP-O04",
            depends_on=("generate",),
        ),
    )

    assert PlanValidator().validate(plan).valid


def test_plan_validator_reports_duplicate_step_id() -> None:
    assert PlanValidationCode.DUPLICATE_STEP_ID in _issue_codes(
        _plan(_step("same"), _step("same"))
    )


def test_plan_validator_reports_unknown_dependency() -> None:
    assert PlanValidationCode.UNKNOWN_DEPENDENCY in _issue_codes(
        _plan(_step("step", depends_on=("missing",)))
    )


def test_plan_validator_reports_transitive_cycle() -> None:
    plan = _plan(
        _step("a", depends_on=("b",)),
        _step("b", depends_on=("c",)),
        _step("c", depends_on=("a",)),
    )

    result = PlanValidator().validate(plan)

    assert PlanValidationCode.DEPENDENCY_CYCLE in tuple(
        issue.code for issue in result.issues
    )
    cycle = next(
        issue
        for issue in result.issues
        if issue.code is PlanValidationCode.DEPENDENCY_CYCLE
    )
    assert cycle.related_step_ids == ("a", "b", "c")


def test_plan_validator_enforces_baseline_step_limit() -> None:
    plan = _plan(*(_step(f"step-{index}") for index in range(25)))
    assert PlanValidationCode.STEP_LIMIT_EXCEEDED in _issue_codes(plan)


def test_plan_validator_reports_unknown_capability() -> None:
    assert PlanValidationCode.UNKNOWN_CAPABILITY in _issue_codes(
        _plan(_step(capability="CAP-X99"))
    )


def test_plan_validator_requires_capability_for_executable_step() -> None:
    result = PlanValidator().validate(_plan(_step(capability=None)))
    issue = next(
        issue
        for issue in result.issues
        if issue.code is PlanValidationCode.UNKNOWN_CAPABILITY
    )
    assert "capability required" in issue.message


@pytest.mark.parametrize(
    "step",
    [
        _step(
            kind=StepKind.AGENT,
            executor=ExecutorKind.APPLICATION,
            capability="CAP-G01",
        ),
        _step(
            kind=StepKind.USE_CASE,
            executor=ExecutorKind.AG_02,
            capability="CAP-R01",
        ),
        _step(
            kind=StepKind.TOOL,
            executor=ExecutorKind.APPLICATION,
            capability="CAP-T01",
        ),
        _step(
            kind=StepKind.JOIN,
            executor=ExecutorKind.UTILITY,
            capability=None,
        ),
    ],
)
def test_plan_validator_reports_kind_executor_mismatch(step: StepSpec) -> None:
    assert PlanValidationCode.KIND_EXECUTOR_MISMATCH in _issue_codes(_plan(step))


def test_plan_validator_reports_agent_owner_mismatch() -> None:
    plan = _plan(
        _step(
            kind=StepKind.AGENT,
            executor=ExecutorKind.AG_02,
            capability="CAP-G01",
        )
    )
    assert PlanValidationCode.AGENT_OWNER_MISMATCH in _issue_codes(plan)


def test_plan_validator_accepts_matching_agent_owner() -> None:
    plan = _plan(
        _step(
            kind=StepKind.AGENT,
            executor=ExecutorKind.AG_03,
            capability="CAP-G01",
        )
    )
    assert PlanValidator().validate(plan).valid


@pytest.mark.parametrize(
    "step",
    [
        _step(capability="CAP-R01"),
        _step(
            kind=StepKind.TOOL,
            executor=ExecutorKind.UTILITY,
            capability="CAP-T01",
        ),
        _step(
            kind=StepKind.JOIN,
            executor=ExecutorKind.RUNTIME,
            capability="CAP-O04",
        ),
    ],
)
def test_plan_validator_accepts_matching_capability_routes(step: StepSpec) -> None:
    assert PlanValidator().validate(_plan(step)).valid


def test_plan_validator_reports_capability_route_mismatch() -> None:
    plan = _plan(_step(capability="CAP-T01"))
    assert PlanValidationCode.CAPABILITY_ROUTE_MISMATCH in _issue_codes(plan)


def test_parallel_group_rejects_direct_dependency() -> None:
    plan = _plan(
        _step("a", parallel_group="group"),
        _step("b", depends_on=("a",), parallel_group="group"),
    )
    assert PlanValidationCode.PARALLEL_DEPENDENCY_CONFLICT in _issue_codes(plan)


def test_parallel_group_rejects_transitive_dependency() -> None:
    plan = _plan(
        _step("a", parallel_group="group"),
        _step("middle", depends_on=("a",)),
        _step("b", depends_on=("middle",), parallel_group="group"),
    )
    assert PlanValidationCode.PARALLEL_DEPENDENCY_CONFLICT in _issue_codes(plan)


def test_parallel_group_accepts_independent_branches() -> None:
    plan = _plan(
        _step("root"),
        _step("left", depends_on=("root",), parallel_group="branches"),
        _step("right", depends_on=("root",), parallel_group="branches"),
    )
    assert PlanValidator().validate(plan).valid


def test_step_budget_narrower_than_plan_is_valid() -> None:
    plan = _plan(
        _step(budget=BudgetSpec(max_tokens=50, max_steps=2)),
        budget_envelope=BudgetSpec(max_tokens=100, max_steps=3),
    )
    assert PlanValidator().validate(plan).valid


def test_step_budget_wider_than_plan_is_rejected() -> None:
    plan = _plan(
        _step(budget=BudgetSpec(max_tokens=101)),
        budget_envelope=BudgetSpec(max_tokens=100),
    )
    assert PlanValidationCode.STEP_BUDGET_OUT_OF_ENVELOPE in _issue_codes(plan)


def test_missing_step_budget_with_bounded_plan_is_rejected() -> None:
    plan = _plan(_step(), budget_envelope=BudgetSpec(max_tokens=100))
    assert PlanValidationCode.STEP_BUDGET_OUT_OF_ENVELOPE in _issue_codes(plan)


def test_plan_validator_result_is_deterministic() -> None:
    plan = _plan(
        _step("same", depends_on=("missing",)),
        _step("same", capability="CAP-X99"),
    )
    validator = PlanValidator()

    assert validator.validate(plan) == validator.validate(plan)


def test_run_and_step_state_are_frozen() -> None:
    run_state = _run_state()
    step_state = run_state.step_states["read"]

    with pytest.raises(FrozenInstanceError):
        run_state.status = WorkflowStatus.RUNNING  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        step_state.status = StepRuntimeStatus.READY  # type: ignore[misc]


def test_step_state_accepts_equal_timestamps() -> None:
    state = StepState(
        step_id="step",
        status=StepRuntimeStatus.SUCCEEDED,
        started_at=NOW,
        ended_at=Instant(NOW.value + timedelta(0)),
    )
    assert state.started_at == state.ended_at
