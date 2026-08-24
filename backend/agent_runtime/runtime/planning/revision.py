from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts import StepSpec, WorkflowStatus
from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)
from backend.agent_runtime.runtime.planning.plan import Plan
from backend.agent_runtime.runtime.planning.validation import PlanValidator
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus, StepState
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class PlanHistory:
    plans: tuple[Plan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plans, tuple):
            raise TypeError("plans must be a tuple")
        if not self.plans:
            raise ValueError("plans must not be empty")
        if any(not isinstance(plan, Plan) for plan in self.plans):
            raise TypeError("plans must contain Plan values")

        first = self.plans[0]
        if first.plan_version != 1:
            raise ValueError("plan history must start at version 1")
        for expected_version, plan in enumerate(self.plans, start=1):
            if plan.run_id != first.run_id:
                raise ValueError("plan history must have one run_id")
            if plan.plan_id != first.plan_id:
                raise ValueError("plan history must have one plan_id")
            if plan.workflow_kind != first.workflow_kind:
                raise ValueError("plan history must have one workflow_kind")
            if plan.plan_version != expected_version:
                raise ValueError("plan history versions must be contiguous")

    @property
    def latest(self) -> Plan:
        return self.plans[-1]

    def append(self, plan: Plan) -> PlanHistory:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        return PlanHistory((*self.plans, plan))


class PlanRevisionCode(StrEnum):
    RUN_NOT_REPLANNING = "RUN_NOT_REPLANNING"
    RUN_HAS_ACTIVE_STEP = "RUN_HAS_ACTIVE_STEP"
    CURRENT_PLAN_MISMATCH = "CURRENT_PLAN_MISMATCH"
    VERSION_NOT_SEQUENTIAL = "VERSION_NOT_SEQUENTIAL"
    MAX_PLAN_VERSIONS_EXCEEDED = "MAX_PLAN_VERSIONS_EXCEEDED"
    RUN_ID_MISMATCH = "RUN_ID_MISMATCH"
    PLAN_ID_MISMATCH = "PLAN_ID_MISMATCH"
    WORKFLOW_KIND_MISMATCH = "WORKFLOW_KIND_MISMATCH"
    OBJECTIVE_MISMATCH = "OBJECTIVE_MISMATCH"
    SUCCESS_CRITERIA_MISMATCH = "SUCCESS_CRITERIA_MISMATCH"
    STOP_CONDITIONS_MISMATCH = "STOP_CONDITIONS_MISMATCH"
    REPLACEMENT_PLAN_INVALID = "REPLACEMENT_PLAN_INVALID"
    STEP_ID_REDEFINED = "STEP_ID_REDEFINED"
    NO_STRUCTURAL_PROGRESS = "NO_STRUCTURAL_PROGRESS"
    STRUCTURAL_CYCLE_DETECTED = "STRUCTURAL_CYCLE_DETECTED"


@dataclass(frozen=True, slots=True)
class PlanRevisionIssue:
    code: PlanRevisionCode
    message: str
    step_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, PlanRevisionCode):
            raise TypeError("code must be a PlanRevisionCode")
        require_non_empty(self.message, "message")
        if self.step_id is not None:
            require_non_empty(self.step_id, "step_id")


@dataclass(frozen=True, slots=True)
class PlanRevisionResult:
    accepted: bool
    issues: tuple[PlanRevisionIssue, ...]
    history: PlanHistory | None = None
    run_state: RunState | None = None
    reused_step_ids: tuple[str, ...] = ()
    reset_step_ids: tuple[str, ...] = ()
    added_step_ids: tuple[str, ...] = ()
    removed_step_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be a bool")
        if not isinstance(self.issues, tuple):
            raise TypeError("issues must be a tuple")
        if any(not isinstance(issue, PlanRevisionIssue) for issue in self.issues):
            raise TypeError("issues must contain PlanRevisionIssue values")
        if self.history is not None and not isinstance(self.history, PlanHistory):
            raise TypeError("history must be a PlanHistory or None")
        if self.run_state is not None and not isinstance(self.run_state, RunState):
            raise TypeError("run_state must be a RunState or None")

        id_fields = (
            "reused_step_ids",
            "reset_step_ids",
            "added_step_ids",
            "removed_step_ids",
        )
        for field_name in id_fields:
            step_ids = getattr(self, field_name)
            if not isinstance(step_ids, tuple):
                raise TypeError(f"{field_name} must be a tuple")
            if len(set(step_ids)) != len(step_ids):
                raise ValueError(f"{field_name} must contain unique ids")
            for step_id in step_ids:
                require_non_empty(step_id, field_name)

        if self.accepted:
            if self.issues:
                raise ValueError("accepted revision must not have issues")
            if self.history is None or self.run_state is None:
                raise ValueError("accepted revision requires history and run_state")
        else:
            if not self.issues:
                raise ValueError("rejected revision requires issues")
            if self.history is not None or self.run_state is not None:
                raise ValueError("rejected revision must not expose history or run_state")
            if any(getattr(self, field_name) for field_name in id_fields):
                raise ValueError("rejected revision must not classify step ids")
            return

        classified = (
            set(self.reused_step_ids),
            set(self.reset_step_ids),
            set(self.added_step_ids),
        )
        if any(left.intersection(right) for index, left in enumerate(classified) for right in classified[index + 1 :]):
            raise ValueError("reused, reset and added ids must be disjoint")
        assert self.run_state is not None
        current_ids = set(self.run_state.step_states)
        if not set().union(*classified).issubset(current_ids):
            raise ValueError("reused, reset and added ids must exist in run_state")
        if set(self.removed_step_ids).intersection(current_ids):
            raise ValueError("removed ids must not exist in run_state")


@dataclass(frozen=True, slots=True)
class PlanRevisionEngine:
    validator: PlanValidator = PlanValidator()
    runtime_policy: AgentRuntimePolicy = BASELINE_AGENT_RUNTIME_POLICY

    def __post_init__(self) -> None:
        if not isinstance(self.validator, PlanValidator):
            raise TypeError("validator must be a PlanValidator")
        if not isinstance(self.runtime_policy, AgentRuntimePolicy):
            raise TypeError("runtime_policy must be an AgentRuntimePolicy")

    def revise(
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

        current = history.latest
        issues: list[PlanRevisionIssue] = []
        if not _run_matches_current(run_state, current):
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.CURRENT_PLAN_MISMATCH,
                    "run state does not match current plan",
                )
            )
        if run_state.status is not WorkflowStatus.REPLANNING:
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.RUN_NOT_REPLANNING,
                    "run is not in replanning status",
                )
            )
        if run_state.current_step_ids:
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.RUN_HAS_ACTIVE_STEP,
                    "run has an active step",
                )
            )
        if replacement.plan_version != current.plan_version + 1:
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.VERSION_NOT_SEQUENTIAL,
                    "replacement version is not current version plus one",
                )
            )
        if replacement.plan_version > self.runtime_policy.max_plan_versions:
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.MAX_PLAN_VERSIONS_EXCEEDED,
                    "replacement exceeds maximum plan versions",
                )
            )

        _append_mismatch_issue(
            issues,
            replacement.run_id != current.run_id,
            PlanRevisionCode.RUN_ID_MISMATCH,
            "replacement run_id differs from current plan",
        )
        _append_mismatch_issue(
            issues,
            replacement.plan_id != current.plan_id,
            PlanRevisionCode.PLAN_ID_MISMATCH,
            "replacement plan_id differs from current plan",
        )
        _append_mismatch_issue(
            issues,
            replacement.workflow_kind != current.workflow_kind,
            PlanRevisionCode.WORKFLOW_KIND_MISMATCH,
            "replacement workflow_kind differs from current plan",
        )
        _append_mismatch_issue(
            issues,
            replacement.objective != current.objective,
            PlanRevisionCode.OBJECTIVE_MISMATCH,
            "replacement objective differs from current plan",
        )
        _append_mismatch_issue(
            issues,
            replacement.success_criteria != current.success_criteria,
            PlanRevisionCode.SUCCESS_CRITERIA_MISMATCH,
            "replacement success criteria differ from current plan",
        )
        _append_mismatch_issue(
            issues,
            replacement.stop_conditions != current.stop_conditions,
            PlanRevisionCode.STOP_CONDITIONS_MISMATCH,
            "replacement stop conditions differ from current plan",
        )

        validation = self.validator.validate(replacement)
        if not validation.valid:
            validation_codes = ",".join(issue.code.value for issue in validation.issues)
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.REPLACEMENT_PLAN_INVALID,
                    f"replacement failed static validation: {validation_codes}",
                )
            )

        current_steps = {step.step_id: step for step in current.steps}
        for new_step in replacement.steps:
            old_step = current_steps.get(new_step.step_id)
            if old_step is not None and _step_execution_identity(
                old_step
            ) != _step_execution_identity(new_step):
                issues.append(
                    PlanRevisionIssue(
                        PlanRevisionCode.STEP_ID_REDEFINED,
                        "step_id has a different execution identity",
                        step_id=new_step.step_id,
                    )
                )

        replacement_signature = _plan_execution_signature(replacement)
        if replacement_signature == _plan_execution_signature(current):
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.NO_STRUCTURAL_PROGRESS,
                    "replacement has no structural execution progress",
                )
            )
        if any(
            replacement_signature == _plan_execution_signature(previous)
            for previous in history.plans[:-1]
        ):
            issues.append(
                PlanRevisionIssue(
                    PlanRevisionCode.STRUCTURAL_CYCLE_DETECTED,
                    "replacement returns to an earlier execution structure",
                )
            )

        if issues:
            return PlanRevisionResult(accepted=False, issues=tuple(issues))
        return _accepted_revision(history, run_state, replacement)


def _append_mismatch_issue(
    issues: list[PlanRevisionIssue],
    mismatch: bool,
    code: PlanRevisionCode,
    message: str,
) -> None:
    if mismatch:
        issues.append(PlanRevisionIssue(code, message))


def _run_matches_current(run_state: RunState, current: Plan) -> bool:
    return bool(
        run_state.run_id == current.run_id
        and run_state.plan_id == current.plan_id
        and run_state.plan_version == current.plan_version
        and run_state.workflow_kind == current.workflow_kind
        and tuple(run_state.step_states) == tuple(step.step_id for step in current.steps)
    )


def _step_execution_identity(step: StepSpec) -> tuple[object, ...]:
    return (
        step.kind,
        step.capability_id,
        step.executor,
        step.objective,
        step.input_refs,
        step.depends_on,
        step.success_criteria,
        step.output_contract,
        step.parallel_group,
    )


def _plan_execution_signature(plan: Plan) -> tuple[object, ...]:
    return tuple(
        (step.step_id, _step_execution_identity(step)) for step in plan.steps
    )


def _accepted_revision(
    history: PlanHistory,
    run_state: RunState,
    replacement: Plan,
) -> PlanRevisionResult:
    current = history.latest
    old_steps = {step.step_id: step for step in current.steps}
    replacement_ids = {step.step_id for step in replacement.steps}
    new_states: dict[str, StepState] = {}
    reused: list[str] = []
    reset: list[str] = []
    added: list[str] = []

    for step in replacement.steps:
        old_step = old_steps.get(step.step_id)
        if old_step is None:
            new_states[step.step_id] = StepState(
                step_id=step.step_id,
                status=StepRuntimeStatus.PENDING,
            )
            added.append(step.step_id)
            continue

        old_state = run_state.step_states[step.step_id]
        if old_state.status is StepRuntimeStatus.SUCCEEDED:
            new_states[step.step_id] = old_state
            reused.append(step.step_id)
            continue
        new_states[step.step_id] = StepState(
            step_id=step.step_id,
            status=StepRuntimeStatus.PENDING,
            attempt_count=old_state.attempt_count,
        )
        reset.append(step.step_id)

    removed = tuple(
        step.step_id for step in current.steps if step.step_id not in replacement_ids
    )
    started_at = run_state.started_at
    revised_state = RunState(
        run_id=run_state.run_id,
        correlation_id=run_state.correlation_id,
        workflow_kind=run_state.workflow_kind,
        plan_id=run_state.plan_id,
        plan_version=replacement.plan_version,
        status=(
            WorkflowStatus.PLANNED
            if started_at is None
            else WorkflowStatus.RUNNING
        ),
        step_states=new_states,
        artifact_refs=run_state.artifact_refs,
        error_refs=run_state.error_refs,
        context_snapshot_ref=run_state.context_snapshot_ref,
        started_at=started_at,
        ended_at=None,
        stop_reason=None,
    )
    return PlanRevisionResult(
        accepted=True,
        issues=(),
        history=history.append(replacement),
        run_state=revised_state,
        reused_step_ids=tuple(reused),
        reset_step_ids=tuple(reset),
        added_step_ids=tuple(added),
        removed_step_ids=removed,
    )
