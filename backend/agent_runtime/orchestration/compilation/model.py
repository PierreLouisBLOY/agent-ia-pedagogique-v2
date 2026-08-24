from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts import (
    BudgetSpec,
    ContractRef,
    FailurePolicy,
)
from backend.agent_runtime.contracts.common import (
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.orchestration.selection import (
    WorkflowSelectionDecision,
    WorkflowSelectionStatus,
)
from backend.agent_runtime.orchestration.workflows import WorkflowResponsibility
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class HumanGateAnchor(StrEnum):
    BEFORE_FIRST_STAGE = "BEFORE_FIRST_STAGE"
    AFTER_EVIDENCE = "AFTER_EVIDENCE"
    AFTER_REVIEW = "AFTER_REVIEW"
    BEFORE_PROMOTION = "BEFORE_PROMOTION"


class PlanCompilationCode(StrEnum):
    WAITING_HUMAN_NOT_COMPILABLE = "WAITING_HUMAN_NOT_COMPILABLE"
    MISSING_STAGE_BINDING = "MISSING_STAGE_BINDING"
    UNEXPECTED_STAGE_BINDING = "UNEXPECTED_STAGE_BINDING"
    DUPLICATE_STEP_ID = "DUPLICATE_STEP_ID"
    INVALID_BRANCH_CARDINALITY = "INVALID_BRANCH_CARDINALITY"
    INVALID_BRANCH_INDEX = "INVALID_BRANCH_INDEX"
    CAPABILITY_REQUIRED = "CAPABILITY_REQUIRED"
    CAPABILITY_NOT_ALLOWED = "CAPABILITY_NOT_ALLOWED"
    PERMISSION_SCOPE_REQUIRED = "PERMISSION_SCOPE_REQUIRED"
    HUMAN_GATE_BINDING_REQUIRED = "HUMAN_GATE_BINDING_REQUIRED"
    HUMAN_GATE_BINDING_FORBIDDEN = "HUMAN_GATE_BINDING_FORBIDDEN"
    HUMAN_GATE_ANCHOR_UNAVAILABLE = "HUMAN_GATE_ANCHOR_UNAVAILABLE"
    PLAN_VALIDATION_FAILED = "PLAN_VALIDATION_FAILED"


class PlanCompilationError(ValueError):
    code: PlanCompilationCode

    def __init__(self, code: PlanCompilationCode, message: str) -> None:
        if not isinstance(code, PlanCompilationCode):
            raise TypeError("code must be a PlanCompilationCode")
        require_non_empty(message, "message")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PlanStepBinding:
    stage_index: int
    responsibility: WorkflowResponsibility
    step_id: str
    objective: str
    capability_id: CapabilityId | None
    permission_scope_ref: ContractRef | None
    input_refs: tuple[ContractRef, ...] = ()
    budget: BudgetSpec | None = None
    success_criteria: Mapping[str, object] = field(default_factory=dict)
    failure_policy: FailurePolicy = FailurePolicy.STOP
    output_contract: Mapping[str, object] = field(default_factory=dict)
    branch_index: int | None = None

    def __post_init__(self) -> None:
        if type(self.stage_index) is not int:
            raise TypeError("stage_index must be an integer")
        if self.stage_index < 0:
            raise ValueError("stage_index must be >= 0")
        if not isinstance(self.responsibility, WorkflowResponsibility):
            raise TypeError("responsibility must be a WorkflowResponsibility")
        require_non_empty(self.step_id, "step_id")
        require_non_empty(self.objective, "objective")
        if self.capability_id is not None and not isinstance(
            self.capability_id, CapabilityId
        ):
            raise TypeError("capability_id must be a CapabilityId or None")
        if self.permission_scope_ref is not None:
            require_contract_ref(self.permission_scope_ref, "permission_scope_ref")
        if not isinstance(self.input_refs, tuple):
            raise TypeError("input_refs must be a tuple")
        for input_ref in self.input_refs:
            require_contract_ref(input_ref, "input_ref")
        if self.budget is not None and not isinstance(self.budget, BudgetSpec):
            raise TypeError("budget must be a BudgetSpec or None")
        if not isinstance(self.failure_policy, FailurePolicy):
            raise TypeError("failure_policy must be a FailurePolicy")
        if self.branch_index is not None:
            if type(self.branch_index) is not int:
                raise TypeError("branch_index must be an integer or None")
            if self.branch_index < 0:
                raise ValueError("branch_index must be >= 0")
        success_criteria = _freeze_mapping(self.success_criteria, "success_criteria")
        output_contract = _freeze_mapping(self.output_contract, "output_contract")
        if not output_contract:
            raise ValueError("output_contract must not be empty")
        object.__setattr__(self, "success_criteria", success_criteria)
        object.__setattr__(self, "output_contract", output_contract)


@dataclass(frozen=True, slots=True)
class HumanGateBinding:
    step_id: str
    objective: str
    anchor: HumanGateAnchor
    success_criteria: Mapping[str, object]
    failure_policy: FailurePolicy
    output_contract: Mapping[str, object]

    def __post_init__(self) -> None:
        require_non_empty(self.step_id, "step_id")
        require_non_empty(self.objective, "objective")
        if not isinstance(self.anchor, HumanGateAnchor):
            raise TypeError("anchor must be a HumanGateAnchor")
        if not isinstance(self.failure_policy, FailurePolicy):
            raise TypeError("failure_policy must be a FailurePolicy")
        success_criteria = _freeze_mapping(self.success_criteria, "success_criteria")
        output_contract = _freeze_mapping(self.output_contract, "output_contract")
        if not output_contract:
            raise ValueError("output_contract must not be empty")
        object.__setattr__(self, "success_criteria", success_criteria)
        object.__setattr__(self, "output_contract", output_contract)


@dataclass(frozen=True, slots=True)
class PlanCompilationRequest:
    selection: WorkflowSelectionDecision
    plan_id: str
    run_id: str
    plan_version: int
    objective: str
    success_criteria: Mapping[str, object]
    stop_conditions: Mapping[str, object]
    bindings: tuple[PlanStepBinding, ...]
    human_gate: HumanGateBinding | None = None
    gate_refs: tuple[ContractRef, ...] = ()
    budget_envelope: BudgetSpec | None = None
    risk_profile: Mapping[str, object] = field(default_factory=dict)
    assumptions: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.selection, WorkflowSelectionDecision):
            raise TypeError("selection must be a WorkflowSelectionDecision")
        require_non_empty(self.plan_id, "plan_id")
        require_non_empty(self.run_id, "run_id")
        if type(self.plan_version) is not int:
            raise TypeError("plan_version must be an integer")
        if self.plan_version < 1:
            raise ValueError("plan_version must be >= 1")
        require_non_empty(self.objective, "objective")
        if not isinstance(self.bindings, tuple):
            raise TypeError("bindings must be a tuple")
        if any(not isinstance(item, PlanStepBinding) for item in self.bindings):
            raise TypeError("bindings must contain PlanStepBinding values")
        if (
            self.selection.status is WorkflowSelectionStatus.SELECTED
            and not self.bindings
        ):
            raise ValueError("bindings must not be empty for a selected workflow")
        stage_count = len(self.selection.stages)
        if any(item.stage_index >= stage_count for item in self.bindings):
            raise ValueError("binding stage_index must reference a selected stage")
        if self.human_gate is not None and not isinstance(
            self.human_gate, HumanGateBinding
        ):
            raise TypeError("human_gate must be a HumanGateBinding or None")
        step_ids = [item.step_id for item in self.bindings]
        if self.human_gate is not None:
            step_ids.append(self.human_gate.step_id)
        if len(set(step_ids)) != len(step_ids):
            raise PlanCompilationError(
                PlanCompilationCode.DUPLICATE_STEP_ID,
                "step identifiers must be globally unique",
            )
        if not isinstance(self.gate_refs, tuple):
            raise TypeError("gate_refs must be a tuple")
        for gate_ref in self.gate_refs:
            require_contract_ref(gate_ref, "gate_ref")
        if self.budget_envelope is not None and not isinstance(
            self.budget_envelope, BudgetSpec
        ):
            raise TypeError("budget_envelope must be a BudgetSpec or None")
        success_criteria = _freeze_mapping(self.success_criteria, "success_criteria")
        stop_conditions = _freeze_mapping(self.stop_conditions, "stop_conditions")
        risk_profile = _freeze_mapping(self.risk_profile, "risk_profile")
        assumptions = _freeze_mapping(self.assumptions, "assumptions")
        if not stop_conditions:
            raise ValueError("stop_conditions must not be empty")
        object.__setattr__(self, "success_criteria", success_criteria)
        object.__setattr__(self, "stop_conditions", stop_conditions)
        object.__setattr__(self, "risk_profile", risk_profile)
        object.__setattr__(self, "assumptions", assumptions)


def _freeze_mapping(value: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return freeze_agent_safe_mapping(value)
