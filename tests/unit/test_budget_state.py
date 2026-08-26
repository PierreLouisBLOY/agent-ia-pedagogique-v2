from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.agent_runtime.recovery import (
    BudgetMetricCompleteness,
    BudgetState,
    BudgetUsageDelta,
    EffectiveBudgetLimits,
    retry_count_from_attempt_count,
)
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(seconds=1))


def _state(**changes: object) -> BudgetState:
    values: dict[str, object] = {
        "run_id": "run-1",
        "version": 1,
        "limits": EffectiveBudgetLimits(),
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return BudgetState(**values)  # type: ignore[arg-type]


def test_initial_budget_state_is_zero_known_and_versioned() -> None:
    state = _state()

    assert state.version == 1
    assert state.consumed_tokens == 0
    assert state.consumed_cost == Decimal("0")
    assert state.active_runtime_seconds == Decimal("0")
    assert state.steps_started == 0
    assert state.tool_calls_total == 0
    assert state.retries_total == 0
    assert state.token_completeness is BudgetMetricCompleteness.COMPLETE
    assert state.cost_completeness is BudgetMetricCompleteness.COMPLETE


def test_budget_state_and_counter_mappings_are_immutable() -> None:
    source = {"step-1": 2}
    state = _state(tool_calls_by_step=source)
    source["step-1"] = 9

    assert state.tool_calls_by_step["step-1"] == 2
    with pytest.raises(TypeError):
        state.tool_calls_by_step["step-1"] = 3  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        state.version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("version", 0),
        ("consumed_tokens", -1),
        ("consumed_cost", Decimal("-0.01")),
        ("active_runtime_seconds", Decimal("-0.1")),
        ("steps_started", -1),
    ],
)
def test_budget_state_rejects_invalid_versions_and_decrements(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        _state(**{field_name: value})


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity")])
def test_budget_state_rejects_non_finite_decimals(value: Decimal) -> None:
    with pytest.raises(ValueError, match="finite"):
        _state(consumed_cost=value)
    with pytest.raises(ValueError, match="finite"):
        EffectiveBudgetLimits(max_cost=value)


def test_budget_state_rejects_unsafe_step_ids_and_negative_counters() -> None:
    with pytest.raises(ValueError, match="safe"):
        _state(retries_by_step={"../step": 1})
    with pytest.raises(ValueError, match=">= 0"):
        _state(tool_calls_by_step={"step-1": -1})


def test_budget_state_rejects_non_monotonic_timestamps() -> None:
    with pytest.raises(ValueError, match="updated_at"):
        _state(created_at=LATER, updated_at=NOW)


def test_usage_delta_requires_non_negative_observations() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        BudgetUsageDelta(tokens=-1)
    with pytest.raises(ValueError, match=">= 0"):
        BudgetUsageDelta(cost=Decimal("-1"))
    with pytest.raises(ValueError, match=">= 0"):
        BudgetUsageDelta(active_runtime_seconds=Decimal("-1"))


def test_unknown_usage_is_explicit_and_never_encoded_as_zero() -> None:
    delta = BudgetUsageDelta(
        tokens=None,
        cost=None,
        token_completeness=BudgetMetricCompleteness.UNKNOWN,
        cost_completeness=BudgetMetricCompleteness.UNKNOWN,
    )

    assert delta.tokens is None
    assert delta.cost is None
    with pytest.raises(ValueError, match="missing tokens"):
        BudgetUsageDelta(tokens=None)
    with pytest.raises(ValueError, match="known tokens"):
        BudgetUsageDelta(
            tokens=0,
            token_completeness=BudgetMetricCompleteness.UNKNOWN,
        )


def test_attempt_one_is_not_a_retry() -> None:
    assert retry_count_from_attempt_count(0) == 0
    assert retry_count_from_attempt_count(1) == 0
    assert retry_count_from_attempt_count(3) == 2
    with pytest.raises(ValueError, match=">= 0"):
        retry_count_from_attempt_count(-1)
