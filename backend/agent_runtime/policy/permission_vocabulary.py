from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts import ActorRef, BudgetSpec
from backend.agent_runtime.contracts.common import freeze_agent_safe_mapping
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class PermissionOperation(StrEnum):
    READ = "read"
    CREATE = "create"
    TRANSFORM = "transform"
    REVIEW = "review"
    REQUEST = "request"


class ScopeEvaluationCode(StrEnum):
    ALLOW = "ALLOW"
    INVALID_SCOPE = "INVALID_SCOPE"
    PRINCIPAL_MISMATCH = "PRINCIPAL_MISMATCH"
    REVOKED = "REVOKED"
    NOT_YET_VALID = "NOT_YET_VALID"
    EXPIRED = "EXPIRED"
    EXPLICIT_DENY = "EXPLICIT_DENY"
    CAPABILITY_NOT_GRANTED = "CAPABILITY_NOT_GRANTED"
    OPERATION_NOT_GRANTED = "OPERATION_NOT_GRANTED"
    RESOURCE_OUT_OF_SCOPE = "RESOURCE_OUT_OF_SCOPE"
    CONSTRAINT_OUT_OF_SCOPE = "CONSTRAINT_OUT_OF_SCOPE"
    GATE_REQUIRED = "GATE_REQUIRED"
    BUDGET_OUT_OF_SCOPE = "BUDGET_OUT_OF_SCOPE"


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeCheck:
    principal: ActorRef
    capability_id: CapabilityId
    operation: PermissionOperation
    resource_scope: Mapping[str, object] = field(default_factory=dict)
    constraints: Mapping[str, object] = field(default_factory=dict)
    requested_budget: BudgetSpec | None = None
    satisfied_gate_requirements: tuple[str, ...] = ()
    evaluated_at: Instant
    revoked: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.principal, ActorRef):
            raise TypeError("principal must be an ActorRef")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(self.operation, PermissionOperation):
            raise TypeError("operation must be a PermissionOperation")
        if self.requested_budget is not None and not isinstance(self.requested_budget, BudgetSpec):
            raise TypeError("requested_budget must be a BudgetSpec or None")
        gates = tuple(self.satisfied_gate_requirements)
        for requirement in gates:
            require_non_empty(requirement, "satisfied_gate_requirement")
        if len(set(gates)) != len(gates):
            raise ValueError("satisfied_gate_requirements must be unique")
        if not isinstance(self.evaluated_at, Instant):
            raise TypeError("evaluated_at must be an Instant")
        if not isinstance(self.revoked, bool):
            raise TypeError("revoked must be a bool")
        object.__setattr__(self, "resource_scope", freeze_agent_safe_mapping(self.resource_scope))
        object.__setattr__(self, "constraints", freeze_agent_safe_mapping(self.constraints))
        object.__setattr__(self, "satisfied_gate_requirements", gates)


@dataclass(frozen=True, slots=True)
class ScopeEvaluation:
    allowed: bool
    code: ScopeEvaluationCode
    missing_gate_requirements: tuple[str, ...] = ()
    matched_deny_rule_index: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")
        if not isinstance(self.code, ScopeEvaluationCode):
            raise TypeError("code must be a ScopeEvaluationCode")
        if self.allowed is not (self.code is ScopeEvaluationCode.ALLOW):
            raise ValueError("allowed must be true exactly for ALLOW")
        missing = tuple(self.missing_gate_requirements)
        for requirement in missing:
            require_non_empty(requirement, "missing_gate_requirement")
        if self.code is ScopeEvaluationCode.GATE_REQUIRED:
            if not missing:
                raise ValueError("GATE_REQUIRED must identify missing requirements")
        elif missing:
            raise ValueError("missing gates are only valid for GATE_REQUIRED")
        deny_index = self.matched_deny_rule_index
        if deny_index is not None:
            if type(deny_index) is not int:
                raise TypeError("matched_deny_rule_index must be an integer or None")
            if deny_index < 0:
                raise ValueError("matched_deny_rule_index must be >= 0")
        if self.code is ScopeEvaluationCode.EXPLICIT_DENY:
            if deny_index is None:
                raise ValueError("EXPLICIT_DENY must identify the matched rule")
        elif deny_index is not None:
            raise ValueError("deny index is only valid for EXPLICIT_DENY")
        object.__setattr__(self, "missing_gate_requirements", missing)
