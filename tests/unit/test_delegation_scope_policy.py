from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    ActorKind,
    ActorRef,
    AgentId,
    BudgetSpec,
    PermissionScope,
)
from backend.agent_runtime.policy import (
    DelegationScopeCode,
    DelegationScopePolicy,
)
from backend.agent_runtime.registry import BASELINE_AGENT_CAPABILITY_MATRIX
from backend.agent_runtime.registry.access_matrix import AccessMode
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 10, 0, tzinfo=UTC))
START = Instant(NOW.value - timedelta(hours=1))
END = Instant(NOW.value + timedelta(hours=1))
E01 = CapabilityId("CAP-E01")


def _parent(**overrides: object) -> PermissionScope:
    values: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, AgentId.AG_01.value),
        "capability_ids": (E01,),
        "resource_scope": {"courses": ("c1", "c2")},
        "operations": ("read",),
        "constraints": {"tenant": "t1"},
        "valid_from": START,
        "expires_at": END,
        "budget": BudgetSpec(max_tokens=100),
        "delegable": True,
        "gate_requirements": ("review",),
        "deny_rules": ({"resource_scope": {"courses": ("c2",)}},),
    }
    values.update(overrides)
    return PermissionScope(**values)  # type: ignore[arg-type]


def _child(
    parent: PermissionScope | None = None,
    target: AgentId = AgentId.AG_02,
    **changes: object,
) -> PermissionScope:
    source = parent or _parent()
    defaults: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, target.value),
        "resource_scope": {"courses": ("c1",)},
        "constraints": {"tenant": "t1", "locale": "fr"},
        "valid_from": NOW,
        "expires_at": END,
        "budget": BudgetSpec(max_tokens=50),
        "delegable": False,
    }
    defaults.update(changes)
    return replace(source, **defaults)  # type: ignore[arg-type]


def _evaluate(
    parent: PermissionScope,
    child: PermissionScope,
    target: AgentId = AgentId.AG_02,
    evaluated_at: Instant = NOW,
):
    return DelegationScopePolicy().evaluate_delegation(parent, child, target, evaluated_at)


def test_ag01_delegable_parent_to_narrowed_ag02_child_is_allowed() -> None:
    evaluation = _evaluate(_parent(), _child())

    assert evaluation.allowed
    assert evaluation.code is DelegationScopeCode.ALLOW


def test_non_delegable_parent_is_refused() -> None:
    parent = _parent(delegable=False)

    assert _evaluate(parent, _child(parent)).code is DelegationScopeCode.PARENT_NOT_DELEGABLE


def test_parent_other_than_ag01_is_refused() -> None:
    parent = _parent(principal=ActorRef(ActorKind.AGENT, AgentId.AG_02.value))
    child = _child(parent, target=AgentId.AG_03)

    assert _evaluate(parent, child, AgentId.AG_03).code is DelegationScopeCode.PARENT_NOT_AG01


def test_target_ag01_is_refused() -> None:
    parent = _parent()
    child = _child(parent, target=AgentId.AG_01)

    assert _evaluate(parent, child, AgentId.AG_01).code is DelegationScopeCode.INVALID_TARGET_AGENT


def test_child_principal_must_match_target_agent() -> None:
    parent = _parent()
    child = _child(parent, target=AgentId.AG_03)

    assert (
        _evaluate(parent, child, AgentId.AG_02).code is DelegationScopeCode.CHILD_PRINCIPAL_MISMATCH
    )


@pytest.mark.parametrize(
    "parent",
    (
        _parent(valid_from=Instant(NOW.value + timedelta(minutes=1))),
        _parent(expires_at=NOW),
    ),
)
def test_inactive_parent_is_refused(parent: PermissionScope) -> None:
    assert _evaluate(parent, _child(parent)).code is DelegationScopeCode.PARENT_INACTIVE


def test_wider_child_is_refused() -> None:
    parent = _parent()
    child = _child(parent, capability_ids=(E01, CapabilityId("CAP-G01")))

    assert _evaluate(parent, child).code is DelegationScopeCode.NOT_NARROWER


def test_child_redelegation_is_forbidden_in_baseline() -> None:
    parent = _parent()
    child = _child(parent, delegable=True)

    assert _evaluate(parent, child).code is DelegationScopeCode.CHILD_REDELEGATION_FORBIDDEN


@pytest.mark.parametrize(
    "capability_id",
    (CapabilityId("CAP-A01"), CapabilityId("CAP-A02")),
)
def test_r3_and_r4_capabilities_are_not_directly_delegable(
    capability_id: CapabilityId,
) -> None:
    parent = _parent(capability_ids=(capability_id,))
    child = _child(parent)
    evaluation = _evaluate(parent, child)

    assert evaluation.code is DelegationScopeCode.RISK_NOT_DELEGABLE
    assert evaluation.offending_capability_id == capability_id


@pytest.mark.parametrize(
    "capability_id",
    (
        CapabilityId("CAP-E01"),
        CapabilityId("CAP-G01"),
        CapabilityId("CAP-T02"),
    ),
)
def test_r0_r1_r2_pass_risk_filter_when_otherwise_valid(
    capability_id: CapabilityId,
) -> None:
    parent = _parent(capability_ids=(capability_id,))
    child = _child(parent)

    assert _evaluate(parent, child).code is DelegationScopeCode.ALLOW


def test_delegation_policy_does_not_apply_owner_or_matrix_decision() -> None:
    capability_id = CapabilityId("CAP-G01")
    parent = _parent(capability_ids=(capability_id,))
    child = _child(parent, target=AgentId.AG_02)

    assert (
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_02, capability_id).mode
        is AccessMode.DENY
    )
    assert _evaluate(parent, child, AgentId.AG_02).code is DelegationScopeCode.ALLOW


def test_invalid_parent_and_child_scopes_fail_closed() -> None:
    invalid_parent = _parent(operations=("delete",))
    valid_parent = _parent()
    invalid_child = _child(valid_parent, capability_ids=(CapabilityId("CAP-X99"),))

    assert (
        _evaluate(invalid_parent, _child(invalid_parent)).code
        is DelegationScopeCode.INVALID_PARENT_SCOPE
    )
    assert _evaluate(valid_parent, invalid_child).code is DelegationScopeCode.INVALID_CHILD_SCOPE
