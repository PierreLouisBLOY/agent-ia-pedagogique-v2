from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.agent_runtime.contracts import ContractRef, WorkflowStatus
from backend.agent_runtime.contracts.common import require_contract_ref
from backend.agent_runtime.runtime.planning.plan import Plan
from backend.agent_runtime.runtime.planning.validation import PlanValidator
from backend.agent_runtime.runtime.state._workflow_statuses import (
    TERMINAL_WORKFLOW_STATUSES,
)
from backend.agent_runtime.runtime.state.step_state import StepRuntimeStatus, StepState
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_STARTED_ACTIVE_STATUSES = frozenset({WorkflowStatus.RUNNING})
_STOP_REASON_REQUIRED_STATUSES = frozenset(
    {WorkflowStatus.FAILED, WorkflowStatus.CANCELLED, WorkflowStatus.ESCALATED}
)


@dataclass(frozen=True, slots=True)
class RunState:
    run_id: str
    correlation_id: CorrelationId
    workflow_kind: str
    plan_id: str
    plan_version: int
    status: WorkflowStatus
    step_states: Mapping[str, StepState]
    artifact_refs: tuple[ContractRef, ...] = ()
    error_refs: tuple[ContractRef, ...] = ()
    context_snapshot_ref: ContractRef | None = None
    started_at: Instant | None = None
    ended_at: Instant | None = None
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.run_id, "run_id")
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        require_non_empty(self.workflow_kind, "workflow_kind")
        require_non_empty(self.plan_id, "plan_id")
        if type(self.plan_version) is not int:
            raise TypeError("plan_version must be an integer")
        if self.plan_version < 1:
            raise ValueError("plan_version must be >= 1")
        if not isinstance(self.status, WorkflowStatus):
            raise TypeError("status must be a WorkflowStatus")
        if not isinstance(self.step_states, Mapping):
            raise TypeError("step_states must be a mapping")
        normalized_states: dict[str, StepState] = {}
        for key, state in self.step_states.items():
            require_non_empty(key, "step_states key")
            if not isinstance(state, StepState):
                raise TypeError("step_states values must be StepState values")
            if key != state.step_id:
                raise ValueError("step_states key must equal StepState.step_id")
            normalized_states[key] = state
        if not isinstance(self.artifact_refs, tuple):
            raise TypeError("artifact_refs must be a tuple")
        if not isinstance(self.error_refs, tuple):
            raise TypeError("error_refs must be a tuple")
        for artifact_ref in self.artifact_refs:
            require_contract_ref(artifact_ref, "artifact_ref")
        for error_ref in self.error_refs:
            require_contract_ref(error_ref, "error_ref")
        if self.context_snapshot_ref is not None:
            require_contract_ref(self.context_snapshot_ref, "context_snapshot_ref")
        if self.started_at is not None and not isinstance(self.started_at, Instant):
            raise TypeError("started_at must be an Instant or None")
        if self.ended_at is not None and not isinstance(self.ended_at, Instant):
            raise TypeError("ended_at must be an Instant or None")
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at.value < self.started_at.value
        ):
            raise ValueError("ended_at must be >= started_at")
        if self.stop_reason is not None:
            require_non_empty(self.stop_reason, "stop_reason")

        if self.status is WorkflowStatus.PLANNED and self.started_at is not None:
            raise ValueError("planned runs must not have started_at")
        if self.status in _STARTED_ACTIVE_STATUSES and (
            self.started_at is None or self.ended_at is not None
        ):
            raise ValueError("active runs require started_at and forbid ended_at")
        if self.status is WorkflowStatus.REPLANNING and self.ended_at is not None:
            raise ValueError("replanning runs must not have ended_at")
        if self.status is WorkflowStatus.WAITING_GATE and self.ended_at is not None:
            raise ValueError("waiting gate runs must not have ended_at")
        if self.status in TERMINAL_WORKFLOW_STATUSES and self.ended_at is None:
            raise ValueError("terminal runs require ended_at")
        if self.status in _STOP_REASON_REQUIRED_STATUSES and self.stop_reason is None:
            raise ValueError("failed, cancelled and escalated runs require stop_reason")

        object.__setattr__(
            self, "step_states", MappingProxyType(normalized_states)
        )

    @property
    def current_step_ids(self) -> tuple[str, ...]:
        return self._step_ids_with_statuses(frozenset({StepRuntimeStatus.RUNNING}))

    @property
    def completed_step_ids(self) -> tuple[str, ...]:
        return self._step_ids_with_statuses(
            frozenset(
                {
                    StepRuntimeStatus.SUCCEEDED,
                    StepRuntimeStatus.PARTIAL,
                    StepRuntimeStatus.SKIPPED,
                }
            )
        )

    @property
    def pending_step_ids(self) -> tuple[str, ...]:
        return self._step_ids_with_statuses(frozenset({StepRuntimeStatus.PENDING}))

    @property
    def ready_step_ids(self) -> tuple[str, ...]:
        return self._step_ids_with_statuses(frozenset({StepRuntimeStatus.READY}))

    @property
    def blocked_step_ids(self) -> tuple[str, ...]:
        return self._step_ids_with_statuses(frozenset({StepRuntimeStatus.BLOCKED}))

    def _step_ids_with_statuses(
        self, statuses: frozenset[StepRuntimeStatus]
    ) -> tuple[str, ...]:
        return tuple(
            step_id
            for step_id, state in self.step_states.items()
            if state.status in statuses
        )


class InvalidInitialPlanError(RuntimeError):
    """Raised when initial technical state is requested for an invalid plan."""


def initialize_run_state(
    plan: Plan,
    correlation_id: CorrelationId,
    *,
    validator: PlanValidator | None = None,
) -> RunState:
    """Validate a plan and create only PENDING state; no step is made READY."""
    if not isinstance(plan, Plan):
        raise TypeError("plan must be a Plan")
    if not isinstance(correlation_id, CorrelationId):
        raise TypeError("correlation_id must be a CorrelationId")
    effective_validator = validator or PlanValidator()
    if not isinstance(effective_validator, PlanValidator):
        raise TypeError("validator must be a PlanValidator or None")
    validation = effective_validator.validate(plan)
    if not validation.valid:
        codes = ", ".join(issue.code.value for issue in validation.issues)
        raise InvalidInitialPlanError(f"plan failed static validation: {codes}")
    return RunState(
        run_id=plan.run_id,
        correlation_id=correlation_id,
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=WorkflowStatus.PLANNED,
        step_states={
            step.step_id: StepState(
                step_id=step.step_id,
                status=StepRuntimeStatus.PENDING,
            )
            for step in plan.steps
        },
    )
