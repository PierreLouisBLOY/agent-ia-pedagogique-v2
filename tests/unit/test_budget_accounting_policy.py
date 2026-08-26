from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.agent_runtime.contracts import BudgetSpec
from backend.agent_runtime.policy import AgentRuntimePolicy
from backend.agent_runtime.recovery import (
    BudgetAccountingPolicy,
    BudgetCheckDisposition,
    BudgetDimension,
    BudgetMetricCompleteness,
    BudgetState,
    BudgetStateError,
    BudgetStateErrorCode,
    BudgetUsageDelta,
    EffectiveBudgetLimits,
    resolve_effective_budget_limits,
)
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(seconds=10))
POLICY = BudgetAccountingPolicy()


def _state(
    *,
    limits: EffectiveBudgetLimits | None = None,
    **changes: object,
) -> BudgetState:
    values: dict[str, object] = {
        "run_id": "run-1",
        "version": 1,
        "limits": limits or EffectiveBudgetLimits(),
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return BudgetState(**values)  # type: ignore[arg-type]


def test_resolver_maps_plan_budget_and_runtime_policy_by_scope() -> None:
    limits = resolve_effective_budget_limits(
        plan_budget=BudgetSpec(
            max_tokens=100,
            max_cost=Decimal("5"),
            max_runtime_seconds=300,
            max_retries=7,
            max_steps=12,
            max_tool_calls=20,
        ),
        runtime_policy=AgentRuntimePolicy(
            max_steps_per_run=10,
            max_retries_per_step=2,
            max_tool_calls_per_step=3,
            run_deadline_default_seconds=200,
            default_cost_budget=Decimal("4"),
        ),
    )

    assert limits.max_tokens == 100
    assert limits.max_cost == Decimal("4")
    assert limits.max_active_runtime_seconds == 200
    assert limits.max_steps_per_run == 10
    assert limits.max_retries_per_envelope == 7
    assert limits.max_retries_per_step == 2
    assert limits.max_tool_calls_per_run == 20
    assert limits.max_tool_calls_per_step == 3


def test_resolver_intersects_plan_and_scope_without_widening() -> None:
    later_deadline = Instant(NOW.value + timedelta(hours=2))
    early_deadline = Instant(NOW.value + timedelta(hours=1))
    limits = resolve_effective_budget_limits(
        plan_budget=BudgetSpec(
            max_tokens=100,
            max_cost=Decimal("8"),
            deadline=later_deadline,
            max_steps=9,
            max_tool_calls=12,
        ),
        scope_budget=BudgetSpec(
            max_tokens=80,
            max_cost=Decimal("6"),
            deadline=early_deadline,
            max_steps=7,
            max_tool_calls=10,
        ),
        runtime_policy=AgentRuntimePolicy(
            max_steps_per_run=8,
            default_cost_budget=Decimal("7"),
        ),
    )

    assert limits.max_tokens == 80
    assert limits.max_cost == Decimal("6")
    assert limits.deadline == early_deadline
    assert limits.max_steps_per_run == 7
    assert limits.max_tool_calls_per_run == 10


def test_resolver_none_adds_no_limit_and_runtime_defaults_remain_caps() -> None:
    runtime = AgentRuntimePolicy(
        max_steps_per_run=5,
        max_retries_per_step=1,
        max_tool_calls_per_step=2,
        run_deadline_default_seconds=90,
        default_cost_budget=None,
    )

    limits = resolve_effective_budget_limits(runtime_policy=runtime)

    assert limits.max_tokens is None
    assert limits.max_cost is None
    assert limits.deadline is None
    assert limits.max_steps_per_run == 5
    assert limits.max_active_runtime_seconds == 90


def test_run_and_step_tool_call_and_retry_dimensions_are_never_merged() -> None:
    limits = resolve_effective_budget_limits(
        plan_budget=BudgetSpec(max_retries=9, max_tool_calls=11),
        runtime_policy=AgentRuntimePolicy(
            max_retries_per_step=2,
            max_tool_calls_per_step=3,
        ),
    )

    assert limits.max_retries_per_envelope == 9
    assert limits.max_retries_per_step == 2
    assert limits.max_tool_calls_per_run == 11
    assert limits.max_tool_calls_per_step == 3


def test_apply_delta_accumulates_every_counter_and_increments_version() -> None:
    state = _state(
        consumed_tokens=5,
        consumed_cost=Decimal("1.25"),
        active_runtime_seconds=Decimal("2.5"),
        steps_started=1,
        retries_by_step={"step-1": 1},
        tool_calls_by_step={"step-1": 2},
    )
    delta = BudgetUsageDelta(
        tokens=7,
        cost=Decimal("0.75"),
        active_runtime_seconds=Decimal("1.5"),
        steps_started=2,
        retries_by_step={"step-1": 1, "step-2": 2},
        tool_calls_by_step={"step-1": 1, "step-2": 3},
    )

    updated = POLICY.apply_delta(state=state, delta=delta, now=LATER)

    assert updated.version == 2
    assert updated.consumed_tokens == 12
    assert updated.consumed_cost == Decimal("2.00")
    assert updated.active_runtime_seconds == Decimal("4.0")
    assert updated.steps_started == 3
    assert dict(updated.retries_by_step) == {"step-1": 2, "step-2": 2}
    assert dict(updated.tool_calls_by_step) == {"step-1": 3, "step-2": 3}
    assert updated.tool_calls_total == 6


def test_unknown_observation_degrades_completeness_without_resetting_usage() -> None:
    state = _state(consumed_tokens=10, consumed_cost=Decimal("2"))
    delta = BudgetUsageDelta(
        tokens=None,
        cost=None,
        token_completeness=BudgetMetricCompleteness.UNKNOWN,
        cost_completeness=BudgetMetricCompleteness.UNKNOWN,
    )

    updated = POLICY.apply_delta(state=state, delta=delta, now=LATER)

    assert updated.consumed_tokens == 10
    assert updated.consumed_cost == Decimal("2")
    assert updated.token_completeness is BudgetMetricCompleteness.PARTIAL
    assert updated.cost_completeness is BudgetMetricCompleteness.PARTIAL


def test_configured_cap_with_unknown_usage_is_not_within_limit() -> None:
    state = _state(
        limits=EffectiveBudgetLimits(max_tokens=100, max_cost=Decimal("10")),
        token_completeness=BudgetMetricCompleteness.UNKNOWN,
        cost_completeness=BudgetMetricCompleteness.PARTIAL,
    )

    result = POLICY.evaluate(state=state, now=NOW)

    assert result.disposition is BudgetCheckDisposition.USAGE_UNKNOWN
    assert result.unknown_dimensions == (BudgetDimension.TOKENS, BudgetDimension.COST)


def test_known_lower_bound_over_cap_is_exceeded_even_when_usage_is_partial() -> None:
    state = _state(
        limits=EffectiveBudgetLimits(max_tokens=5),
        consumed_tokens=6,
        token_completeness=BudgetMetricCompleteness.PARTIAL,
    )

    result = POLICY.evaluate(state=state, now=NOW)

    assert result.disposition is BudgetCheckDisposition.LIMIT_EXCEEDED
    assert result.exceeded_dimensions == (BudgetDimension.TOKENS,)
    assert result.unknown_dimensions == ()


def test_evaluation_reports_multiple_exceeded_dimensions() -> None:
    limits = EffectiveBudgetLimits(
        max_tokens=5,
        max_cost=Decimal("1"),
        max_active_runtime_seconds=2,
        max_steps_per_run=1,
        max_retries_per_envelope=1,
        max_retries_per_step=1,
        max_tool_calls_per_run=1,
        max_tool_calls_per_step=1,
    )
    state = _state(
        limits=limits,
        consumed_tokens=6,
        consumed_cost=Decimal("2"),
        active_runtime_seconds=Decimal("3"),
        steps_started=2,
        retries_by_step={"step-1": 2},
        tool_calls_by_step={"step-1": 2},
    )

    result = POLICY.evaluate(state=state, now=NOW)

    assert result.disposition is BudgetCheckDisposition.LIMIT_EXCEEDED
    assert set(result.exceeded_dimensions) == {
        BudgetDimension.TOKENS,
        BudgetDimension.COST,
        BudgetDimension.ACTIVE_RUNTIME,
        BudgetDimension.STEPS,
        BudgetDimension.RETRIES_PER_ENVELOPE,
        BudgetDimension.RETRIES_PER_STEP,
        BudgetDimension.TOOL_CALLS_PER_RUN,
        BudgetDimension.TOOL_CALLS_PER_STEP,
    }


def test_deadline_is_distinct_and_fails_closed_at_boundary() -> None:
    state = _state(limits=EffectiveBudgetLimits(deadline=LATER))

    before = POLICY.evaluate(state=state, now=NOW)
    at_deadline = POLICY.evaluate(state=state, now=LATER)

    assert before.disposition is BudgetCheckDisposition.WITHIN_LIMIT
    assert at_deadline.exceeded_dimensions == (BudgetDimension.DEADLINE,)


def test_compare_and_set_rejects_stale_version_and_counter_reset() -> None:
    current = _state(retries_by_step={"step-1": 2})
    valid = POLICY.apply_delta(state=current, delta=BudgetUsageDelta(), now=LATER)
    with pytest.raises(BudgetStateError) as stale:
        POLICY.validate_compare_and_set(
            current=current,
            expected_version=0,
            replacement=valid,
        )
    assert stale.value.code is BudgetStateErrorCode.VERSION_CONFLICT

    reset = replace(valid, retries_by_step={"step-1": 1})
    with pytest.raises(BudgetStateError) as invalid:
        POLICY.validate_compare_and_set(
            current=current,
            expected_version=1,
            replacement=reset,
        )
    assert invalid.value.code is BudgetStateErrorCode.INVALID_STATE


def test_apply_delta_rejects_time_regression() -> None:
    state = _state(updated_at=LATER)

    with pytest.raises(ValueError, match="now"):
        POLICY.apply_delta(state=state, delta=BudgetUsageDelta(), now=NOW)
