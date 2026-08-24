from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts import AgentId, BudgetSpec, ContractRef, StepSpec
from backend.agent_runtime.contracts.common import (
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class Plan:
    """Immutable declarative plan whose DAG comes only from StepSpec.depends_on."""

    plan_id: str
    run_id: str
    plan_version: int
    objective: str
    success_criteria: Mapping[str, object]
    workflow_kind: str
    steps: tuple[StepSpec, ...]
    gate_refs: tuple[ContractRef, ...] = ()
    budget_envelope: BudgetSpec | None = None
    risk_profile: Mapping[str, object] = field(default_factory=dict)
    assumptions: Mapping[str, object] = field(default_factory=dict)
    stop_conditions: Mapping[str, object] = field(default_factory=dict)
    created_by: AgentId = AgentId.AG_01

    def __post_init__(self) -> None:
        require_non_empty(self.plan_id, "plan_id")
        require_non_empty(self.run_id, "run_id")
        if type(self.plan_version) is not int:
            raise TypeError("plan_version must be an integer")
        if self.plan_version < 1:
            raise ValueError("plan_version must be >= 1")
        require_non_empty(self.objective, "objective")
        require_non_empty(self.workflow_kind, "workflow_kind")
        if not isinstance(self.steps, tuple):
            raise TypeError("steps must be a tuple")
        if not self.steps:
            raise ValueError("steps must not be empty")
        if any(not isinstance(step, StepSpec) for step in self.steps):
            raise TypeError("steps must contain StepSpec values")
        if not isinstance(self.gate_refs, tuple):
            raise TypeError("gate_refs must be a tuple")
        for gate_ref in self.gate_refs:
            require_contract_ref(gate_ref, "gate_ref")
        if self.budget_envelope is not None and not isinstance(
            self.budget_envelope, BudgetSpec
        ):
            raise TypeError("budget_envelope must be a BudgetSpec or None")
        if not isinstance(self.created_by, AgentId):
            raise TypeError("created_by must be an AgentId")
        if self.created_by is not AgentId.AG_01:
            raise ValueError("created_by must be AG-01")

        success_criteria = freeze_agent_safe_mapping(self.success_criteria)
        risk_profile = freeze_agent_safe_mapping(self.risk_profile)
        assumptions = freeze_agent_safe_mapping(self.assumptions)
        stop_conditions = freeze_agent_safe_mapping(self.stop_conditions)
        if not stop_conditions:
            raise ValueError("stop_conditions must not be empty")
        object.__setattr__(self, "success_criteria", success_criteria)
        object.__setattr__(self, "risk_profile", risk_profile)
        object.__setattr__(self, "assumptions", assumptions)
        object.__setattr__(self, "stop_conditions", stop_conditions)
