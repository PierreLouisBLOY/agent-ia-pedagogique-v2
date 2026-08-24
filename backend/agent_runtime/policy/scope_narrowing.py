from __future__ import annotations

from collections.abc import Mapping

from backend.agent_runtime.contracts import BudgetSpec, PermissionScope

_BUDGET_LIMIT_FIELDS = (
    "max_tokens",
    "max_cost",
    "max_runtime_seconds",
    "max_retries",
    "max_steps",
    "max_tool_calls",
)


def resource_scope_contains(granted: Mapping[str, object], requested: Mapping[str, object]) -> bool:
    if not isinstance(granted, Mapping) or not isinstance(requested, Mapping):
        raise TypeError("resource scopes must be mappings")
    return _mapping_contains(granted, requested)


def constraints_are_narrower_or_equal(
    parent_constraints: Mapping[str, object],
    effective_constraints: Mapping[str, object],
) -> bool:
    if not isinstance(parent_constraints, Mapping) or not isinstance(
        effective_constraints, Mapping
    ):
        raise TypeError("constraints must be mappings")
    return _constraints_contain(parent_constraints, effective_constraints)


def resource_scopes_intersect(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        raise TypeError("resource scopes must be mappings")
    return any(
        key in right and _values_intersect(left_value, right[key])
        for key, left_value in left.items()
    )


def budget_is_narrower_or_equal(parent: BudgetSpec | None, child: BudgetSpec | None) -> bool:
    if parent is not None and not isinstance(parent, BudgetSpec):
        raise TypeError("parent must be a BudgetSpec or None")
    if child is not None and not isinstance(child, BudgetSpec):
        raise TypeError("child must be a BudgetSpec or None")
    if child is None:
        return parent is None or not _budget_has_limit(parent)
    if parent is None:
        return True
    for field_name in _BUDGET_LIMIT_FIELDS:
        parent_value = getattr(parent, field_name)
        child_value = getattr(child, field_name)
        if parent_value is not None and (child_value is None or child_value > parent_value):
            return False
    if parent.deadline is not None and (
        child.deadline is None or child.deadline.value > parent.deadline.value
    ):
        return False
    return True


def is_scope_narrower_or_equal(
    parent: PermissionScope,
    child: PermissionScope,
    *,
    allow_principal_change: bool = False,
) -> bool:
    if not isinstance(parent, PermissionScope):
        raise TypeError("parent must be a PermissionScope")
    if not isinstance(child, PermissionScope):
        raise TypeError("child must be a PermissionScope")
    if not isinstance(allow_principal_change, bool):
        raise TypeError("allow_principal_change must be a bool")
    if not allow_principal_change and child.principal != parent.principal:
        return False
    if not set(child.capability_ids).issubset(parent.capability_ids):
        return False
    if not set(child.operations).issubset(parent.operations):
        return False
    if not resource_scope_contains(parent.resource_scope, child.resource_scope):
        return False
    if not constraints_are_narrower_or_equal(parent.constraints, child.constraints):
        return False
    if parent.valid_from is not None and (
        child.valid_from is None or child.valid_from.value < parent.valid_from.value
    ):
        return False
    if parent.expires_at is not None and (
        child.expires_at is None or child.expires_at.value > parent.expires_at.value
    ):
        return False
    if not budget_is_narrower_or_equal(parent.budget, child.budget):
        return False
    if any(requirement not in child.gate_requirements for requirement in parent.gate_requirements):
        return False
    if not _all_structural_items_preserved(parent.deny_rules, child.deny_rules):
        return False
    return not (not parent.delegable and child.delegable)


def structurally_equal(left: object, right: object) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            structurally_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, tuple) and isinstance(right, tuple):
        return len(left) == len(right) and all(
            structurally_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return type(left) is type(right) and left == right


def _mapping_contains(granted: Mapping[str, object], requested: Mapping[str, object]) -> bool:
    return all(
        key in granted and _resource_value_contains(granted[key], requested_value)
        for key, requested_value in requested.items()
    )


def _resource_value_contains(granted: object, requested: object) -> bool:
    if isinstance(granted, Mapping) and isinstance(requested, Mapping):
        return _mapping_contains(granted, requested)
    if isinstance(granted, tuple) and isinstance(requested, tuple):
        return all(
            any(structurally_equal(item, candidate) for candidate in granted) for item in requested
        )
    return structurally_equal(granted, requested)


def _constraints_contain(parent: object, effective: object) -> bool:
    if isinstance(parent, Mapping) and isinstance(effective, Mapping):
        return all(
            key in effective and _constraints_contain(value, effective[key])
            for key, value in parent.items()
        )
    if isinstance(parent, tuple) and isinstance(effective, tuple):
        return all(
            any(structurally_equal(item, candidate) for candidate in parent) for item in effective
        )
    return structurally_equal(parent, effective)


def _values_intersect(left: object, right: object) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return resource_scopes_intersect(left, right)
    if isinstance(left, tuple) and isinstance(right, tuple):
        return any(
            structurally_equal(left_item, right_item) for left_item in left for right_item in right
        )
    return structurally_equal(left, right)


def _budget_has_limit(budget: BudgetSpec) -> bool:
    return budget.deadline is not None or any(
        getattr(budget, field_name) is not None for field_name in _BUDGET_LIMIT_FIELDS
    )


def _all_structural_items_preserved(
    parent_items: tuple[Mapping[str, object], ...],
    child_items: tuple[Mapping[str, object], ...],
) -> bool:
    available = list(child_items)
    for parent_item in parent_items:
        match_index = next(
            (
                index
                for index, child_item in enumerate(available)
                if structurally_equal(parent_item, child_item)
            ),
            None,
        )
        if match_index is None:
            return False
        available.pop(match_index)
    return True
