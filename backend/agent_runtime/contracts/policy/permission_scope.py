from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import ActorRef, freeze_agent_safe_mapping
from backend.agent_runtime.contracts.policy.budget import BudgetSpec
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class PermissionScope:
    """Immutable permission data contract without evaluator semantics."""

    principal: ActorRef
    capability_ids: tuple[CapabilityId, ...] = ()
    resource_scope: Mapping[str, object] = field(default_factory=dict)
    operations: tuple[str, ...] = ()
    constraints: Mapping[str, object] = field(default_factory=dict)
    valid_from: Instant | None = None
    expires_at: Instant | None = None
    budget: BudgetSpec | None = None
    delegable: bool = False
    gate_requirements: tuple[str, ...] = ()
    deny_rules: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.principal, ActorRef):
            raise TypeError("principal must be an ActorRef")
        capability_ids = tuple(self.capability_ids)
        if any(not isinstance(item, CapabilityId) for item in capability_ids):
            raise TypeError("capability_ids must contain CapabilityId values")
        operations = tuple(self.operations)
        for operation in operations:
            require_non_empty(operation, "operation")
        if self.valid_from is not None and not isinstance(self.valid_from, Instant):
            raise TypeError("valid_from must be an Instant")
        if self.expires_at is not None and not isinstance(self.expires_at, Instant):
            raise TypeError("expires_at must be an Instant")
        if (
            self.valid_from is not None
            and self.expires_at is not None
            and self.expires_at.value <= self.valid_from.value
        ):
            raise ValueError("expires_at must be greater than valid_from")
        if self.budget is not None and not isinstance(self.budget, BudgetSpec):
            raise TypeError("budget must be a BudgetSpec")
        if not isinstance(self.delegable, bool):
            raise TypeError("delegable must be a bool")
        gate_requirements = tuple(self.gate_requirements)
        for requirement in gate_requirements:
            require_non_empty(requirement, "gate_requirement")
        deny_rules = tuple(freeze_agent_safe_mapping(rule) for rule in self.deny_rules)
        object.__setattr__(self, "capability_ids", capability_ids)
        object.__setattr__(self, "resource_scope", freeze_agent_safe_mapping(self.resource_scope))
        object.__setattr__(self, "operations", operations)
        object.__setattr__(self, "constraints", freeze_agent_safe_mapping(self.constraints))
        object.__setattr__(self, "gate_requirements", gate_requirements)
        object.__setattr__(self, "deny_rules", deny_rules)
