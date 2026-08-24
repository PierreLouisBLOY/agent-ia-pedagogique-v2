from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    ActorKind,
    ActorRef,
    AgentId,
    PermissionScope,
)
from backend.agent_runtime.policy import (
    AuthorityKind,
    CapabilityAuthorizationPolicy,
    ConditionalResolution,
    DelegationAuthorizationCode,
    DelegationScopeCode,
    PermissionOperation,
    PolicyConfigurationError,
    PolicyDecisionCode,
    PolicyDisposition,
    PolicyFacts,
    ScopeCheck,
    ScopeEvaluationCode,
    authority_for,
    validate_policy_configuration,
)
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_AGENT_REGISTRY,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMatrix,
    AccessMode,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
DEFAULT_FACTS = PolicyFacts()


def _capability(code: str) -> CapabilityId:
    return CapabilityId(code)


def _scope(
    agent_id: AgentId,
    capability_id: CapabilityId,
    operation: PermissionOperation = PermissionOperation.READ,
    **overrides: object,
) -> PermissionScope:
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
    capability_id: CapabilityId,
    operation: PermissionOperation = PermissionOperation.READ,
    **overrides: object,
) -> ScopeCheck:
    values: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, agent_id.value),
        "capability_id": capability_id,
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
    operation: PermissionOperation = PermissionOperation.READ,
    *,
    scope: PermissionScope | None = None,
    check: ScopeCheck | None = None,
    facts: PolicyFacts = DEFAULT_FACTS,
):
    capability_id = _capability(code)
    return CapabilityAuthorizationPolicy().evaluate(
        agent_id=agent_id,
        scope=scope or _scope(agent_id, capability_id, operation),
        check=check or _check(agent_id, capability_id, operation),
        facts=facts,
    )


def test_policy_vocabularies_are_closed_and_exact() -> None:
    assert {item.value for item in PolicyDisposition} == {
        "DENY",
        "ALLOW",
        "REQUEST",
        "DELEGATE",
        "REQUEST_GATE",
        "CONDITION_REQUIRED",
    }
    assert {item.value for item in PolicyDecisionCode} == {
        "ALLOW",
        "MATRIX_DENY",
        "SCOPE_DENY",
        "REQUEST_APPLICATION",
        "DELEGATE_AGENT",
        "GATE_REQUIRED",
        "CONDITION_REQUIRED",
        "CONDITIONAL_ALLOW",
        "CONDITIONAL_REQUEST",
        "OWNER_MISMATCH",
        "INVALID_POLICY_CONFIGURATION",
    }
    assert {item.value for item in DelegationAuthorizationCode} == {
        "ALLOW",
        "MATRIX_DENY",
        "NOT_DELEGATABLE_BY_MATRIX",
        "OWNER_MISMATCH",
        "CAPABILITY_NOT_IN_SCOPE",
        "SCOPE_DELEGATION_DENY",
    }


def test_matrix_deny_precedes_scope_allow_without_evaluating_scope() -> None:
    decision = _evaluate(AgentId.AG_02, "CAP-G01", PermissionOperation.TRANSFORM)

    assert (decision.disposition, decision.code) == (
        PolicyDisposition.DENY,
        PolicyDecisionCode.MATRIX_DENY,
    )
    assert decision.scope_evaluation is None


def test_scope_deny_blocks_matrix_allow() -> None:
    capability_id = _capability("CAP-G01")
    scope = _scope(
        AgentId.AG_03,
        capability_id,
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


@pytest.mark.parametrize(
    ("agent_id", "code"),
    (
        (AgentId.AG_03, "CAP-G01"),
        (AgentId.AG_04, "CAP-V01"),
    ),
)
def test_specialist_owner_with_scope_allow_executes_agent_route(
    agent_id: AgentId, code: str
) -> None:
    operation = PermissionOperation.TRANSFORM if code == "CAP-G01" else PermissionOperation.REVIEW
    decision = _evaluate(agent_id, code, operation)

    assert (decision.disposition, decision.code, decision.authority) == (
        PolicyDisposition.ALLOW,
        PolicyDecisionCode.ALLOW,
        AuthorityKind.AGENT_SPECIALIST,
    )


@pytest.mark.parametrize(
    ("code", "target"),
    (
        ("CAP-E01", AgentId.AG_02),
        ("CAP-G01", AgentId.AG_03),
        ("CAP-V01", AgentId.AG_04),
    ),
)
def test_ag01_delegates_specialist_capability_without_direct_allow(
    code: str, target: AgentId
) -> None:
    decision = _evaluate(AgentId.AG_01, code)

    assert (decision.disposition, decision.code, decision.target_agent) == (
        PolicyDisposition.DELEGATE,
        PolicyDecisionCode.DELEGATE_AGENT,
        target,
    )


def test_read_route_is_requested_from_application() -> None:
    decision = _evaluate(AgentId.AG_01, "CAP-R01")

    assert (decision.disposition, decision.code, decision.authority) == (
        PolicyDisposition.REQUEST,
        PolicyDecisionCode.REQUEST_APPLICATION,
        AuthorityKind.APPLICATION,
    )


def test_specialist_read_request_propagates_limited_flag() -> None:
    decision = _evaluate(AgentId.AG_02, "CAP-R01")

    assert decision.disposition is PolicyDisposition.REQUEST
    assert decision.limited


@pytest.mark.parametrize(
    ("code", "authority"),
    (
        ("CAP-A01", AuthorityKind.APPLICATION_DOMAIN),
        ("CAP-A03", AuthorityKind.APPLICATION),
    ),
)
def test_application_actions_are_requests_not_direct_allow(
    code: str, authority: AuthorityKind
) -> None:
    decision = _evaluate(AgentId.AG_01, code, PermissionOperation.REQUEST)

    assert (decision.disposition, decision.code, decision.authority) == (
        PolicyDisposition.REQUEST,
        PolicyDecisionCode.REQUEST_APPLICATION,
        authority,
    )


def test_a02_requires_matrix_gate_even_when_scope_has_no_gate() -> None:
    decision = _evaluate(AgentId.AG_01, "CAP-A02", PermissionOperation.REQUEST)

    assert decision.disposition is PolicyDisposition.REQUEST_GATE
    assert decision.code is PolicyDecisionCode.GATE_REQUIRED
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.allowed


def test_a02_satisfied_matrix_gate_only_allows_application_request() -> None:
    decision = _evaluate(
        AgentId.AG_01,
        "CAP-A02",
        PermissionOperation.REQUEST,
        facts=PolicyFacts(matrix_gate_satisfied=True),
    )

    assert (decision.disposition, decision.code, decision.authority) == (
        PolicyDisposition.REQUEST,
        PolicyDecisionCode.REQUEST_APPLICATION,
        AuthorityKind.APPLICATION_DOMAIN,
    )


def test_orchestration_is_runtime_allow_only_for_ag01() -> None:
    allowed = _evaluate(AgentId.AG_01, "CAP-O01", PermissionOperation.REQUEST)
    denied = _evaluate(AgentId.AG_02, "CAP-O01", PermissionOperation.REQUEST)

    assert (allowed.disposition, allowed.authority) == (
        PolicyDisposition.ALLOW,
        AuthorityKind.AGENT_RUNTIME,
    )
    assert denied.code is PolicyDecisionCode.MATRIX_DENY


def test_t01_specialist_is_limited_utility_allow() -> None:
    decision = _evaluate(AgentId.AG_02, "CAP-T01")

    assert (decision.disposition, decision.authority, decision.limited) == (
        PolicyDisposition.ALLOW,
        AuthorityKind.TECHNICAL_UTILITY,
        True,
    )


@pytest.mark.parametrize("agent_id", tuple(AgentId))
def test_t04_is_allowed_for_every_agent(agent_id: AgentId) -> None:
    assert _evaluate(agent_id, "CAP-T04").disposition is PolicyDisposition.ALLOW


def test_conditional_utility_requires_trusted_resolution() -> None:
    decision = _evaluate(AgentId.AG_01, "CAP-T02")

    assert (decision.disposition, decision.code) == (
        PolicyDisposition.CONDITION_REQUIRED,
        PolicyDecisionCode.CONDITION_REQUIRED,
    )


@pytest.mark.parametrize(
    ("resolution", "disposition", "code"),
    (
        (
            ConditionalResolution.ALLOW,
            PolicyDisposition.ALLOW,
            PolicyDecisionCode.CONDITIONAL_ALLOW,
        ),
        (
            ConditionalResolution.REQUEST,
            PolicyDisposition.REQUEST,
            PolicyDecisionCode.CONDITIONAL_REQUEST,
        ),
    ),
)
def test_conditional_utility_resolves_from_trusted_fact(
    resolution: ConditionalResolution,
    disposition: PolicyDisposition,
    code: PolicyDecisionCode,
) -> None:
    decision = _evaluate(
        AgentId.AG_01,
        "CAP-T02",
        facts=PolicyFacts(conditional_resolution=resolution),
    )

    assert (decision.disposition, decision.code) == (disposition, code)


def test_ag03_t02_is_direct_limited_utility_allow() -> None:
    decision = _evaluate(AgentId.AG_03, "CAP-T02")

    assert decision.disposition is PolicyDisposition.ALLOW
    assert decision.limited


def test_ag02_t02_is_matrix_deny() -> None:
    assert _evaluate(AgentId.AG_02, "CAP-T02").code is PolicyDecisionCode.MATRIX_DENY


def test_agent_principal_mismatch_fails_closed() -> None:
    capability_id = _capability("CAP-G01")
    decision = _evaluate(
        AgentId.AG_03,
        "CAP-G01",
        PermissionOperation.TRANSFORM,
        scope=_scope(AgentId.AG_02, capability_id, PermissionOperation.TRANSFORM),
        check=_check(AgentId.AG_02, capability_id, PermissionOperation.TRANSFORM),
    )

    assert decision.code is PolicyDecisionCode.SCOPE_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is ScopeEvaluationCode.PRINCIPAL_MISMATCH


@pytest.mark.parametrize(
    ("scope_overrides", "check_overrides", "expected"),
    (
        ({}, {"revoked": True}, ScopeEvaluationCode.REVOKED),
        ({"expires_at": NOW}, {}, ScopeEvaluationCode.EXPIRED),
        (
            {"deny_rules": ({"capability_id": "CAP-G01"},)},
            {},
            ScopeEvaluationCode.EXPLICIT_DENY,
        ),
    ),
)
def test_scope_refusals_are_composed_without_bypass(
    scope_overrides: dict[str, object],
    check_overrides: dict[str, object],
    expected: ScopeEvaluationCode,
) -> None:
    capability_id = _capability("CAP-G01")
    scope = _scope(
        AgentId.AG_03,
        capability_id,
        PermissionOperation.TRANSFORM,
        **scope_overrides,
    )
    check = _check(
        AgentId.AG_03,
        capability_id,
        PermissionOperation.TRANSFORM,
        **check_overrides,
    )
    decision = _evaluate(
        AgentId.AG_03,
        "CAP-G01",
        PermissionOperation.TRANSFORM,
        scope=scope,
        check=check,
    )

    assert decision.code is PolicyDecisionCode.SCOPE_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is expected


def test_baseline_policy_configuration_is_valid() -> None:
    assert (
        validate_policy_configuration(
            BASELINE_AGENT_REGISTRY,
            BASELINE_CAPABILITY_REGISTRY,
            BASELINE_AGENT_CAPABILITY_MATRIX,
        )
        is None
    )


def test_corrupted_custom_matrix_is_rejected_at_policy_construction() -> None:
    capability_id = _capability("CAP-G01")
    rules = tuple(
        replace(rule, mode=AccessMode.DENY)
        if rule.agent_id is AgentId.AG_03 and rule.capability_id == capability_id
        else rule
        for rule in BASELINE_AGENT_CAPABILITY_MATRIX.all()
    )
    corrupted = AccessMatrix(
        rules,
        agent_ids=tuple(AgentId),
        capability_ids=tuple(
            descriptor.capability_id for descriptor in BASELINE_CAPABILITY_REGISTRY.all()
        ),
    )

    with pytest.raises(PolicyConfigurationError, match="AG-03/CAP-G01"):
        CapabilityAuthorizationPolicy(access_matrix=corrupted)


def test_authority_mapping_is_exact() -> None:
    expected = {
        "CAP-O01": AuthorityKind.AGENT_RUNTIME,
        "CAP-E01": AuthorityKind.AGENT_SPECIALIST,
        "CAP-G01": AuthorityKind.AGENT_SPECIALIST,
        "CAP-V01": AuthorityKind.AGENT_SPECIALIST,
        "CAP-R01": AuthorityKind.APPLICATION,
        "CAP-A01": AuthorityKind.APPLICATION_DOMAIN,
        "CAP-A02": AuthorityKind.APPLICATION_DOMAIN,
        "CAP-A03": AuthorityKind.APPLICATION,
        "CAP-T01": AuthorityKind.TECHNICAL_UTILITY,
    }

    assert {
        code: authority_for(BASELINE_CAPABILITY_REGISTRY.get(_capability(code)))
        for code in expected
    } == expected


def _delegation_scopes(
    capability_id: CapabilityId,
    target_agent: AgentId,
    *,
    parent_agent: AgentId = AgentId.AG_01,
    parent_capability_ids: tuple[CapabilityId, ...] | None = None,
    child_capability_ids: tuple[CapabilityId, ...] | None = None,
) -> tuple[PermissionScope, PermissionScope]:
    parent = _scope(
        parent_agent,
        capability_id,
        PermissionOperation.TRANSFORM,
        capability_ids=(capability_id,) if parent_capability_ids is None else parent_capability_ids,
        delegable=True,
    )
    child = _scope(
        target_agent,
        capability_id,
        PermissionOperation.TRANSFORM,
        capability_ids=(capability_id,) if child_capability_ids is None else child_capability_ids,
        valid_from=NOW,
        delegable=False,
    )
    return parent, child


def _evaluate_delegation(
    code: str,
    target_agent: AgentId,
    *,
    parent_agent: AgentId = AgentId.AG_01,
    parent_capability_ids: tuple[CapabilityId, ...] | None = None,
    child_capability_ids: tuple[CapabilityId, ...] | None = None,
    parent_revoked: bool = False,
):
    capability_id = _capability(code)
    parent, child = _delegation_scopes(
        capability_id,
        target_agent,
        parent_agent=parent_agent,
        parent_capability_ids=parent_capability_ids,
        child_capability_ids=child_capability_ids,
    )
    return CapabilityAuthorizationPolicy().evaluate_delegation(
        parent_scope=parent,
        child_scope=child,
        capability_id=capability_id,
        target_agent=target_agent,
        evaluated_at=NOW,
        parent_revoked=parent_revoked,
    )


@pytest.mark.parametrize(
    ("code", "target"),
    (("CAP-G01", AgentId.AG_03), ("CAP-E01", AgentId.AG_02)),
)
def test_owner_aware_delegation_allows_canonical_target(code: str, target: AgentId) -> None:
    decision = _evaluate_delegation(code, target)

    assert decision.allowed
    assert decision.code is DelegationAuthorizationCode.ALLOW


def test_g01_delegation_to_ag02_is_owner_mismatch() -> None:
    decision = _evaluate_delegation("CAP-G01", AgentId.AG_02)

    assert decision.code is DelegationAuthorizationCode.OWNER_MISMATCH
    assert not decision.allowed


def test_delegated_capability_must_be_in_both_scoped_grants() -> None:
    e01 = _capability("CAP-E01")
    decision = _evaluate_delegation(
        "CAP-G01",
        AgentId.AG_03,
        parent_capability_ids=(e01,),
        child_capability_ids=(e01,),
    )

    assert decision.code is DelegationAuthorizationCode.CAPABILITY_NOT_IN_SCOPE
    assert not decision.allowed
    assert decision.scope_evaluation is None


def test_delegated_capability_absent_from_empty_narrow_scopes_is_denied() -> None:
    decision = _evaluate_delegation(
        "CAP-G01",
        AgentId.AG_03,
        parent_capability_ids=(),
        child_capability_ids=(),
    )

    assert decision.code is DelegationAuthorizationCode.CAPABILITY_NOT_IN_SCOPE
    assert not decision.allowed


def test_empty_child_capability_grant_is_preserved_and_denied() -> None:
    decision = _evaluate_delegation(
        "CAP-G01",
        AgentId.AG_03,
        child_capability_ids=(),
    )

    assert decision.code is DelegationAuthorizationCode.CAPABILITY_NOT_IN_SCOPE
    assert not decision.allowed


def test_child_grant_for_another_parent_capability_does_not_bind_g01() -> None:
    e01 = _capability("CAP-E01")
    decision = _evaluate_delegation(
        "CAP-G01",
        AgentId.AG_03,
        parent_capability_ids=(_capability("CAP-G01"), e01),
        child_capability_ids=(e01,),
    )

    assert decision.code is DelegationAuthorizationCode.CAPABILITY_NOT_IN_SCOPE
    assert not decision.allowed


def test_parent_revocation_is_composed_in_final_delegation_denial() -> None:
    decision = _evaluate_delegation("CAP-G01", AgentId.AG_03, parent_revoked=True)

    assert decision.code is DelegationAuthorizationCode.SCOPE_DELEGATION_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is DelegationScopeCode.PARENT_REVOKED


def test_wider_child_scope_is_composed_in_final_delegation_denial() -> None:
    decision = _evaluate_delegation(
        "CAP-G01",
        AgentId.AG_03,
        child_capability_ids=(_capability("CAP-G01"), _capability("CAP-E01")),
    )

    assert decision.code is DelegationAuthorizationCode.SCOPE_DELEGATION_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is DelegationScopeCode.NOT_NARROWER


@pytest.mark.parametrize("code", ("CAP-A01", "CAP-A02"))
def test_r3_r4_application_actions_are_not_delegatable_by_matrix(code: str) -> None:
    decision = _evaluate_delegation(
        code,
        AgentId.AG_02,
        parent_capability_ids=(),
        child_capability_ids=(),
    )

    assert decision.code is DelegationAuthorizationCode.NOT_DELEGATABLE_BY_MATRIX


def test_specialist_cannot_redelegate() -> None:
    decision = _evaluate_delegation("CAP-G01", AgentId.AG_03, parent_agent=AgentId.AG_03)

    assert decision.code is DelegationAuthorizationCode.SCOPE_DELEGATION_DENY
    assert decision.scope_evaluation is not None
    assert decision.scope_evaluation.code is DelegationScopeCode.PARENT_NOT_AG01
