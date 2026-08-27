from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite

from backend.agent_runtime.contracts import ActorKind, AgentId, ToolCallRequest
from backend.agent_runtime.policy.capability_decision import (
    CapabilityAuthorizationPolicy,
    CapabilityPolicyDecision,
    PolicyDecisionCode,
    PolicyDisposition,
    PolicyFacts,
)
from backend.agent_runtime.policy.permission_vocabulary import (
    PermissionOperation,
    ScopeCheck,
)
from backend.agent_runtime.registry.capabilities import (
    CapabilityClass,
    CapabilityExecutionRoute,
    UnknownCapabilityError,
)
from backend.agent_runtime.registry.tools import (
    BASELINE_TOOL_REGISTRY,
    ToolDescriptor,
    ToolEffectClass,
    ToolRegistry,
    UnknownToolError,
)
from backend.agent_runtime.security.structural_keys import contains_structural_keys
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class ToolCallDisposition(StrEnum):
    DENY = "DENY"
    ALLOW = "ALLOW"


class ToolCallDecisionCode(StrEnum):
    ALLOW = "ALLOW"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    NON_UTILITY_CAPABILITY = "NON_UTILITY_CAPABILITY"
    CAPABILITY_TOOL_MISMATCH = "CAPABILITY_TOOL_MISMATCH"
    CAPABILITY_NOT_ALLOWED = "CAPABILITY_NOT_ALLOWED"
    PERMISSION_SCOPE_MISMATCH = "PERMISSION_SCOPE_MISMATCH"
    IDEMPOTENCY_REQUIRED = "IDEMPOTENCY_REQUIRED"
    TIMEOUT_EXCEEDS_CEILING = "TIMEOUT_EXCEEDS_CEILING"
    SANDBOX_REQUIRED = "SANDBOX_REQUIRED"
    SANDBOX_PROFILE_MISMATCH = "SANDBOX_PROFILE_MISMATCH"
    EXTERNAL_MUTATION_FORBIDDEN = "EXTERNAL_MUTATION_FORBIDDEN"
    INVALID_REQUEST = "INVALID_REQUEST"


@dataclass(frozen=True, slots=True)
class ToolCallDecision:
    """Data-only authorization decision; it never resolves or invokes a handler."""

    disposition: ToolCallDisposition
    code: ToolCallDecisionCode
    tool_id: str
    capability_id: CapabilityId
    capability_decision: CapabilityPolicyDecision | None
    effect_class: ToolEffectClass | None
    sandbox_profile_id: str | None
    idempotency_required: bool
    effective_timeout: int | float | None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, ToolCallDisposition):
            raise TypeError("disposition must be a ToolCallDisposition")
        if not isinstance(self.code, ToolCallDecisionCode):
            raise TypeError("code must be a ToolCallDecisionCode")
        require_non_empty(self.tool_id, "tool_id")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if self.capability_decision is not None and not isinstance(
            self.capability_decision, CapabilityPolicyDecision
        ):
            raise TypeError(
                "capability_decision must be a CapabilityPolicyDecision or None"
            )
        if self.effect_class is not None and not isinstance(
            self.effect_class, ToolEffectClass
        ):
            raise TypeError("effect_class must be a ToolEffectClass or None")
        if self.sandbox_profile_id is not None:
            require_non_empty(self.sandbox_profile_id, "sandbox_profile_id")
        if not isinstance(self.idempotency_required, bool):
            raise TypeError("idempotency_required must be a bool")
        if self.effective_timeout is not None:
            if not isinstance(self.effective_timeout, (int, float)) or isinstance(
                self.effective_timeout, bool
            ):
                raise TypeError("effective_timeout must be a number or None")
            if self.effective_timeout < 0:
                raise ValueError("effective_timeout must be >= 0")
            if isinstance(self.effective_timeout, float) and not isfinite(
                self.effective_timeout
            ):
                raise ValueError("effective_timeout must be finite")

        is_allow = self.disposition is ToolCallDisposition.ALLOW
        if is_allow is not (self.code is ToolCallDecisionCode.ALLOW):
            raise ValueError("ALLOW disposition and code must be equivalent")
        if is_allow:
            if self.capability_decision is None:
                raise ValueError("ALLOW requires a capability_decision")
            if self.capability_decision.disposition is not PolicyDisposition.ALLOW:
                raise ValueError("tool ALLOW requires capability ALLOW")
            if self.effect_class is None:
                raise ValueError("ALLOW requires an effect_class")


_DEFAULT_POLICY_FACTS = PolicyFacts()

TOOL_ARGUMENT_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "approval",
        "auth_token",
        "callable",
        "capability",
        "capability_id",
        "capability_override",
        "circuit_binding",
        "class_path",
        "credential",
        "credentials",
        "gate_approval",
        "gate_approved",
        "gate_decision",
        "gate",
        "handler",
        "handler_id",
        "handler_path",
        "import",
        "import_path",
        "module",
        "module_path",
        "password",
        "permission",
        "permission_scope",
        "permissions",
        "policy_facts",
        "provider",
        "provider_config",
        "provider_credentials",
        "provider_id",
        "provider_name",
        "sandbox_profile",
        "sandbox_profile_id",
        "sandbox_root",
        "binding",
        "effect_state",
        "owner",
        "reconciliation_status",
        "record_id",
        "retry_facts",
        "route",
        "secret",
        "snapshot_ref",
        "snapshot_refs",
        "target",
        "tool",
        "tool_id",
        "tool_override",
    }
)


@dataclass(frozen=True, slots=True)
class ToolCallPolicy:
    """Composes canonical capability authorization with static tool constraints."""

    capability_policy: CapabilityAuthorizationPolicy = field(
        default_factory=CapabilityAuthorizationPolicy
    )
    tool_registry: ToolRegistry = BASELINE_TOOL_REGISTRY

    def __post_init__(self) -> None:
        if not isinstance(self.capability_policy, CapabilityAuthorizationPolicy):
            raise TypeError(
                "capability_policy must be a CapabilityAuthorizationPolicy"
            )
        if not isinstance(self.tool_registry, ToolRegistry):
            raise TypeError("tool_registry must be a ToolRegistry")
        if (
            self.tool_registry.capability_registry
            is not self.capability_policy.capability_registry
        ):
            raise ValueError(
                "tool registry and capability policy must share CapabilityRegistry"
            )

    def evaluate(
        self,
        *,
        agent_id: AgentId,
        request: ToolCallRequest,
        evaluated_at: Instant,
        facts: PolicyFacts = _DEFAULT_POLICY_FACTS,
        declared_sandbox_profile_ids: tuple[str, ...] = (),
        satisfied_gate_requirements: tuple[str, ...] = (),
        scope_revoked: bool = False,
    ) -> ToolCallDecision:
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(request, ToolCallRequest):
            raise TypeError("request must be a ToolCallRequest")
        if not isinstance(evaluated_at, Instant):
            raise TypeError("evaluated_at must be an Instant")
        if not isinstance(facts, PolicyFacts):
            raise TypeError("facts must be PolicyFacts")
        sandbox_profiles = _validate_string_tuple(
            declared_sandbox_profile_ids, "declared_sandbox_profile_ids"
        )
        satisfied_gates = _validate_string_tuple(
            satisfied_gate_requirements, "satisfied_gate_requirements"
        )
        if not isinstance(scope_revoked, bool):
            raise TypeError("scope_revoked must be a bool")

        if not (
            request.meta.actor.kind is ActorKind.AGENT
            and request.meta.actor.actor_id == agent_id.value
        ):
            return self._deny(request, ToolCallDecisionCode.INVALID_REQUEST)

        try:
            capability = self.capability_policy.capability_registry.get(
                request.capability_id
            )
        except UnknownCapabilityError:
            return self._deny(request, ToolCallDecisionCode.UNKNOWN_CAPABILITY)
        if (
            capability.capability_class is not CapabilityClass.TECHNICAL_UTILITY
            or capability.execution_route is not CapabilityExecutionRoute.UTILITY
            or capability.owner_agent is not None
        ):
            return self._deny(request, ToolCallDecisionCode.NON_UTILITY_CAPABILITY)

        try:
            descriptor = self.tool_registry.get(request.tool_id)
        except UnknownToolError:
            return self._deny(request, ToolCallDecisionCode.UNKNOWN_TOOL)
        if descriptor.capability_id != request.capability_id:
            return self._deny(
                request,
                ToolCallDecisionCode.CAPABILITY_TOOL_MISMATCH,
                descriptor=descriptor,
            )
        if contains_structural_keys(
            request.arguments,
            forbidden_keys=TOOL_ARGUMENT_FORBIDDEN_KEYS,
        ):
            return self._deny(
                request,
                ToolCallDecisionCode.INVALID_REQUEST,
                descriptor=descriptor,
            )
        if descriptor.effect_class is ToolEffectClass.EXTERNAL_MUTATION:
            return self._deny(
                request,
                ToolCallDecisionCode.EXTERNAL_MUTATION_FORBIDDEN,
                descriptor=descriptor,
            )

        scope_check = ScopeCheck(
            principal=request.permission_scope.principal,
            capability_id=request.capability_id,
            operation=_permission_operation_for(descriptor.effect_class),
            resource_scope=request.permission_scope.resource_scope,
            constraints=request.permission_scope.constraints,
            requested_budget=request.permission_scope.budget,
            satisfied_gate_requirements=satisfied_gates,
            evaluated_at=evaluated_at,
            revoked=scope_revoked,
        )
        capability_decision = self.capability_policy.evaluate(
            agent_id=agent_id,
            scope=request.permission_scope,
            check=scope_check,
            facts=facts,
        )
        if capability_decision.disposition is not PolicyDisposition.ALLOW:
            code = (
                ToolCallDecisionCode.PERMISSION_SCOPE_MISMATCH
                if capability_decision.code is PolicyDecisionCode.SCOPE_DENY
                else ToolCallDecisionCode.CAPABILITY_NOT_ALLOWED
            )
            return self._deny(
                request,
                code,
                descriptor=descriptor,
                capability_decision=capability_decision,
            )

        if descriptor.idempotency_required and request.idempotency_key is None:
            return self._deny(
                request,
                ToolCallDecisionCode.IDEMPOTENCY_REQUIRED,
                descriptor=descriptor,
                capability_decision=capability_decision,
            )
        if isinstance(request.timeout, float) and not isfinite(request.timeout):
            return self._deny(
                request,
                ToolCallDecisionCode.INVALID_REQUEST,
                descriptor=descriptor,
                capability_decision=capability_decision,
            )
        if (
            descriptor.timeout_ceiling is not None
            and request.timeout is not None
            and request.timeout > descriptor.timeout_ceiling
        ):
            return self._deny(
                request,
                ToolCallDecisionCode.TIMEOUT_EXCEEDS_CEILING,
                descriptor=descriptor,
                capability_decision=capability_decision,
            )
        if descriptor.sandbox_profile_id is not None:
            if not sandbox_profiles:
                return self._deny(
                    request,
                    ToolCallDecisionCode.SANDBOX_REQUIRED,
                    descriptor=descriptor,
                    capability_decision=capability_decision,
                )
            if descriptor.sandbox_profile_id not in sandbox_profiles:
                return self._deny(
                    request,
                    ToolCallDecisionCode.SANDBOX_PROFILE_MISMATCH,
                    descriptor=descriptor,
                    capability_decision=capability_decision,
                )

        effective_timeout = (
            request.timeout
            if request.timeout is not None
            else descriptor.timeout_ceiling
        )
        return ToolCallDecision(
            disposition=ToolCallDisposition.ALLOW,
            code=ToolCallDecisionCode.ALLOW,
            tool_id=request.tool_id,
            capability_id=request.capability_id,
            capability_decision=capability_decision,
            effect_class=descriptor.effect_class,
            sandbox_profile_id=descriptor.sandbox_profile_id,
            idempotency_required=descriptor.idempotency_required,
            effective_timeout=effective_timeout,
        )

    @staticmethod
    def _deny(
        request: ToolCallRequest,
        code: ToolCallDecisionCode,
        *,
        descriptor: ToolDescriptor | None = None,
        capability_decision: CapabilityPolicyDecision | None = None,
    ) -> ToolCallDecision:
        return ToolCallDecision(
            disposition=ToolCallDisposition.DENY,
            code=code,
            tool_id=request.tool_id,
            capability_id=request.capability_id,
            capability_decision=capability_decision,
            effect_class=(descriptor.effect_class if descriptor is not None else None),
            sandbox_profile_id=(
                descriptor.sandbox_profile_id if descriptor is not None else None
            ),
            idempotency_required=(
                descriptor.idempotency_required if descriptor is not None else False
            ),
            effective_timeout=None,
        )


def _permission_operation_for(effect_class: ToolEffectClass) -> PermissionOperation:
    if effect_class is ToolEffectClass.LOCAL_FILE_TRANSFORM:
        return PermissionOperation.TRANSFORM
    if effect_class in {ToolEffectClass.READ_ONLY, ToolEffectClass.PURE_COMPUTE}:
        return PermissionOperation.READ
    return PermissionOperation.REQUEST


def _validate_string_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for value in values:
        require_non_empty(value, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain unique values")
    return values
