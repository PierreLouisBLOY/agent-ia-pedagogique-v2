"""Configurable technical guardrails for the agent runtime."""

from backend.agent_runtime.policy.capability_decision import (
    AuthorityKind,
    CapabilityAuthorizationPolicy,
    CapabilityPolicyDecision,
    ConditionalResolution,
    DelegationAuthorizationCode,
    DelegationAuthorizationDecision,
    PolicyDecisionCode,
    PolicyDisposition,
    PolicyFacts,
    authority_for,
)
from backend.agent_runtime.policy.delegation_policy import (
    DelegationScopeCode,
    DelegationScopeEvaluation,
    DelegationScopePolicy,
)
from backend.agent_runtime.policy.permission_evaluator import (
    PermissionScopeEvaluator,
    scope_configuration_is_valid,
)
from backend.agent_runtime.policy.permission_vocabulary import (
    PermissionOperation,
    ScopeCheck,
    ScopeEvaluation,
    ScopeEvaluationCode,
)
from backend.agent_runtime.policy.policy_configuration import (
    PolicyConfigurationError,
    validate_policy_configuration,
)
from backend.agent_runtime.policy.runtime_policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)
from backend.agent_runtime.policy.scope_narrowing import (
    budget_is_narrower_or_equal,
    constraints_are_narrower_or_equal,
    is_scope_narrower_or_equal,
    resource_scope_contains,
    resource_scopes_intersect,
)
from backend.agent_runtime.policy.tool_call_policy import (
    ToolCallDecision,
    ToolCallDecisionCode,
    ToolCallDisposition,
    ToolCallPolicy,
)

__all__ = [
    "BASELINE_AGENT_RUNTIME_POLICY",
    "AgentRuntimePolicy",
    "AuthorityKind",
    "CapabilityAuthorizationPolicy",
    "CapabilityPolicyDecision",
    "ConditionalResolution",
    "DelegationAuthorizationCode",
    "DelegationAuthorizationDecision",
    "DelegationScopeCode",
    "DelegationScopeEvaluation",
    "DelegationScopePolicy",
    "PermissionOperation",
    "PermissionScopeEvaluator",
    "PolicyConfigurationError",
    "PolicyDecisionCode",
    "PolicyDisposition",
    "PolicyFacts",
    "ScopeCheck",
    "ScopeEvaluation",
    "ScopeEvaluationCode",
    "ToolCallDecision",
    "ToolCallDecisionCode",
    "ToolCallDisposition",
    "ToolCallPolicy",
    "budget_is_narrower_or_equal",
    "authority_for",
    "constraints_are_narrower_or_equal",
    "is_scope_narrower_or_equal",
    "resource_scope_contains",
    "resource_scopes_intersect",
    "scope_configuration_is_valid",
    "validate_policy_configuration",
]
