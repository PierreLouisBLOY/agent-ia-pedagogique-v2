from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    AgentId,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.policy import BudgetSpec
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class StepKind(StrEnum):
    AGENT = "agent"
    USE_CASE = "use_case"
    TOOL = "tool"
    GATE = "gate"
    JOIN = "join"
    DECISION = "decision"


class FailurePolicy(StrEnum):
    RETRY = "retry"
    REPLAN = "replan"
    ESCALATE = "escalate"
    STOP = "stop"


class ExecutorKind(StrEnum):
    AG_02 = "AG-02"
    AG_03 = "AG-03"
    AG_04 = "AG-04"
    APPLICATION = "APPLICATION"
    UTILITY = "UTILITY"
    RUNTIME = "RUNTIME"


_EXECUTOR_AGENT_IDS = {
    ExecutorKind.AG_02: AgentId.AG_02,
    ExecutorKind.AG_03: AgentId.AG_03,
    ExecutorKind.AG_04: AgentId.AG_04,
}


@dataclass(frozen=True, slots=True)
class ExecutorRef:
    """Reference to one of the executors allowed by StepSpec."""

    kind: ExecutorKind

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ExecutorKind):
            raise TypeError("kind must be an ExecutorKind")

    @property
    def agent_id(self) -> AgentId | None:
        return _EXECUTOR_AGENT_IDS.get(self.kind)


@dataclass(frozen=True, slots=True)
class StepSpec:
    """Immutable declarative work-unit specification with no runtime status."""

    step_id: str
    kind: StepKind
    capability_id: CapabilityId | None
    executor: ExecutorRef
    objective: str
    input_refs: tuple[ContractRef, ...] = ()
    depends_on: tuple[str, ...] = ()
    permission_scope_ref: ContractRef | None = None
    budget: BudgetSpec | None = None
    success_criteria: Mapping[str, object] = field(default_factory=dict)
    failure_policy: FailurePolicy = FailurePolicy.STOP
    output_contract: Mapping[str, object] = field(default_factory=dict)
    parallel_group: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.step_id, "step_id")
        if not isinstance(self.kind, StepKind):
            raise TypeError("kind must be a StepKind")
        if self.capability_id is not None and not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(self.executor, ExecutorRef):
            raise TypeError("executor must be an ExecutorRef")
        require_non_empty(self.objective, "objective")
        input_refs = tuple(self.input_refs)
        for input_ref in input_refs:
            require_contract_ref(input_ref, "input_ref")
        depends_on = tuple(self.depends_on)
        for dependency in depends_on:
            require_non_empty(dependency, "dependency")
        if self.step_id in depends_on:
            raise ValueError("depends_on must not contain step_id")
        if self.permission_scope_ref is not None:
            require_contract_ref(self.permission_scope_ref, "permission_scope_ref")
        if self.budget is not None and not isinstance(self.budget, BudgetSpec):
            raise TypeError("budget must be a BudgetSpec")
        if not isinstance(self.failure_policy, FailurePolicy):
            raise TypeError("failure_policy must be a FailurePolicy")
        if not self.output_contract:
            raise ValueError("output_contract must not be empty")
        if self.parallel_group is not None:
            require_non_empty(self.parallel_group, "parallel_group")
        object.__setattr__(self, "input_refs", input_refs)
        object.__setattr__(self, "depends_on", depends_on)
        object.__setattr__(
            self,
            "success_criteria",
            freeze_agent_safe_mapping(self.success_criteria),
        )
        object.__setattr__(
            self,
            "output_contract",
            freeze_agent_safe_mapping(self.output_contract),
        )
