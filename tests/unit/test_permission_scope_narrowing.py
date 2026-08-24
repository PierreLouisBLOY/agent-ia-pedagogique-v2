from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.agent_runtime.contracts import ActorKind, ActorRef, BudgetSpec, PermissionScope
from backend.agent_runtime.policy import (
    budget_is_narrower_or_equal,
    constraints_are_narrower_or_equal,
    is_scope_narrower_or_equal,
    resource_scope_contains,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

START = Instant(datetime(2026, 8, 24, 8, 0, tzinfo=UTC))
END = Instant(START.value + timedelta(hours=8))
PRINCIPAL = ActorRef(ActorKind.AGENT, "AG-01")
R01 = CapabilityId("CAP-R01")
G01 = CapabilityId("CAP-G01")


def _parent(**overrides: object) -> PermissionScope:
    values: dict[str, object] = {
        "principal": PRINCIPAL,
        "capability_ids": (R01, G01),
        "resource_scope": {"courses": ("c1", "c2"), "tenant": "t1"},
        "operations": ("read", "transform"),
        "constraints": {"formats": ("pdf", "docx"), "tenant": "t1"},
        "valid_from": START,
        "expires_at": END,
        "budget": BudgetSpec(max_tokens=100, max_cost=Decimal("2")),
        "delegable": True,
        "gate_requirements": ("review",),
        "deny_rules": ({"resource_scope": {"courses": ("c2",)}},),
    }
    values.update(overrides)
    return PermissionScope(**values)  # type: ignore[arg-type]


def _child(parent: PermissionScope | None = None, **changes: object) -> PermissionScope:
    source = parent or _parent()
    defaults: dict[str, object] = {
        "capability_ids": (R01,),
        "resource_scope": {"courses": ("c1",)},
        "operations": ("read",),
        "constraints": {"formats": ("pdf",), "tenant": "t1", "locale": "fr"},
        "valid_from": Instant(START.value + timedelta(hours=1)),
        "expires_at": Instant(END.value - timedelta(hours=1)),
        "budget": BudgetSpec(max_tokens=50, max_cost=Decimal("1")),
        "delegable": False,
    }
    defaults.update(changes)
    return replace(source, **defaults)  # type: ignore[arg-type]


def test_child_capability_subset_is_narrower() -> None:
    assert is_scope_narrower_or_equal(_parent(), _child())


def test_added_capability_is_not_narrower() -> None:
    parent = _parent(capability_ids=(R01,))
    child = _child(parent, capability_ids=(R01, G01))

    assert not is_scope_narrower_or_equal(parent, child)


def test_resource_child_subset_is_narrower() -> None:
    assert resource_scope_contains(
        {"courses": ("c1", "c2"), "nested": {"section": "s1"}},
        {"courses": ("c1",), "nested": {}},
    )


def test_new_resource_is_not_narrower() -> None:
    assert not resource_scope_contains({"courses": ("c1",)}, {"courses": ("c2",)})


def test_parent_constraints_preserved_with_extra_constraint_are_narrower() -> None:
    assert constraints_are_narrower_or_equal(
        {"formats": ("pdf", "docx")},
        {"formats": ("pdf",), "locale": "fr"},
    )


def test_removed_parent_constraint_is_not_narrower() -> None:
    assert not constraints_are_narrower_or_equal({"tenant": "t1"}, {"locale": "fr"})


def test_removed_parent_gate_is_not_narrower() -> None:
    assert not is_scope_narrower_or_equal(_parent(), _child(gate_requirements=()))


def test_extra_gate_is_narrower() -> None:
    assert is_scope_narrower_or_equal(_parent(), _child(gate_requirements=("review", "legal")))


def test_removed_parent_deny_is_not_narrower() -> None:
    assert not is_scope_narrower_or_equal(_parent(), _child(deny_rules=()))


def test_extra_deny_is_narrower() -> None:
    parent = _parent()
    child = _child(
        parent,
        deny_rules=(
            *parent.deny_rules,
            {"capability_id": "CAP-G01", "reason_code": "restricted"},
        ),
    )

    assert is_scope_narrower_or_equal(parent, child)


def test_narrowed_validity_window_is_accepted() -> None:
    assert is_scope_narrower_or_equal(_parent(), _child())


def test_removed_parent_expiry_is_not_narrower() -> None:
    assert not is_scope_narrower_or_equal(_parent(), _child(expires_at=None))


def test_narrowed_budget_is_accepted() -> None:
    assert budget_is_narrower_or_equal(
        BudgetSpec(max_tokens=100, deadline=END),
        BudgetSpec(max_tokens=50, deadline=START),
    )


def test_removed_budget_limit_is_not_narrower() -> None:
    assert not budget_is_narrower_or_equal(BudgetSpec(max_tokens=100), None)


def test_limit_can_be_added_to_unbounded_budget() -> None:
    assert budget_is_narrower_or_equal(None, BudgetSpec(max_steps=3))


def test_delegable_false_to_true_is_not_narrowing() -> None:
    parent = _parent(delegable=False)
    child = _child(parent, delegable=True)

    assert not is_scope_narrower_or_equal(parent, child)


def test_principal_change_requires_explicit_opt_in() -> None:
    parent = _parent()
    child = _child(parent, principal=ActorRef(ActorKind.AGENT, "AG-02"))

    assert not is_scope_narrower_or_equal(parent, child)
    assert is_scope_narrower_or_equal(parent, child, allow_principal_change=True)


def test_numeric_types_are_not_coerced_in_resource_or_constraints() -> None:
    assert not resource_scope_contains({"value": 1}, {"value": 1.0})
    assert not constraints_are_narrower_or_equal({"value": 1}, {"value": 1.0})
