from __future__ import annotations

import ast
import tomllib
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.agent_runtime.contracts import ActorKind, ActorRef, AgentId, PermissionScope
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    CapabilityPolicyDecision,
    DelegationAuthorizationCode,
    DelegationAuthorizationDecision,
    DelegationScopeCode,
    PermissionOperation,
    PermissionScopeEvaluator,
    PolicyDecisionCode,
    PolicyDisposition,
    PolicyFacts,
    ScopeCheck,
    ScopeEvaluationCode,
)
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_AGENT_REGISTRY,
    BASELINE_CAPABILITY_REGISTRY,
    REQUEST_OR_ALLOW_BY_WORKFLOW,
    AccessMode,
    CapabilityClass,
    CapabilityExecutionRoute,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "backend" / "agent_runtime" / "registry"
POLICY = ROOT / "backend" / "agent_runtime" / "policy"
NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
DEFAULT_FACTS = PolicyFacts()
PHASE_12_4_FILES = (
    REGISTRY / "access_matrix.py",
    REGISTRY / "agents.py",
    REGISTRY / "capabilities.py",
    POLICY / "capability_decision.py",
    POLICY / "delegation_policy.py",
    POLICY / "permission_evaluator.py",
    POLICY / "permission_vocabulary.py",
    POLICY / "policy_configuration.py",
    POLICY / "runtime_policy.py",
    POLICY / "scope_narrowing.py",
)


def _capability(code: str) -> CapabilityId:
    return CapabilityId(code)


def _scope(
    agent_id: AgentId,
    code: str,
    operation: PermissionOperation,
    **overrides: object,
) -> PermissionScope:
    capability_id = _capability(code)
    values: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, agent_id.value),
        "capability_ids": (capability_id,),
        "resource_scope": {},
        "operations": (operation.value,),
        "constraints": {},
        "valid_from": BEFORE,
        "expires_at": AFTER,
        "budget": None,
        "delegable": False,
        "gate_requirements": (),
        "deny_rules": (),
    }
    values.update(overrides)
    return PermissionScope(**values)  # type: ignore[arg-type]


def _check(
    agent_id: AgentId,
    code: str,
    operation: PermissionOperation,
    **overrides: object,
) -> ScopeCheck:
    values: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, agent_id.value),
        "capability_id": _capability(code),
        "operation": operation,
        "resource_scope": {},
        "constraints": {},
        "requested_budget": None,
        "satisfied_gate_requirements": (),
        "evaluated_at": NOW,
        "revoked": False,
    }
    values.update(overrides)
    return ScopeCheck(**values)  # type: ignore[arg-type]


def _evaluate(
    agent_id: AgentId,
    code: str,
    operation: PermissionOperation,
    *,
    scope: PermissionScope | None = None,
    facts: PolicyFacts = DEFAULT_FACTS,
):
    return CapabilityAuthorizationPolicy().evaluate(
        agent_id=agent_id,
        scope=scope or _scope(agent_id, code, operation),
        check=_check(agent_id, code, operation),
        facts=facts,
    )


def _delegation(
    code: str,
    target_agent: AgentId,
    *,
    parent_agent: AgentId = AgentId.AG_01,
    parent_capability_ids: tuple[CapabilityId, ...] | None = None,
    child_capability_ids: tuple[CapabilityId, ...] | None = None,
    child_delegable: bool = False,
    parent_revoked: bool = False,
):
    capability_id = _capability(code)
    parent = _scope(
        parent_agent,
        code,
        PermissionOperation.TRANSFORM,
        capability_ids=(capability_id,) if parent_capability_ids is None else parent_capability_ids,
        delegable=True,
    )
    child = _scope(
        target_agent,
        code,
        PermissionOperation.TRANSFORM,
        capability_ids=(capability_id,) if child_capability_ids is None else child_capability_ids,
        delegable=child_delegable,
    )
    return CapabilityAuthorizationPolicy().evaluate_delegation(
        parent_scope=parent,
        child_scope=child,
        capability_id=capability_id,
        target_agent=target_agent,
        evaluated_at=NOW,
        parent_revoked=parent_revoked,
    )


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted((*REGISTRY.glob("*.py"), *POLICY.glob("*.py"))))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_closure_has_exactly_four_agents() -> None:
    assert len(BASELINE_AGENT_REGISTRY.all()) == 4


def test_closure_has_exactly_twenty_four_capabilities() -> None:
    assert len(BASELINE_CAPABILITY_REGISTRY.all()) == 24


def test_closure_has_exactly_ninety_six_matrix_rules() -> None:
    assert len(BASELINE_AGENT_CAPABILITY_MATRIX.all()) == 96


def test_ag01_is_the_only_orchestrator() -> None:
    assert [
        descriptor.agent_id
        for descriptor in BASELINE_AGENT_REGISTRY.all()
        if descriptor.is_orchestrator
    ] == [AgentId.AG_01]


@pytest.mark.parametrize(
    ("capability_class", "owner"),
    (
        (CapabilityClass.EVIDENCE, AgentId.AG_02),
        (CapabilityClass.GENERATE_TRANSFORM, AgentId.AG_03),
        (CapabilityClass.REVIEW, AgentId.AG_04),
    ),
)
def test_specialist_capability_owners_are_separated(
    capability_class: CapabilityClass, owner: AgentId
) -> None:
    descriptors = BASELINE_CAPABILITY_REGISTRY.by_class(capability_class)

    assert descriptors
    assert all(descriptor.owner_agent is owner for descriptor in descriptors)


def test_ag01_delegates_every_specialist_capability_without_direct_allow() -> None:
    specialist_classes = {
        CapabilityClass.EVIDENCE,
        CapabilityClass.GENERATE_TRANSFORM,
        CapabilityClass.REVIEW,
    }

    for descriptor in BASELINE_CAPABILITY_REGISTRY.all():
        if descriptor.capability_class in specialist_classes:
            rule = BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(
                AgentId.AG_01, descriptor.capability_id
            )
            assert rule.mode is AccessMode.DELEGATE
            assert rule.mode is not AccessMode.ALLOW


def test_non_owner_specialists_are_denied_specialist_capabilities() -> None:
    specialists = (AgentId.AG_02, AgentId.AG_03, AgentId.AG_04)

    for descriptor in BASELINE_CAPABILITY_REGISTRY.all():
        if descriptor.execution_route is CapabilityExecutionRoute.AGENT:
            assert descriptor.owner_agent is not None
            for agent_id in specialists:
                if agent_id is not descriptor.owner_agent:
                    assert (
                        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(
                            agent_id, descriptor.capability_id
                        ).mode
                        is AccessMode.DENY
                    )


def test_application_descriptors_have_no_direct_allow_rule() -> None:
    for descriptor in BASELINE_CAPABILITY_REGISTRY.all():
        if descriptor.execution_route is CapabilityExecutionRoute.APPLICATION:
            assert all(
                rule.mode is not AccessMode.ALLOW
                for rule in BASELINE_AGENT_CAPABILITY_MATRIX.rules_for_capability(
                    descriptor.capability_id
                )
            )


@pytest.mark.parametrize("code", ("CAP-A01", "CAP-A03"))
def test_application_actions_are_requests_for_ag01(code: str) -> None:
    rule = BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_01, _capability(code))

    assert rule.mode is AccessMode.REQUEST


def test_promotion_is_request_gate_for_ag01() -> None:
    rule = BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_01, _capability("CAP-A02"))

    assert rule.mode is AccessMode.REQUEST_GATE


def test_specialists_are_denied_every_application_action() -> None:
    for code in ("CAP-A01", "CAP-A02", "CAP-A03"):
        assert all(
            BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(agent_id, _capability(code)).mode
            is AccessMode.DENY
            for agent_id in (AgentId.AG_02, AgentId.AG_03, AgentId.AG_04)
        )


def test_permission_scope_contract_defines_no_evaluator_or_grant_method() -> None:
    assert {"allows", "evaluate", "grant", "merge"}.isdisjoint(vars(PermissionScope))


def test_permission_scope_evaluator_does_not_depend_on_access_matrix() -> None:
    source = (POLICY / "permission_evaluator.py").read_text(encoding="utf-8")

    assert "AccessMatrix" not in source
    assert "AccessMode" not in source


def test_deny_v1_rejects_unknown_grammar_keys() -> None:
    scope = _scope(
        AgentId.AG_03,
        "CAP-G01",
        PermissionOperation.TRANSFORM,
        deny_rules=({"unknown_selector": "value"},),
    )
    evaluation = PermissionScopeEvaluator().evaluate(
        scope, _check(AgentId.AG_03, "CAP-G01", PermissionOperation.TRANSFORM)
    )

    assert evaluation.code is ScopeEvaluationCode.INVALID_SCOPE


def test_revocation_and_expiration_remain_distinct_scope_refusals() -> None:
    evaluator = PermissionScopeEvaluator()
    revoked = evaluator.evaluate(
        _scope(AgentId.AG_03, "CAP-G01", PermissionOperation.TRANSFORM),
        _check(
            AgentId.AG_03,
            "CAP-G01",
            PermissionOperation.TRANSFORM,
            revoked=True,
        ),
    )
    expired = evaluator.evaluate(
        _scope(
            AgentId.AG_03,
            "CAP-G01",
            PermissionOperation.TRANSFORM,
            valid_from=Instant(NOW.value - timedelta(hours=2)),
            expires_at=NOW,
        ),
        _check(AgentId.AG_03, "CAP-G01", PermissionOperation.TRANSFORM),
    )

    assert revoked.code is ScopeEvaluationCode.REVOKED
    assert expired.code is ScopeEvaluationCode.EXPIRED


def test_matrix_deny_cannot_become_positive_with_scope_allow() -> None:
    decision = _evaluate(AgentId.AG_02, "CAP-G01", PermissionOperation.TRANSFORM)

    assert decision.disposition is PolicyDisposition.DENY
    assert decision.code is PolicyDecisionCode.MATRIX_DENY
    assert decision.scope_evaluation is None


def test_scope_deny_blocks_a_positive_matrix_rule() -> None:
    scope = _scope(
        AgentId.AG_03,
        "CAP-G01",
        PermissionOperation.TRANSFORM,
        deny_rules=({"capability_id": "CAP-G01"},),
    )
    decision = _evaluate(
        AgentId.AG_03,
        "CAP-G01",
        PermissionOperation.TRANSFORM,
        scope=scope,
    )

    assert decision.code is PolicyDecisionCode.SCOPE_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is ScopeEvaluationCode.EXPLICIT_DENY


def test_ag03_g01_nominal_decision_is_allow() -> None:
    decision = _evaluate(AgentId.AG_03, "CAP-G01", PermissionOperation.TRANSFORM)

    assert (decision.disposition, decision.code) == (
        PolicyDisposition.ALLOW,
        PolicyDecisionCode.ALLOW,
    )


def test_ag01_g01_decision_delegates_to_ag03() -> None:
    decision = _evaluate(AgentId.AG_01, "CAP-G01", PermissionOperation.TRANSFORM)

    assert decision.disposition is PolicyDisposition.DELEGATE
    assert decision.target_agent is AgentId.AG_03


def test_a02_without_matrix_gate_remains_request_gate() -> None:
    decision = _evaluate(AgentId.AG_01, "CAP-A02", PermissionOperation.REQUEST)

    assert (decision.disposition, decision.code) == (
        PolicyDisposition.REQUEST_GATE,
        PolicyDecisionCode.GATE_REQUIRED,
    )


def test_a02_with_matrix_gate_becomes_request_not_allow() -> None:
    decision = _evaluate(
        AgentId.AG_01,
        "CAP-A02",
        PermissionOperation.REQUEST,
        facts=PolicyFacts(matrix_gate_satisfied=True),
    )

    assert (decision.disposition, decision.code) == (
        PolicyDisposition.REQUEST,
        PolicyDecisionCode.REQUEST_APPLICATION,
    )


def test_t02_without_trusted_resolution_requires_condition() -> None:
    decision = _evaluate(AgentId.AG_01, "CAP-T02", PermissionOperation.REQUEST)

    assert (decision.disposition, decision.code) == (
        PolicyDisposition.CONDITION_REQUIRED,
        PolicyDecisionCode.CONDITION_REQUIRED,
    )


def test_permission_decision_has_no_runtime_mode_or_autonomy_input() -> None:
    source = (POLICY / "capability_decision.py").read_text(encoding="utf-8")

    assert "RuntimeMode" not in source
    assert "AutonomyLevel" not in source


def test_g01_delegation_to_ag03_is_allowed() -> None:
    decision = _delegation("CAP-G01", AgentId.AG_03)

    assert decision.allowed
    assert decision.code is DelegationAuthorizationCode.ALLOW


def test_g01_delegation_to_ag02_is_owner_mismatch() -> None:
    decision = _delegation("CAP-G01", AgentId.AG_02)

    assert not decision.allowed
    assert decision.code is DelegationAuthorizationCode.OWNER_MISMATCH


def test_delegated_capability_must_belong_to_parent_and_child_grants() -> None:
    e01 = _capability("CAP-E01")
    decision = _delegation(
        "CAP-G01",
        AgentId.AG_03,
        parent_capability_ids=(e01,),
        child_capability_ids=(e01,),
    )

    assert decision.code is DelegationAuthorizationCode.CAPABILITY_NOT_IN_SCOPE


def test_parent_revocation_is_composed_by_final_delegation_policy() -> None:
    decision = _delegation("CAP-G01", AgentId.AG_03, parent_revoked=True)

    assert decision.code is DelegationAuthorizationCode.SCOPE_DELEGATION_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is DelegationScopeCode.PARENT_REVOKED


def test_wider_child_scope_is_composed_by_final_delegation_policy() -> None:
    decision = _delegation(
        "CAP-G01",
        AgentId.AG_03,
        child_capability_ids=(_capability("CAP-G01"), _capability("CAP-E01")),
    )

    assert decision.code is DelegationAuthorizationCode.SCOPE_DELEGATION_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is DelegationScopeCode.NOT_NARROWER


def test_specialist_cannot_redelegate() -> None:
    decision = _delegation("CAP-G01", AgentId.AG_03, parent_agent=AgentId.AG_03)

    assert decision.code is DelegationAuthorizationCode.SCOPE_DELEGATION_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is DelegationScopeCode.PARENT_NOT_AG01


@pytest.mark.parametrize("code", ("CAP-A01", "CAP-A02"))
def test_application_actions_are_not_directly_delegatable(code: str) -> None:
    decision = _delegation(code, AgentId.AG_02)

    assert decision.code is DelegationAuthorizationCode.NOT_DELEGATABLE_BY_MATRIX


def test_registry_and_policy_imports_respect_architectural_boundaries() -> None:
    forbidden_prefixes = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
        "backend.providers",
    )
    violations: list[str] = []

    for path in _python_files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            else:
                modules = []
            violations.extend(
                f"{path.name}: {module}"
                for module in modules
                if module.startswith(forbidden_prefixes) or ".provider" in module.casefold()
            )

    assert violations == []


def test_phase_12_4_defines_no_scheduler_or_execution_state() -> None:
    class_names = {
        node.name
        for path in _python_files()
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert class_names.isdisjoint({"Scheduler", "RunState", "StepState"})


def test_phase_12_4_defines_no_deferred_policy_engine_or_mutable_budget_state() -> None:
    class_names = {
        node.name
        for path in PHASE_12_4_FILES
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }

    assert class_names.isdisjoint(
        {"GateEngine", "BudgetState", "ToolCallPolicy", "GrantRegistry", "ToolRegistry"}
    )


def test_decision_types_store_no_concrete_execution_binding() -> None:
    decision_fields = {
        field.name
        for decision_type in (CapabilityPolicyDecision, DelegationAuthorizationDecision)
        for field in fields(decision_type)
    }

    assert decision_fields.isdisjoint({"handler", "tool_id", "use_case_handler"})


def test_decision_api_exposes_no_fallback_or_alternative_agent() -> None:
    source = (POLICY / "capability_decision.py").read_text(encoding="utf-8")

    assert "fallback" not in source.casefold()
    assert "alternative_agent" not in source


def test_conditional_workflow_literal_has_one_python_source_of_truth() -> None:
    occurrences = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files()
        if "request_or_allow_by_workflow" in path.read_text(encoding="utf-8")
    ]
    rule = BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_01, _capability("CAP-T02"))

    assert occurrences == ["backend/agent_runtime/registry/access_matrix.py"]
    assert rule.condition == REQUEST_OR_ALLOW_BY_WORKFLOW


def test_project_runtime_dependencies_remain_empty_at_phase_closure() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["dependencies"] == []
