from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts import PermissionScope
from backend.agent_runtime.policy.permission_vocabulary import (
    PermissionOperation,
    ScopeCheck,
    ScopeEvaluation,
    ScopeEvaluationCode,
)
from backend.agent_runtime.policy.scope_narrowing import (
    budget_is_narrower_or_equal,
    constraints_are_narrower_or_equal,
    resource_scope_contains,
    resource_scopes_intersect,
)
from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityRegistry,
)

_DENY_RULE_KEYS = frozenset({"capability_id", "operation", "resource_scope", "reason_code"})
_OPERATION_VALUES = frozenset(operation.value for operation in PermissionOperation)


@dataclass(frozen=True, slots=True)
class PermissionScopeEvaluator:
    capability_registry: CapabilityRegistry = BASELINE_CAPABILITY_REGISTRY

    def __post_init__(self) -> None:
        if not isinstance(self.capability_registry, CapabilityRegistry):
            raise TypeError("capability_registry must be a CapabilityRegistry")

    def evaluate(self, scope: PermissionScope, check: ScopeCheck) -> ScopeEvaluation:
        if not isinstance(scope, PermissionScope):
            raise TypeError("scope must be a PermissionScope")
        if not isinstance(check, ScopeCheck):
            raise TypeError("check must be a ScopeCheck")
        if not scope_configuration_is_valid(scope, self.capability_registry):
            return _refusal(ScopeEvaluationCode.INVALID_SCOPE)
        if check.principal != scope.principal:
            return _refusal(ScopeEvaluationCode.PRINCIPAL_MISMATCH)
        if check.revoked:
            return _refusal(ScopeEvaluationCode.REVOKED)
        if scope.valid_from is not None and check.evaluated_at.value < scope.valid_from.value:
            return _refusal(ScopeEvaluationCode.NOT_YET_VALID)
        if scope.expires_at is not None and check.evaluated_at.value >= scope.expires_at.value:
            return _refusal(ScopeEvaluationCode.EXPIRED)

        deny_index = _first_matching_deny_rule(scope.deny_rules, check)
        if deny_index is not None:
            return ScopeEvaluation(
                allowed=False,
                code=ScopeEvaluationCode.EXPLICIT_DENY,
                matched_deny_rule_index=deny_index,
            )
        if check.capability_id not in scope.capability_ids:
            return _refusal(ScopeEvaluationCode.CAPABILITY_NOT_GRANTED)
        if check.operation.value not in scope.operations:
            return _refusal(ScopeEvaluationCode.OPERATION_NOT_GRANTED)
        if not resource_scope_contains(scope.resource_scope, check.resource_scope):
            return _refusal(ScopeEvaluationCode.RESOURCE_OUT_OF_SCOPE)
        if not constraints_are_narrower_or_equal(scope.constraints, check.constraints):
            return _refusal(ScopeEvaluationCode.CONSTRAINT_OUT_OF_SCOPE)

        missing_gates = tuple(
            requirement
            for requirement in scope.gate_requirements
            if requirement not in check.satisfied_gate_requirements
        )
        if missing_gates:
            return ScopeEvaluation(
                allowed=False,
                code=ScopeEvaluationCode.GATE_REQUIRED,
                missing_gate_requirements=missing_gates,
            )
        if not budget_is_narrower_or_equal(scope.budget, check.requested_budget):
            return _refusal(ScopeEvaluationCode.BUDGET_OUT_OF_SCOPE)
        return ScopeEvaluation(allowed=True, code=ScopeEvaluationCode.ALLOW)


def scope_configuration_is_valid(
    scope: PermissionScope, capability_registry: CapabilityRegistry
) -> bool:
    if not isinstance(scope, PermissionScope):
        raise TypeError("scope must be a PermissionScope")
    if not isinstance(capability_registry, CapabilityRegistry):
        raise TypeError("capability_registry must be a CapabilityRegistry")
    if len(set(scope.capability_ids)) != len(scope.capability_ids):
        return False
    if any(
        not capability_registry.contains(capability_id) for capability_id in scope.capability_ids
    ):
        return False
    if len(set(scope.operations)) != len(scope.operations):
        return False
    if any(
        type(operation) is not str or operation not in _OPERATION_VALUES
        for operation in scope.operations
    ):
        return False
    if len(set(scope.gate_requirements)) != len(scope.gate_requirements):
        return False
    return all(_deny_rule_is_valid(rule) for rule in scope.deny_rules)


def _refusal(code: ScopeEvaluationCode) -> ScopeEvaluation:
    return ScopeEvaluation(allowed=False, code=code)


def _deny_rule_is_valid(rule: Mapping[str, object]) -> bool:
    if not isinstance(rule, Mapping) or not set(rule).issubset(_DENY_RULE_KEYS):
        return False
    capability_id = rule.get("capability_id")
    if "capability_id" in rule and not _is_non_empty_string(capability_id):
        return False
    operation = rule.get("operation")
    if "operation" in rule and (type(operation) is not str or operation not in _OPERATION_VALUES):
        return False
    resource_scope = rule.get("resource_scope")
    if "resource_scope" in rule and not isinstance(resource_scope, Mapping):
        return False
    reason_code = rule.get("reason_code")
    return "reason_code" not in rule or _is_non_empty_string(reason_code)


def _first_matching_deny_rule(
    rules: tuple[Mapping[str, object], ...], check: ScopeCheck
) -> int | None:
    return next(
        (index for index, rule in enumerate(rules) if _deny_rule_matches(rule, check)),
        None,
    )


def _deny_rule_matches(rule: Mapping[str, object], check: ScopeCheck) -> bool:
    if "capability_id" in rule and rule["capability_id"] != check.capability_id.value:
        return False
    if "operation" in rule and rule["operation"] != check.operation.value:
        return False
    if "resource_scope" in rule:
        resource_selector = rule["resource_scope"]
        if not isinstance(resource_selector, Mapping):
            return False
        if not resource_scopes_intersect(resource_selector, check.resource_scope):
            return False
    return True


def _is_non_empty_string(value: object) -> bool:
    return type(value) is str and bool(value.strip())
