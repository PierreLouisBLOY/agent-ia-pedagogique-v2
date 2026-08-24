from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts import (
    ActorKind,
    AgentId,
    PermissionScope,
)
from backend.agent_runtime.policy.delegation_policy import (
    DelegationScopeEvaluation,
    DelegationScopePolicy,
)
from backend.agent_runtime.policy.permission_evaluator import PermissionScopeEvaluator
from backend.agent_runtime.policy.permission_vocabulary import (
    ScopeCheck,
    ScopeEvaluation,
    ScopeEvaluationCode,
)
from backend.agent_runtime.policy.policy_configuration import (
    PolicyConfigurationError,
    validate_policy_configuration,
)
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_AGENT_REGISTRY,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMatrix,
    AccessMode,
    AgentRegistry,
    CapabilityClass,
    CapabilityDescriptor,
    CapabilityExecutionRoute,
    CapabilityRegistry,
    UnknownCapabilityError,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

_CONDITIONAL_WORKFLOW = "request_or_allow_by_workflow"


class PolicyDisposition(StrEnum):
    DENY = "DENY"
    ALLOW = "ALLOW"
    REQUEST = "REQUEST"
    DELEGATE = "DELEGATE"
    REQUEST_GATE = "REQUEST_GATE"
    CONDITION_REQUIRED = "CONDITION_REQUIRED"


class PolicyDecisionCode(StrEnum):
    ALLOW = "ALLOW"
    MATRIX_DENY = "MATRIX_DENY"
    SCOPE_DENY = "SCOPE_DENY"
    REQUEST_APPLICATION = "REQUEST_APPLICATION"
    DELEGATE_AGENT = "DELEGATE_AGENT"
    GATE_REQUIRED = "GATE_REQUIRED"
    CONDITION_REQUIRED = "CONDITION_REQUIRED"
    CONDITIONAL_ALLOW = "CONDITIONAL_ALLOW"
    CONDITIONAL_REQUEST = "CONDITIONAL_REQUEST"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    INVALID_POLICY_CONFIGURATION = "INVALID_POLICY_CONFIGURATION"


class AuthorityKind(StrEnum):
    AGENT_RUNTIME = "AGENT_RUNTIME"
    AGENT_SPECIALIST = "AGENT_SPECIALIST"
    APPLICATION = "APPLICATION"
    APPLICATION_DOMAIN = "APPLICATION_DOMAIN"
    TECHNICAL_UTILITY = "TECHNICAL_UTILITY"


class ConditionalResolution(StrEnum):
    ALLOW = "ALLOW"
    REQUEST = "REQUEST"


@dataclass(frozen=True, slots=True)
class PolicyFacts:
    matrix_gate_satisfied: bool = False
    conditional_resolution: ConditionalResolution | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.matrix_gate_satisfied, bool):
            raise TypeError("matrix_gate_satisfied must be a bool")
        if self.conditional_resolution is not None and not isinstance(
            self.conditional_resolution, ConditionalResolution
        ):
            raise TypeError("conditional_resolution must be a ConditionalResolution or None")


_DEFAULT_POLICY_FACTS = PolicyFacts()


@dataclass(frozen=True, slots=True)
class CapabilityPolicyDecision:
    disposition: PolicyDisposition
    code: PolicyDecisionCode
    capability_id: CapabilityId
    agent_id: AgentId
    route: CapabilityExecutionRoute
    authority: AuthorityKind
    scope_evaluation: ScopeEvaluation | None
    target_agent: AgentId | None = None
    limited: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, PolicyDisposition):
            raise TypeError("disposition must be a PolicyDisposition")
        if not isinstance(self.code, PolicyDecisionCode):
            raise TypeError("code must be a PolicyDecisionCode")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(self.route, CapabilityExecutionRoute):
            raise TypeError("route must be a CapabilityExecutionRoute")
        if not isinstance(self.authority, AuthorityKind):
            raise TypeError("authority must be an AuthorityKind")
        if self.scope_evaluation is not None and not isinstance(
            self.scope_evaluation, ScopeEvaluation
        ):
            raise TypeError("scope_evaluation must be a ScopeEvaluation or None")
        if self.target_agent is not None and not isinstance(self.target_agent, AgentId):
            raise TypeError("target_agent must be an AgentId or None")
        if not isinstance(self.limited, bool):
            raise TypeError("limited must be a bool")

        allowed_codes = {
            PolicyDisposition.DENY: {
                PolicyDecisionCode.MATRIX_DENY,
                PolicyDecisionCode.SCOPE_DENY,
                PolicyDecisionCode.OWNER_MISMATCH,
                PolicyDecisionCode.INVALID_POLICY_CONFIGURATION,
            },
            PolicyDisposition.ALLOW: {
                PolicyDecisionCode.ALLOW,
                PolicyDecisionCode.CONDITIONAL_ALLOW,
            },
            PolicyDisposition.REQUEST: {
                PolicyDecisionCode.REQUEST_APPLICATION,
                PolicyDecisionCode.CONDITIONAL_REQUEST,
            },
            PolicyDisposition.DELEGATE: {PolicyDecisionCode.DELEGATE_AGENT},
            PolicyDisposition.REQUEST_GATE: {PolicyDecisionCode.GATE_REQUIRED},
            PolicyDisposition.CONDITION_REQUIRED: {PolicyDecisionCode.CONDITION_REQUIRED},
        }
        if self.code not in allowed_codes[self.disposition]:
            raise ValueError("code is inconsistent with disposition")
        if self.disposition is PolicyDisposition.DELEGATE:
            if self.target_agent is None:
                raise ValueError("DELEGATE requires target_agent")
        elif self.target_agent is not None:
            raise ValueError("target_agent is only valid for DELEGATE")
        if self.code is PolicyDecisionCode.MATRIX_DENY:
            if self.scope_evaluation is not None:
                raise ValueError("MATRIX_DENY must not evaluate scope")
        elif (
            self.code is not PolicyDecisionCode.INVALID_POLICY_CONFIGURATION
            and self.scope_evaluation is None
        ):
            raise ValueError("scope_evaluation is required after scope evaluation")


class DelegationAuthorizationCode(StrEnum):
    ALLOW = "ALLOW"
    MATRIX_DENY = "MATRIX_DENY"
    NOT_DELEGATABLE_BY_MATRIX = "NOT_DELEGATABLE_BY_MATRIX"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    SCOPE_DELEGATION_DENY = "SCOPE_DELEGATION_DENY"


@dataclass(frozen=True, slots=True)
class DelegationAuthorizationDecision:
    allowed: bool
    code: DelegationAuthorizationCode
    capability_id: CapabilityId
    target_agent: AgentId
    scope_evaluation: DelegationScopeEvaluation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")
        if not isinstance(self.code, DelegationAuthorizationCode):
            raise TypeError("code must be a DelegationAuthorizationCode")
        if self.allowed is not (self.code is DelegationAuthorizationCode.ALLOW):
            raise ValueError("allowed must be true exactly for ALLOW")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(self.target_agent, AgentId):
            raise TypeError("target_agent must be an AgentId")
        if self.scope_evaluation is not None and not isinstance(
            self.scope_evaluation, DelegationScopeEvaluation
        ):
            raise TypeError("scope_evaluation must be a DelegationScopeEvaluation or None")
        if self.code is DelegationAuthorizationCode.SCOPE_DELEGATION_DENY:
            if self.scope_evaluation is None or self.scope_evaluation.allowed:
                raise ValueError("scope delegation denial must compose its refusal")
        elif self.scope_evaluation is not None:
            raise ValueError("scope_evaluation is only valid for SCOPE_DELEGATION_DENY")


def authority_for(capability: CapabilityDescriptor) -> AuthorityKind:
    if not isinstance(capability, CapabilityDescriptor):
        raise TypeError("capability must be a CapabilityDescriptor")
    capability_class = capability.capability_class
    route = capability.execution_route
    if (
        capability_class is CapabilityClass.ORCHESTRATION
        and route is CapabilityExecutionRoute.RUNTIME
    ):
        return AuthorityKind.AGENT_RUNTIME
    if (
        capability_class
        in {
            CapabilityClass.EVIDENCE,
            CapabilityClass.GENERATE_TRANSFORM,
            CapabilityClass.REVIEW,
        }
        and route is CapabilityExecutionRoute.AGENT
    ):
        return AuthorityKind.AGENT_SPECIALIST
    if capability_class is CapabilityClass.READ and route is CapabilityExecutionRoute.APPLICATION:
        return AuthorityKind.APPLICATION
    if (
        capability_class is CapabilityClass.APPLICATION_ACTION
        and route is CapabilityExecutionRoute.APPLICATION
    ):
        if capability.capability_id.value in {"CAP-A01", "CAP-A02"}:
            return AuthorityKind.APPLICATION_DOMAIN
        if capability.capability_id.value == "CAP-A03":
            return AuthorityKind.APPLICATION
    if (
        capability_class is CapabilityClass.TECHNICAL_UTILITY
        and route is CapabilityExecutionRoute.UTILITY
    ):
        return AuthorityKind.TECHNICAL_UTILITY
    raise PolicyConfigurationError(
        f"authority mapping is inconsistent for {capability.capability_id.value}"
    )


@dataclass(frozen=True, slots=True)
class CapabilityAuthorizationPolicy:
    agent_registry: AgentRegistry = BASELINE_AGENT_REGISTRY
    capability_registry: CapabilityRegistry = BASELINE_CAPABILITY_REGISTRY
    access_matrix: AccessMatrix = BASELINE_AGENT_CAPABILITY_MATRIX
    scope_evaluator: PermissionScopeEvaluator = field(default_factory=PermissionScopeEvaluator)

    def __post_init__(self) -> None:
        if not isinstance(self.agent_registry, AgentRegistry):
            raise TypeError("agent_registry must be an AgentRegistry")
        if not isinstance(self.capability_registry, CapabilityRegistry):
            raise TypeError("capability_registry must be a CapabilityRegistry")
        if not isinstance(self.access_matrix, AccessMatrix):
            raise TypeError("access_matrix must be an AccessMatrix")
        if not isinstance(self.scope_evaluator, PermissionScopeEvaluator):
            raise TypeError("scope_evaluator must be a PermissionScopeEvaluator")
        if self.scope_evaluator.capability_registry is not self.capability_registry:
            raise PolicyConfigurationError(
                "scope evaluator must use the policy capability registry"
            )
        validate_policy_configuration(
            self.agent_registry, self.capability_registry, self.access_matrix
        )

    def evaluate(
        self,
        *,
        agent_id: AgentId,
        scope: PermissionScope,
        check: ScopeCheck,
        facts: PolicyFacts = _DEFAULT_POLICY_FACTS,
    ) -> CapabilityPolicyDecision:
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(scope, PermissionScope):
            raise TypeError("scope must be a PermissionScope")
        if not isinstance(check, ScopeCheck):
            raise TypeError("check must be a ScopeCheck")
        if not isinstance(facts, PolicyFacts):
            raise TypeError("facts must be PolicyFacts")
        if not self.agent_registry.contains(agent_id):
            raise PolicyConfigurationError(f"agent is not configured: {agent_id.value}")
        try:
            capability = self.capability_registry.get(check.capability_id)
        except UnknownCapabilityError as error:
            raise PolicyConfigurationError(
                f"capability is not configured: {check.capability_id.value}"
            ) from error
        authority = authority_for(capability)

        expected_principal = (
            scope.principal.kind is ActorKind.AGENT
            and scope.principal.actor_id == agent_id.value
            and check.principal.kind is ActorKind.AGENT
            and check.principal.actor_id == agent_id.value
        )
        if not expected_principal:
            scope_evaluation = self.scope_evaluator.evaluate(scope, check)
            if scope_evaluation.allowed:
                scope_evaluation = ScopeEvaluation(
                    allowed=False,
                    code=ScopeEvaluationCode.PRINCIPAL_MISMATCH,
                )
            return self._decision(
                PolicyDisposition.DENY,
                PolicyDecisionCode.SCOPE_DENY,
                capability,
                agent_id,
                authority,
                scope_evaluation,
                limited=False,
            )

        rule = self.access_matrix.rule_for(agent_id, capability.capability_id)
        if rule.mode is AccessMode.DENY:
            return self._decision(
                PolicyDisposition.DENY,
                PolicyDecisionCode.MATRIX_DENY,
                capability,
                agent_id,
                authority,
                None,
                limited=rule.limited,
            )

        scope_evaluation = self.scope_evaluator.evaluate(scope, check)
        if not scope_evaluation.allowed:
            return self._decision(
                PolicyDisposition.DENY,
                PolicyDecisionCode.SCOPE_DENY,
                capability,
                agent_id,
                authority,
                scope_evaluation,
                limited=rule.limited,
            )
        if rule.mode is AccessMode.ALLOW:
            return self._allow_decision(
                capability, agent_id, authority, scope_evaluation, rule.limited
            )
        if rule.mode is AccessMode.REQUEST:
            if capability.execution_route is not CapabilityExecutionRoute.APPLICATION:
                return self._invalid_configuration(
                    capability, agent_id, authority, scope_evaluation, rule.limited
                )
            return self._decision(
                PolicyDisposition.REQUEST,
                PolicyDecisionCode.REQUEST_APPLICATION,
                capability,
                agent_id,
                authority,
                scope_evaluation,
                limited=rule.limited,
            )
        if rule.mode is AccessMode.DELEGATE:
            if (
                capability.execution_route is not CapabilityExecutionRoute.AGENT
                or capability.owner_agent is None
                or agent_id is not AgentId.AG_01
            ):
                return self._invalid_configuration(
                    capability, agent_id, authority, scope_evaluation, rule.limited
                )
            return self._decision(
                PolicyDisposition.DELEGATE,
                PolicyDecisionCode.DELEGATE_AGENT,
                capability,
                agent_id,
                authority,
                scope_evaluation,
                target_agent=capability.owner_agent,
                limited=rule.limited,
            )
        if rule.mode is AccessMode.REQUEST_GATE:
            if capability.execution_route is not CapabilityExecutionRoute.APPLICATION:
                return self._invalid_configuration(
                    capability, agent_id, authority, scope_evaluation, rule.limited
                )
            if not facts.matrix_gate_satisfied:
                return self._decision(
                    PolicyDisposition.REQUEST_GATE,
                    PolicyDecisionCode.GATE_REQUIRED,
                    capability,
                    agent_id,
                    authority,
                    scope_evaluation,
                    limited=rule.limited,
                )
            return self._decision(
                PolicyDisposition.REQUEST,
                PolicyDecisionCode.REQUEST_APPLICATION,
                capability,
                agent_id,
                authority,
                scope_evaluation,
                limited=rule.limited,
            )
        if rule.mode is AccessMode.CONDITIONAL:
            return self._conditional_decision(
                capability,
                agent_id,
                authority,
                scope_evaluation,
                facts,
                rule.condition,
                rule.limited,
            )
        return self._invalid_configuration(
            capability, agent_id, authority, scope_evaluation, rule.limited
        )

    def evaluate_delegation(
        self,
        *,
        parent_scope: PermissionScope,
        child_scope: PermissionScope,
        capability_id: CapabilityId,
        target_agent: AgentId,
        evaluated_at: Instant,
        parent_revoked: bool = False,
    ) -> DelegationAuthorizationDecision:
        if not isinstance(parent_scope, PermissionScope):
            raise TypeError("parent_scope must be a PermissionScope")
        if not isinstance(child_scope, PermissionScope):
            raise TypeError("child_scope must be a PermissionScope")
        if not isinstance(capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(target_agent, AgentId):
            raise TypeError("target_agent must be an AgentId")
        if not isinstance(evaluated_at, Instant):
            raise TypeError("evaluated_at must be an Instant")
        if not isinstance(parent_revoked, bool):
            raise TypeError("parent_revoked must be a bool")
        try:
            capability = self.capability_registry.get(capability_id)
        except UnknownCapabilityError as error:
            raise PolicyConfigurationError(
                f"capability is not configured: {capability_id.value}"
            ) from error
        orchestrator_rule = self.access_matrix.rule_for(AgentId.AG_01, capability_id)
        if orchestrator_rule.mode is AccessMode.DENY:
            return self._delegation_decision(
                DelegationAuthorizationCode.MATRIX_DENY,
                capability_id,
                target_agent,
            )
        if (
            orchestrator_rule.mode is not AccessMode.DELEGATE
            or capability.execution_route is not CapabilityExecutionRoute.AGENT
            or capability.owner_agent is None
        ):
            return self._delegation_decision(
                DelegationAuthorizationCode.NOT_DELEGATABLE_BY_MATRIX,
                capability_id,
                target_agent,
            )
        if target_agent is not capability.owner_agent:
            return self._delegation_decision(
                DelegationAuthorizationCode.OWNER_MISMATCH,
                capability_id,
                target_agent,
            )
        target_rule = self.access_matrix.rule_for(target_agent, capability_id)
        if target_rule.mode is AccessMode.DENY:
            return self._delegation_decision(
                DelegationAuthorizationCode.MATRIX_DENY,
                capability_id,
                target_agent,
            )
        if target_rule.mode is not AccessMode.ALLOW:
            return self._delegation_decision(
                DelegationAuthorizationCode.NOT_DELEGATABLE_BY_MATRIX,
                capability_id,
                target_agent,
            )
        scope_evaluation = DelegationScopePolicy(self.capability_registry).evaluate_delegation(
            parent_scope,
            child_scope,
            target_agent,
            evaluated_at,
            parent_revoked=parent_revoked,
        )
        if not scope_evaluation.allowed:
            return self._delegation_decision(
                DelegationAuthorizationCode.SCOPE_DELEGATION_DENY,
                capability_id,
                target_agent,
                scope_evaluation,
            )
        return self._delegation_decision(
            DelegationAuthorizationCode.ALLOW,
            capability_id,
            target_agent,
        )

    def _allow_decision(
        self,
        capability: CapabilityDescriptor,
        agent_id: AgentId,
        authority: AuthorityKind,
        scope_evaluation: ScopeEvaluation,
        limited: bool,
    ) -> CapabilityPolicyDecision:
        route = capability.execution_route
        if route is CapabilityExecutionRoute.AGENT:
            if capability.owner_agent is not agent_id:
                return self._decision(
                    PolicyDisposition.DENY,
                    PolicyDecisionCode.OWNER_MISMATCH,
                    capability,
                    agent_id,
                    authority,
                    scope_evaluation,
                    limited=limited,
                )
        elif route is CapabilityExecutionRoute.RUNTIME:
            if agent_id is not AgentId.AG_01:
                return self._decision(
                    PolicyDisposition.DENY,
                    PolicyDecisionCode.OWNER_MISMATCH,
                    capability,
                    agent_id,
                    authority,
                    scope_evaluation,
                    limited=limited,
                )
        elif route is not CapabilityExecutionRoute.UTILITY:
            return self._invalid_configuration(
                capability, agent_id, authority, scope_evaluation, limited
            )
        return self._decision(
            PolicyDisposition.ALLOW,
            PolicyDecisionCode.ALLOW,
            capability,
            agent_id,
            authority,
            scope_evaluation,
            limited=limited,
        )

    def _conditional_decision(
        self,
        capability: CapabilityDescriptor,
        agent_id: AgentId,
        authority: AuthorityKind,
        scope_evaluation: ScopeEvaluation,
        facts: PolicyFacts,
        condition: str | None,
        limited: bool,
    ) -> CapabilityPolicyDecision:
        if (
            condition != _CONDITIONAL_WORKFLOW
            or capability.execution_route is not CapabilityExecutionRoute.UTILITY
        ):
            return self._invalid_configuration(
                capability, agent_id, authority, scope_evaluation, limited
            )
        if facts.conditional_resolution is None:
            return self._decision(
                PolicyDisposition.CONDITION_REQUIRED,
                PolicyDecisionCode.CONDITION_REQUIRED,
                capability,
                agent_id,
                authority,
                scope_evaluation,
                limited=limited,
            )
        if facts.conditional_resolution is ConditionalResolution.ALLOW:
            return self._decision(
                PolicyDisposition.ALLOW,
                PolicyDecisionCode.CONDITIONAL_ALLOW,
                capability,
                agent_id,
                authority,
                scope_evaluation,
                limited=limited,
            )
        return self._decision(
            PolicyDisposition.REQUEST,
            PolicyDecisionCode.CONDITIONAL_REQUEST,
            capability,
            agent_id,
            authority,
            scope_evaluation,
            limited=limited,
        )

    def _invalid_configuration(
        self,
        capability: CapabilityDescriptor,
        agent_id: AgentId,
        authority: AuthorityKind,
        scope_evaluation: ScopeEvaluation,
        limited: bool,
    ) -> CapabilityPolicyDecision:
        return self._decision(
            PolicyDisposition.DENY,
            PolicyDecisionCode.INVALID_POLICY_CONFIGURATION,
            capability,
            agent_id,
            authority,
            scope_evaluation,
            limited=limited,
        )

    @staticmethod
    def _decision(
        disposition: PolicyDisposition,
        code: PolicyDecisionCode,
        capability: CapabilityDescriptor,
        agent_id: AgentId,
        authority: AuthorityKind,
        scope_evaluation: ScopeEvaluation | None,
        *,
        target_agent: AgentId | None = None,
        limited: bool,
    ) -> CapabilityPolicyDecision:
        return CapabilityPolicyDecision(
            disposition=disposition,
            code=code,
            capability_id=capability.capability_id,
            agent_id=agent_id,
            route=capability.execution_route,
            authority=authority,
            scope_evaluation=scope_evaluation,
            target_agent=target_agent,
            limited=limited,
        )

    @staticmethod
    def _delegation_decision(
        code: DelegationAuthorizationCode,
        capability_id: CapabilityId,
        target_agent: AgentId,
        scope_evaluation: DelegationScopeEvaluation | None = None,
    ) -> DelegationAuthorizationDecision:
        return DelegationAuthorizationDecision(
            allowed=code is DelegationAuthorizationCode.ALLOW,
            code=code,
            capability_id=capability_id,
            target_agent=target_agent,
            scope_evaluation=scope_evaluation,
        )
