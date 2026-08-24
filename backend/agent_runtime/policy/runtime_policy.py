from dataclasses import dataclass
from decimal import Decimal
from typing import Final


@dataclass(frozen=True, slots=True)
class AgentRuntimePolicy:
    """Configurable technical guardrails without business permission semantics."""

    max_steps_per_run: int = 24
    max_plan_versions: int = 6
    max_parallel_steps: int = 4
    max_delegation_depth: int = 2
    max_tool_calls_per_step: int = 8
    max_retries_per_step: int = 2
    max_review_cycles: int = 2
    max_evidence_rounds: int = 3
    context_compress_at: Decimal = Decimal("0.70")
    max_context_utilization: Decimal = Decimal("0.80")
    run_deadline_default_seconds: int = 600
    step_deadline_default_seconds: int = 120
    gate_wait_pauses_run_deadline: bool = True
    default_cost_budget: Decimal | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "max_steps_per_run",
            "max_plan_versions",
            "max_parallel_steps",
            "max_delegation_depth",
            "max_tool_calls_per_step",
            "max_retries_per_step",
            "max_review_cycles",
            "max_evidence_rounds",
        ):
            _require_non_negative_int(getattr(self, field_name), field_name)
        _require_positive_int(self.run_deadline_default_seconds, "run_deadline_default_seconds")
        _require_positive_int(self.step_deadline_default_seconds, "step_deadline_default_seconds")
        if not isinstance(self.context_compress_at, Decimal):
            raise TypeError("context_compress_at must be a Decimal")
        if not isinstance(self.max_context_utilization, Decimal):
            raise TypeError("max_context_utilization must be a Decimal")
        if not self.context_compress_at.is_finite():
            raise ValueError("context_compress_at must be finite")
        if not self.max_context_utilization.is_finite():
            raise ValueError("max_context_utilization must be finite")
        if not (
            Decimal("0") < self.context_compress_at < self.max_context_utilization <= Decimal("1")
        ):
            raise ValueError(
                "ratios must satisfy 0 < context_compress_at < max_context_utilization <= 1"
            )
        if not isinstance(self.gate_wait_pauses_run_deadline, bool):
            raise TypeError("gate_wait_pauses_run_deadline must be a bool")
        if self.default_cost_budget is not None:
            if not isinstance(self.default_cost_budget, Decimal):
                raise TypeError("default_cost_budget must be a Decimal or None")
            if not self.default_cost_budget.is_finite():
                raise ValueError("default_cost_budget must be finite")
            if self.default_cost_budget < Decimal("0"):
                raise ValueError("default_cost_budget must be >= 0")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")


BASELINE_AGENT_RUNTIME_POLICY: Final = AgentRuntimePolicy()
