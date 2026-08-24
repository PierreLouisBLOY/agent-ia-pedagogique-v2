from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import ActorKind, ActorRef, BudgetSpec, PermissionScope
from backend.agent_runtime.policy import (
    PermissionOperation,
    PermissionScopeEvaluator,
    ScopeCheck,
    ScopeEvaluationCode,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 10, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
PRINCIPAL = ActorRef(ActorKind.USER, "user-1")
CAP_R01 = CapabilityId("CAP-R01")


def _scope(**overrides: object) -> PermissionScope:
    values: dict[str, object] = {
        "principal": PRINCIPAL,
        "capability_ids": (CAP_R01,),
        "resource_scope": {
            "course_ids": ("course-1", "course-2"),
            "tenant": "tenant-1",
            "nested": {"section": "section-1", "version": "v1"},
        },
        "operations": (PermissionOperation.READ.value,),
        "constraints": {
            "formats": ("pdf", "docx"),
            "tenant": "tenant-1",
        },
        "valid_from": BEFORE,
        "expires_at": AFTER,
        "budget": BudgetSpec(max_tokens=100),
        "delegable": False,
        "gate_requirements": ("human_review",),
        "deny_rules": (),
    }
    values.update(overrides)
    return PermissionScope(**values)  # type: ignore[arg-type]


def _check(**overrides: object) -> ScopeCheck:
    values: dict[str, object] = {
        "principal": PRINCIPAL,
        "capability_id": CAP_R01,
        "operation": PermissionOperation.READ,
        "resource_scope": {
            "course_ids": ("course-1",),
            "nested": {"section": "section-1"},
        },
        "constraints": {"formats": ("pdf",), "tenant": "tenant-1"},
        "requested_budget": BudgetSpec(max_tokens=50),
        "satisfied_gate_requirements": ("human_review",),
        "evaluated_at": NOW,
        "revoked": False,
    }
    values.update(overrides)
    return ScopeCheck(**values)  # type: ignore[arg-type]


def _code(scope: PermissionScope, check: ScopeCheck | None = None) -> ScopeEvaluationCode:
    return PermissionScopeEvaluator().evaluate(scope, check or _check()).code


def test_active_nominal_scope_allows_at_inclusive_valid_from() -> None:
    scope = _scope(valid_from=NOW)

    evaluation = PermissionScopeEvaluator().evaluate(scope, _check(evaluated_at=NOW))

    assert evaluation.allowed
    assert evaluation.code is ScopeEvaluationCode.ALLOW


def test_principal_mismatch_is_refused() -> None:
    assert (
        _code(
            _scope(),
            _check(principal=ActorRef(ActorKind.USER, "user-2")),
        )
        is ScopeEvaluationCode.PRINCIPAL_MISMATCH
    )


def test_revocation_precedes_time_window() -> None:
    assert (
        _code(
            _scope(
                valid_from=AFTER,
                expires_at=Instant(AFTER.value + timedelta(hours=1)),
            ),
            _check(revoked=True),
        )
        is ScopeEvaluationCode.REVOKED
    )


def test_before_valid_from_is_refused() -> None:
    assert (
        _code(
            _scope(
                valid_from=AFTER,
                expires_at=Instant(AFTER.value + timedelta(hours=1)),
            )
        )
        is ScopeEvaluationCode.NOT_YET_VALID
    )


def test_expires_at_is_exclusive() -> None:
    assert _code(_scope(expires_at=NOW), _check(evaluated_at=NOW)) is ScopeEvaluationCode.EXPIRED


def test_capability_not_granted_is_refused() -> None:
    assert (
        _code(_scope(), _check(capability_id=CapabilityId("CAP-R02")))
        is ScopeEvaluationCode.CAPABILITY_NOT_GRANTED
    )


def test_operation_not_granted_is_refused() -> None:
    assert (
        _code(_scope(), _check(operation=PermissionOperation.TRANSFORM))
        is ScopeEvaluationCode.OPERATION_NOT_GRANTED
    )


def test_resource_subset_is_accepted() -> None:
    assert _code(_scope()) is ScopeEvaluationCode.ALLOW


def test_new_resource_is_refused() -> None:
    assert (
        _code(_scope(), _check(resource_scope={"course_ids": ("course-3",)}))
        is ScopeEvaluationCode.RESOURCE_OUT_OF_SCOPE
    )


def test_equal_constraints_are_accepted() -> None:
    assert (
        _code(
            _scope(),
            _check(constraints={"formats": ("pdf", "docx"), "tenant": "tenant-1"}),
        )
        is ScopeEvaluationCode.ALLOW
    )


def test_narrower_constraint_allowlist_is_accepted() -> None:
    assert _code(_scope()) is ScopeEvaluationCode.ALLOW


def test_omitted_parent_constraint_is_refused() -> None:
    assert (
        _code(_scope(), _check(constraints={"formats": ("pdf",)}))
        is ScopeEvaluationCode.CONSTRAINT_OUT_OF_SCOPE
    )


def test_capability_deny_precedes_missing_capability_grant() -> None:
    scope = _scope(deny_rules=({"capability_id": "CAP-G01"},))
    evaluation = PermissionScopeEvaluator().evaluate(
        scope, _check(capability_id=CapabilityId("CAP-G01"))
    )

    assert evaluation.code is ScopeEvaluationCode.EXPLICIT_DENY
    assert evaluation.matched_deny_rule_index == 0


def test_operation_deny_precedes_missing_operation_grant() -> None:
    scope = _scope(deny_rules=({"operation": "transform"},))

    assert (
        _code(scope, _check(operation=PermissionOperation.TRANSFORM))
        is ScopeEvaluationCode.EXPLICIT_DENY
    )


def test_resource_intersection_deny_matches_structurally() -> None:
    scope = _scope(deny_rules=({"resource_scope": {"course_ids": ("course-1",)}},))

    assert _code(scope) is ScopeEvaluationCode.EXPLICIT_DENY


@pytest.mark.parametrize("deny_rule", ({}, {"reason_code": "maintenance"}))
def test_selectorless_deny_rule_is_global(deny_rule: dict[str, object]) -> None:
    assert _code(_scope(deny_rules=(deny_rule,))) is ScopeEvaluationCode.EXPLICIT_DENY


def test_unknown_deny_key_invalidates_scope() -> None:
    assert _code(_scope(deny_rules=({"unknown": "value"},))) is ScopeEvaluationCode.INVALID_SCOPE


@pytest.mark.parametrize(
    "deny_rule",
    (
        {"capability_id": " "},
        {"operation": "delete"},
        {"resource_scope": "course-1"},
        {"reason_code": 1},
    ),
)
def test_malformed_deny_rule_invalidates_scope(deny_rule: dict[str, object]) -> None:
    assert _code(_scope(deny_rules=(deny_rule,))) is ScopeEvaluationCode.INVALID_SCOPE


def test_satisfied_gate_allows_evaluation_to_continue() -> None:
    assert _code(_scope()) is ScopeEvaluationCode.ALLOW


def test_missing_gates_are_reported_in_scope_order() -> None:
    scope = _scope(gate_requirements=("first", "second", "third"))
    evaluation = PermissionScopeEvaluator().evaluate(
        scope,
        _check(satisfied_gate_requirements=("second",)),
    )

    assert evaluation.code is ScopeEvaluationCode.GATE_REQUIRED
    assert evaluation.missing_gate_requirements == ("first", "third")


def test_narrower_requested_budget_is_accepted() -> None:
    assert _code(_scope()) is ScopeEvaluationCode.ALLOW


def test_larger_requested_budget_is_refused() -> None:
    assert (
        _code(_scope(), _check(requested_budget=BudgetSpec(max_tokens=101)))
        is ScopeEvaluationCode.BUDGET_OUT_OF_SCOPE
    )


def test_removing_parent_budget_limit_is_refused() -> None:
    assert _code(_scope(), _check(requested_budget=None)) is ScopeEvaluationCode.BUDGET_OUT_OF_SCOPE


@pytest.mark.parametrize(
    "scope",
    (
        _scope(capability_ids=(CAP_R01, CAP_R01)),
        _scope(operations=("read", "read")),
        _scope(gate_requirements=("human_review", "human_review")),
    ),
)
def test_duplicate_scope_entries_fail_closed(scope: PermissionScope) -> None:
    assert _code(scope) is ScopeEvaluationCode.INVALID_SCOPE


def test_unknown_operation_in_scope_fails_closed() -> None:
    assert _code(_scope(operations=("delete",))) is ScopeEvaluationCode.INVALID_SCOPE


def test_unknown_capability_in_scope_fails_closed() -> None:
    assert (
        _code(_scope(capability_ids=(CapabilityId("CAP-X99"),)))
        is ScopeEvaluationCode.INVALID_SCOPE
    )


def test_scope_check_deeply_freezes_mappings_and_requires_unique_gates() -> None:
    mutable = {"nested": {"ids": ["one"]}}
    check = _check(resource_scope=mutable)
    mutable["nested"] = {"ids": ["two"]}

    assert check.resource_scope["nested"] != mutable["nested"]
    with pytest.raises(ValueError, match="must be unique"):
        replace(check, satisfied_gate_requirements=("gate", "gate"))
