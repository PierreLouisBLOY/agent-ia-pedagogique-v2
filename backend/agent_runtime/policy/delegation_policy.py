from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts import ActorKind, AgentId, PermissionScope
from backend.agent_runtime.policy.permission_evaluator import (
    scope_configuration_is_valid,
)
from backend.agent_runtime.policy.scope_narrowing import is_scope_narrower_or_equal
from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityRegistry,
    CapabilityRisk,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant


class DelegationScopeCode(StrEnum):
    ALLOW = "ALLOW"
    INVALID_PARENT_SCOPE = "INVALID_PARENT_SCOPE"
    INVALID_CHILD_SCOPE = "INVALID_CHILD_SCOPE"
    PARENT_NOT_DELEGABLE = "PARENT_NOT_DELEGABLE"
    PARENT_NOT_AG01 = "PARENT_NOT_AG01"
    INVALID_TARGET_AGENT = "INVALID_TARGET_AGENT"
    CHILD_PRINCIPAL_MISMATCH = "CHILD_PRINCIPAL_MISMATCH"
    PARENT_REVOKED = "PARENT_REVOKED"
    PARENT_INACTIVE = "PARENT_INACTIVE"
    NOT_NARROWER = "NOT_NARROWER"
    RISK_NOT_DELEGABLE = "RISK_NOT_DELEGABLE"
    CHILD_REDELEGATION_FORBIDDEN = "CHILD_REDELEGATION_FORBIDDEN"


@dataclass(frozen=True, slots=True)
class DelegationScopeEvaluation:
    allowed: bool
    code: DelegationScopeCode
    offending_capability_id: CapabilityId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")
        if not isinstance(self.code, DelegationScopeCode):
            raise TypeError("code must be a DelegationScopeCode")
        if self.allowed is not (self.code is DelegationScopeCode.ALLOW):
            raise ValueError("allowed must be true exactly for ALLOW")
        if self.offending_capability_id is not None and not isinstance(
            self.offending_capability_id, CapabilityId
        ):
            raise TypeError("offending_capability_id must be a CapabilityId or None")
        if self.code is DelegationScopeCode.RISK_NOT_DELEGABLE:
            if self.offending_capability_id is None:
                raise ValueError("RISK_NOT_DELEGABLE must identify a capability")
        elif self.offending_capability_id is not None:
            raise ValueError("offending_capability_id is only valid for RISK_NOT_DELEGABLE")


@dataclass(frozen=True, slots=True)
class DelegationScopePolicy:
    capability_registry: CapabilityRegistry = BASELINE_CAPABILITY_REGISTRY

    def __post_init__(self) -> None:
        if not isinstance(self.capability_registry, CapabilityRegistry):
            raise TypeError("capability_registry must be a CapabilityRegistry")

    def evaluate_delegation(
        self,
        parent_scope: PermissionScope,
        child_scope: PermissionScope,
        target_agent: AgentId,
        evaluated_at: Instant,
        *,
        parent_revoked: bool = False,
    ) -> DelegationScopeEvaluation:
        if not isinstance(parent_scope, PermissionScope):
            raise TypeError("parent_scope must be a PermissionScope")
        if not isinstance(child_scope, PermissionScope):
            raise TypeError("child_scope must be a PermissionScope")
        if not isinstance(target_agent, AgentId):
            raise TypeError("target_agent must be an AgentId")
        if not isinstance(evaluated_at, Instant):
            raise TypeError("evaluated_at must be an Instant")
        if not isinstance(parent_revoked, bool):
            raise TypeError("parent_revoked must be a bool")
        if not scope_configuration_is_valid(parent_scope, self.capability_registry):
            return _refusal(DelegationScopeCode.INVALID_PARENT_SCOPE)
        if not scope_configuration_is_valid(child_scope, self.capability_registry):
            return _refusal(DelegationScopeCode.INVALID_CHILD_SCOPE)
        if not (
            parent_scope.principal.kind is ActorKind.AGENT
            and parent_scope.principal.actor_id == AgentId.AG_01.value
        ):
            return _refusal(DelegationScopeCode.PARENT_NOT_AG01)
        if target_agent not in (AgentId.AG_02, AgentId.AG_03, AgentId.AG_04):
            return _refusal(DelegationScopeCode.INVALID_TARGET_AGENT)
        if not (
            child_scope.principal.kind is ActorKind.AGENT
            and child_scope.principal.actor_id == target_agent.value
        ):
            return _refusal(DelegationScopeCode.CHILD_PRINCIPAL_MISMATCH)
        if parent_revoked:
            return _refusal(DelegationScopeCode.PARENT_REVOKED)
        if not parent_scope.delegable:
            return _refusal(DelegationScopeCode.PARENT_NOT_DELEGABLE)
        if (
            parent_scope.valid_from is not None
            and evaluated_at.value < parent_scope.valid_from.value
        ) or (
            parent_scope.expires_at is not None
            and evaluated_at.value >= parent_scope.expires_at.value
        ):
            return _refusal(DelegationScopeCode.PARENT_INACTIVE)
        if child_scope.delegable:
            return _refusal(DelegationScopeCode.CHILD_REDELEGATION_FORBIDDEN)
        if not is_scope_narrower_or_equal(parent_scope, child_scope, allow_principal_change=True):
            return _refusal(DelegationScopeCode.NOT_NARROWER)
        for capability_id in child_scope.capability_ids:
            descriptor = self.capability_registry.get(capability_id)
            if descriptor.risk in (CapabilityRisk.R3, CapabilityRisk.R4):
                return DelegationScopeEvaluation(
                    allowed=False,
                    code=DelegationScopeCode.RISK_NOT_DELEGABLE,
                    offending_capability_id=capability_id,
                )
        return DelegationScopeEvaluation(
            allowed=True,
            code=DelegationScopeCode.ALLOW,
        )


def _refusal(code: DelegationScopeCode) -> DelegationScopeEvaluation:
    return DelegationScopeEvaluation(allowed=False, code=code)
