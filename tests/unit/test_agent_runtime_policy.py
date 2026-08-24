from dataclasses import fields
from decimal import Decimal

import pytest

from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)


def test_runtime_policy_baseline_values_are_exact() -> None:
    assert BASELINE_AGENT_RUNTIME_POLICY == AgentRuntimePolicy(
        max_steps_per_run=24,
        max_plan_versions=6,
        max_parallel_steps=4,
        max_delegation_depth=2,
        max_tool_calls_per_step=8,
        max_retries_per_step=2,
        max_review_cycles=2,
        max_evidence_rounds=3,
        context_compress_at=Decimal("0.70"),
        max_context_utilization=Decimal("0.80"),
        run_deadline_default_seconds=600,
        step_deadline_default_seconds=120,
        gate_wait_pauses_run_deadline=True,
        default_cost_budget=None,
    )


def test_runtime_policy_accepts_valid_custom_configuration() -> None:
    policy = AgentRuntimePolicy(
        max_steps_per_run=0,
        max_parallel_steps=1,
        context_compress_at=Decimal("0.5"),
        max_context_utilization=Decimal("1"),
        run_deadline_default_seconds=1,
        step_deadline_default_seconds=1,
        gate_wait_pauses_run_deadline=False,
        default_cost_budget=Decimal("0"),
    )

    assert policy.max_steps_per_run == 0
    assert policy.default_cost_budget == Decimal("0")


@pytest.mark.parametrize(
    "field_name",
    (
        "max_steps_per_run",
        "max_plan_versions",
        "max_parallel_steps",
        "max_delegation_depth",
        "max_tool_calls_per_step",
        "max_retries_per_step",
        "max_review_cycles",
        "max_evidence_rounds",
        "run_deadline_default_seconds",
        "step_deadline_default_seconds",
    ),
)
def test_runtime_policy_rejects_bool_for_integer_fields(field_name: str) -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        AgentRuntimePolicy(**{field_name: True})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    (
        {"context_compress_at": Decimal("0")},
        {"context_compress_at": Decimal("0.80")},
        {"max_context_utilization": Decimal("1.01")},
        {"context_compress_at": Decimal("NaN")},
    ),
)
def test_runtime_policy_rejects_incoherent_ratios(overrides: dict[str, Decimal]) -> None:
    with pytest.raises(ValueError):
        AgentRuntimePolicy(**overrides)  # type: ignore[arg-type]


def test_runtime_policy_requires_decimal_ratios_and_cost() -> None:
    with pytest.raises(TypeError, match="context_compress_at must be a Decimal"):
        AgentRuntimePolicy(context_compress_at=0.7)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="default_cost_budget must be a Decimal"):
        AgentRuntimePolicy(default_cost_budget=1)  # type: ignore[arg-type]


def test_runtime_policy_rejects_negative_cost_budget() -> None:
    with pytest.raises(ValueError, match="default_cost_budget must be >= 0"):
        AgentRuntimePolicy(default_cost_budget=Decimal("-0.01"))


def test_runtime_mode_and_autonomy_cannot_derive_permissions() -> None:
    field_names = {field.name for field in fields(AgentRuntimePolicy)}

    assert field_names.isdisjoint(
        {"runtime_mode", "autonomy_level", "permission_scope", "permissions"}
    )
