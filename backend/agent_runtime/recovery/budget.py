from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from backend.agent_runtime.contracts import BudgetSpec
from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)
from backend.shared_kernel.time import Instant

_ZERO = Decimal("0")
_SAFE_STEP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


class BudgetMetricCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class BudgetCheckDisposition(StrEnum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    USAGE_UNKNOWN = "USAGE_UNKNOWN"


class BudgetDimension(StrEnum):
    TOKENS = "TOKENS"
    COST = "COST"
    ACTIVE_RUNTIME = "ACTIVE_RUNTIME"
    DEADLINE = "DEADLINE"
    STEPS = "STEPS"
    RETRIES_PER_ENVELOPE = "RETRIES_PER_ENVELOPE"
    RETRIES_PER_STEP = "RETRIES_PER_STEP"
    TOOL_CALLS_PER_RUN = "TOOL_CALLS_PER_RUN"
    TOOL_CALLS_PER_STEP = "TOOL_CALLS_PER_STEP"


class BudgetStateErrorCode(StrEnum):
    VERSION_CONFLICT = "VERSION_CONFLICT"
    RUN_MISMATCH = "RUN_MISMATCH"
    LIMITS_MISMATCH = "LIMITS_MISMATCH"
    INVALID_STATE = "INVALID_STATE"


_BUDGET_ERROR_MESSAGES = MappingProxyType(
    {
        BudgetStateErrorCode.VERSION_CONFLICT: "budget state version conflict",
        BudgetStateErrorCode.RUN_MISMATCH: "budget state run mismatch",
        BudgetStateErrorCode.LIMITS_MISMATCH: "budget state limits mismatch",
        BudgetStateErrorCode.INVALID_STATE: "invalid budget state replacement",
    }
)


class BudgetStateError(ValueError):
    code: BudgetStateErrorCode

    def __init__(self, code: BudgetStateErrorCode) -> None:
        if not isinstance(code, BudgetStateErrorCode):
            raise TypeError("code must be a BudgetStateErrorCode")
        self.code = code
        super().__init__(_BUDGET_ERROR_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class EffectiveBudgetLimits:
    """Resolved technical ceilings with run/envelope and step scopes kept distinct."""

    max_tokens: int | None = None
    max_cost: Decimal | None = None
    max_active_runtime_seconds: int | None = None
    deadline: Instant | None = None
    max_steps_per_run: int | None = None
    max_retries_per_envelope: int | None = None
    max_retries_per_step: int | None = None
    max_tool_calls_per_run: int | None = None
    max_tool_calls_per_step: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "max_tokens",
            "max_active_runtime_seconds",
            "max_steps_per_run",
            "max_retries_per_envelope",
            "max_retries_per_step",
            "max_tool_calls_per_run",
            "max_tool_calls_per_step",
        ):
            _require_optional_non_negative_int(getattr(self, field_name), field_name)
        _require_optional_non_negative_decimal(self.max_cost, "max_cost")
        if self.deadline is not None and not isinstance(self.deadline, Instant):
            raise TypeError("deadline must be an Instant or None")


@dataclass(frozen=True, slots=True)
class BudgetUsageDelta:
    """Non-negative accounting observation; missing metrics remain explicit."""

    tokens: int | None = 0
    cost: Decimal | None = _ZERO
    active_runtime_seconds: Decimal = _ZERO
    steps_started: int = 0
    retries_by_step: Mapping[str, int] = field(default_factory=dict)
    tool_calls_by_step: Mapping[str, int] = field(default_factory=dict)
    token_completeness: BudgetMetricCompleteness = BudgetMetricCompleteness.COMPLETE
    cost_completeness: BudgetMetricCompleteness = BudgetMetricCompleteness.COMPLETE

    def __post_init__(self) -> None:
        _require_optional_non_negative_int(self.tokens, "tokens")
        _require_optional_non_negative_decimal(self.cost, "cost")
        _require_non_negative_decimal(self.active_runtime_seconds, "active_runtime_seconds")
        _require_non_negative_int(self.steps_started, "steps_started")
        retries = _freeze_counter_mapping(self.retries_by_step, "retries_by_step")
        tool_calls = _freeze_counter_mapping(self.tool_calls_by_step, "tool_calls_by_step")
        _require_metric_observation(
            self.tokens,
            self.token_completeness,
            "tokens",
        )
        _require_metric_observation(
            self.cost,
            self.cost_completeness,
            "cost",
        )
        object.__setattr__(self, "retries_by_step", retries)
        object.__setattr__(self, "tool_calls_by_step", tool_calls)


@dataclass(frozen=True, slots=True)
class BudgetState:
    run_id: str
    version: int
    limits: EffectiveBudgetLimits
    created_at: Instant
    updated_at: Instant
    consumed_tokens: int = 0
    consumed_cost: Decimal = _ZERO
    active_runtime_seconds: Decimal = _ZERO
    steps_started: int = 0
    retries_by_step: Mapping[str, int] = field(default_factory=dict)
    tool_calls_by_step: Mapping[str, int] = field(default_factory=dict)
    token_completeness: BudgetMetricCompleteness = BudgetMetricCompleteness.COMPLETE
    cost_completeness: BudgetMetricCompleteness = BudgetMetricCompleteness.COMPLETE

    def __post_init__(self) -> None:
        _require_safe_step_id(self.run_id, "run_id")
        _require_positive_int(self.version, "version")
        if not isinstance(self.limits, EffectiveBudgetLimits):
            raise TypeError("limits must be EffectiveBudgetLimits")
        _require_instant(self.created_at, "created_at")
        _require_instant(self.updated_at, "updated_at")
        if self.updated_at.value < self.created_at.value:
            raise ValueError("updated_at must be >= created_at")
        _require_non_negative_int(self.consumed_tokens, "consumed_tokens")
        _require_non_negative_decimal(self.consumed_cost, "consumed_cost")
        _require_non_negative_decimal(
            self.active_runtime_seconds,
            "active_runtime_seconds",
        )
        _require_non_negative_int(self.steps_started, "steps_started")
        retries = _freeze_counter_mapping(self.retries_by_step, "retries_by_step")
        tool_calls = _freeze_counter_mapping(self.tool_calls_by_step, "tool_calls_by_step")
        _require_completeness(self.token_completeness, "token_completeness")
        _require_completeness(self.cost_completeness, "cost_completeness")
        object.__setattr__(self, "retries_by_step", retries)
        object.__setattr__(self, "tool_calls_by_step", tool_calls)

    @property
    def tool_calls_total(self) -> int:
        return sum(self.tool_calls_by_step.values())

    @property
    def retries_total(self) -> int:
        return sum(self.retries_by_step.values())


@dataclass(frozen=True, slots=True)
class BudgetCheckResult:
    disposition: BudgetCheckDisposition
    exceeded_dimensions: tuple[BudgetDimension, ...] = ()
    unknown_dimensions: tuple[BudgetDimension, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, BudgetCheckDisposition):
            raise TypeError("disposition must be a BudgetCheckDisposition")
        _require_dimension_tuple(self.exceeded_dimensions, "exceeded_dimensions")
        _require_dimension_tuple(self.unknown_dimensions, "unknown_dimensions")
        if set(self.exceeded_dimensions) & set(self.unknown_dimensions):
            raise ValueError("a dimension cannot be both exceeded and unknown")
        if self.disposition is BudgetCheckDisposition.WITHIN_LIMIT and (
            self.exceeded_dimensions or self.unknown_dimensions
        ):
            raise ValueError("WITHIN_LIMIT cannot contain problem dimensions")
        if self.disposition is BudgetCheckDisposition.LIMIT_EXCEEDED and not (
            self.exceeded_dimensions
        ):
            raise ValueError("LIMIT_EXCEEDED requires an exceeded dimension")
        if self.disposition is BudgetCheckDisposition.USAGE_UNKNOWN and (
            self.exceeded_dimensions or not self.unknown_dimensions
        ):
            raise ValueError("USAGE_UNKNOWN requires only unknown dimensions")


def resolve_effective_budget_limits(
    *,
    plan_budget: BudgetSpec | None = None,
    scope_budget: BudgetSpec | None = None,
    runtime_policy: AgentRuntimePolicy = BASELINE_AGENT_RUNTIME_POLICY,
) -> EffectiveBudgetLimits:
    """Intersect comparable run/envelope limits without folding in step budgets."""
    _require_optional_budget(plan_budget, "plan_budget")
    _require_optional_budget(scope_budget, "scope_budget")
    if not isinstance(runtime_policy, AgentRuntimePolicy):
        raise TypeError("runtime_policy must be an AgentRuntimePolicy")
    budgets = tuple(item for item in (plan_budget, scope_budget) if item is not None)
    return EffectiveBudgetLimits(
        max_tokens=_minimum_int(*(item.max_tokens for item in budgets)),
        max_cost=_minimum_decimal(
            *(item.max_cost for item in budgets),
            runtime_policy.default_cost_budget,
        ),
        max_active_runtime_seconds=_minimum_int(
            *(item.max_runtime_seconds for item in budgets),
            runtime_policy.run_deadline_default_seconds,
        ),
        deadline=_minimum_deadline(*(item.deadline for item in budgets)),
        max_steps_per_run=_minimum_int(
            *(item.max_steps for item in budgets),
            runtime_policy.max_steps_per_run,
        ),
        max_retries_per_envelope=_minimum_int(
            *(item.max_retries for item in budgets)
        ),
        max_retries_per_step=runtime_policy.max_retries_per_step,
        max_tool_calls_per_run=_minimum_int(
            *(item.max_tool_calls for item in budgets)
        ),
        max_tool_calls_per_step=runtime_policy.max_tool_calls_per_step,
    )


def retry_count_from_attempt_count(attempt_count: int) -> int:
    """Translate StepState lineage without importing or mutating StepState."""
    _require_non_negative_int(attempt_count, "attempt_count")
    return max(0, attempt_count - 1)


@dataclass(frozen=True, slots=True)
class BudgetAccountingPolicy:
    """Pure technical accounting; results never grant execution authority."""

    def apply_delta(
        self,
        *,
        state: BudgetState,
        delta: BudgetUsageDelta,
        now: Instant,
    ) -> BudgetState:
        _require_state(state)
        if not isinstance(delta, BudgetUsageDelta):
            raise TypeError("delta must be a BudgetUsageDelta")
        _require_instant(now, "now")
        if now.value < state.updated_at.value:
            raise ValueError("now must be >= state.updated_at")
        retries = _add_counter_mappings(state.retries_by_step, delta.retries_by_step)
        tool_calls = _add_counter_mappings(
            state.tool_calls_by_step,
            delta.tool_calls_by_step,
        )
        replacement = replace(
            state,
            version=state.version + 1,
            updated_at=now,
            consumed_tokens=state.consumed_tokens + (delta.tokens or 0),
            consumed_cost=state.consumed_cost + (delta.cost or _ZERO),
            active_runtime_seconds=(
                state.active_runtime_seconds + delta.active_runtime_seconds
            ),
            steps_started=state.steps_started + delta.steps_started,
            retries_by_step=retries,
            tool_calls_by_step=tool_calls,
            token_completeness=_merge_completeness(
                state.token_completeness,
                delta.token_completeness,
            ),
            cost_completeness=_merge_completeness(
                state.cost_completeness,
                delta.cost_completeness,
            ),
        )
        self.validate_compare_and_set(
            current=state,
            expected_version=state.version,
            replacement=replacement,
        )
        return replacement

    def evaluate(self, *, state: BudgetState, now: Instant) -> BudgetCheckResult:
        _require_state(state)
        _require_instant(now, "now")
        exceeded: list[BudgetDimension] = []
        unknown: list[BudgetDimension] = []
        limits = state.limits
        _evaluate_observed_metric(
            value=state.consumed_tokens,
            limit=limits.max_tokens,
            completeness=state.token_completeness,
            dimension=BudgetDimension.TOKENS,
            exceeded=exceeded,
            unknown=unknown,
        )
        _evaluate_observed_metric(
            value=state.consumed_cost,
            limit=limits.max_cost,
            completeness=state.cost_completeness,
            dimension=BudgetDimension.COST,
            exceeded=exceeded,
            unknown=unknown,
        )
        _append_if_exceeded(
            state.active_runtime_seconds,
            limits.max_active_runtime_seconds,
            BudgetDimension.ACTIVE_RUNTIME,
            exceeded,
        )
        if limits.deadline is not None and now.value >= limits.deadline.value:
            exceeded.append(BudgetDimension.DEADLINE)
        _append_if_exceeded(
            state.steps_started,
            limits.max_steps_per_run,
            BudgetDimension.STEPS,
            exceeded,
        )
        _append_if_exceeded(
            state.retries_total,
            limits.max_retries_per_envelope,
            BudgetDimension.RETRIES_PER_ENVELOPE,
            exceeded,
        )
        if _mapping_exceeds(state.retries_by_step, limits.max_retries_per_step):
            exceeded.append(BudgetDimension.RETRIES_PER_STEP)
        _append_if_exceeded(
            state.tool_calls_total,
            limits.max_tool_calls_per_run,
            BudgetDimension.TOOL_CALLS_PER_RUN,
            exceeded,
        )
        if _mapping_exceeds(
            state.tool_calls_by_step,
            limits.max_tool_calls_per_step,
        ):
            exceeded.append(BudgetDimension.TOOL_CALLS_PER_STEP)
        if exceeded:
            return BudgetCheckResult(
                BudgetCheckDisposition.LIMIT_EXCEEDED,
                exceeded_dimensions=tuple(exceeded),
                unknown_dimensions=tuple(unknown),
            )
        if unknown:
            return BudgetCheckResult(
                BudgetCheckDisposition.USAGE_UNKNOWN,
                unknown_dimensions=tuple(unknown),
            )
        return BudgetCheckResult(BudgetCheckDisposition.WITHIN_LIMIT)

    def validate_compare_and_set(
        self,
        *,
        current: BudgetState,
        expected_version: int,
        replacement: BudgetState,
    ) -> None:
        _require_state(current)
        _require_state(replacement)
        if type(expected_version) is not int:
            raise TypeError("expected_version must be an integer")
        if expected_version != current.version:
            raise BudgetStateError(BudgetStateErrorCode.VERSION_CONFLICT)
        if replacement.version != current.version + 1:
            raise BudgetStateError(BudgetStateErrorCode.VERSION_CONFLICT)
        if replacement.run_id != current.run_id:
            raise BudgetStateError(BudgetStateErrorCode.RUN_MISMATCH)
        if replacement.limits != current.limits:
            raise BudgetStateError(BudgetStateErrorCode.LIMITS_MISMATCH)
        if replacement.created_at != current.created_at:
            raise BudgetStateError(BudgetStateErrorCode.INVALID_STATE)
        if replacement.updated_at.value < current.updated_at.value:
            raise BudgetStateError(BudgetStateErrorCode.INVALID_STATE)
        if any(
            replacement_value < current_value
            for replacement_value, current_value in (
                (replacement.consumed_tokens, current.consumed_tokens),
                (replacement.consumed_cost, current.consumed_cost),
                (replacement.active_runtime_seconds, current.active_runtime_seconds),
                (replacement.steps_started, current.steps_started),
            )
        ):
            raise BudgetStateError(BudgetStateErrorCode.INVALID_STATE)
        if not _mapping_is_monotone(current.retries_by_step, replacement.retries_by_step):
            raise BudgetStateError(BudgetStateErrorCode.INVALID_STATE)
        if not _mapping_is_monotone(
            current.tool_calls_by_step,
            replacement.tool_calls_by_step,
        ):
            raise BudgetStateError(BudgetStateErrorCode.INVALID_STATE)
        if not _completeness_is_monotone(
            current.token_completeness,
            replacement.token_completeness,
        ) or not _completeness_is_monotone(
            current.cost_completeness,
            replacement.cost_completeness,
        ):
            raise BudgetStateError(BudgetStateErrorCode.INVALID_STATE)


def _require_optional_budget(value: BudgetSpec | None, field_name: str) -> None:
    if value is not None and not isinstance(value, BudgetSpec):
        raise TypeError(f"{field_name} must be a BudgetSpec or None")
    if value is not None:
        _require_optional_non_negative_decimal(value.max_cost, f"{field_name}.max_cost")


def _minimum_int(*values: int | None) -> int | None:
    present = tuple(value for value in values if value is not None)
    return min(present) if present else None


def _minimum_decimal(*values: Decimal | None) -> Decimal | None:
    present = tuple(value for value in values if value is not None)
    return min(present) if present else None


def _minimum_deadline(*values: Instant | None) -> Instant | None:
    present = tuple(value for value in values if value is not None)
    return min(present, key=lambda item: item.value) if present else None


def _require_metric_observation(
    value: int | Decimal | None,
    completeness: BudgetMetricCompleteness,
    field_name: str,
) -> None:
    _require_completeness(completeness, f"{field_name}_completeness")
    if value is None and completeness is not BudgetMetricCompleteness.UNKNOWN:
        raise ValueError(f"missing {field_name} must be UNKNOWN")
    if value is not None and completeness is BudgetMetricCompleteness.UNKNOWN:
        raise ValueError(f"known {field_name} cannot be UNKNOWN")


def _merge_completeness(
    current: BudgetMetricCompleteness,
    observed: BudgetMetricCompleteness,
) -> BudgetMetricCompleteness:
    if current is BudgetMetricCompleteness.COMPLETE and observed is BudgetMetricCompleteness.COMPLETE:
        return BudgetMetricCompleteness.COMPLETE
    if current is BudgetMetricCompleteness.UNKNOWN and observed is BudgetMetricCompleteness.UNKNOWN:
        return BudgetMetricCompleteness.UNKNOWN
    return BudgetMetricCompleteness.PARTIAL


def _completeness_is_monotone(
    current: BudgetMetricCompleteness,
    replacement: BudgetMetricCompleteness,
) -> bool:
    if current is BudgetMetricCompleteness.COMPLETE:
        return replacement in {
            BudgetMetricCompleteness.COMPLETE,
            BudgetMetricCompleteness.PARTIAL,
        }
    if current is BudgetMetricCompleteness.UNKNOWN:
        return replacement in {
            BudgetMetricCompleteness.UNKNOWN,
            BudgetMetricCompleteness.PARTIAL,
        }
    return replacement is BudgetMetricCompleteness.PARTIAL


def _evaluate_observed_metric(
    *,
    value: int | Decimal,
    limit: int | Decimal | None,
    completeness: BudgetMetricCompleteness,
    dimension: BudgetDimension,
    exceeded: list[BudgetDimension],
    unknown: list[BudgetDimension],
) -> None:
    if limit is None:
        return
    if value > limit:
        exceeded.append(dimension)
    elif completeness is not BudgetMetricCompleteness.COMPLETE:
        unknown.append(dimension)


def _append_if_exceeded(
    value: int | Decimal,
    limit: int | Decimal | None,
    dimension: BudgetDimension,
    exceeded: list[BudgetDimension],
) -> None:
    if limit is not None and value > limit:
        exceeded.append(dimension)


def _mapping_exceeds(values: Mapping[str, int], limit: int | None) -> bool:
    return limit is not None and any(value > limit for value in values.values())


def _add_counter_mappings(
    current: Mapping[str, int],
    delta: Mapping[str, int],
) -> Mapping[str, int]:
    merged = dict(current)
    for step_id, increment in delta.items():
        merged[step_id] = merged.get(step_id, 0) + increment
    return merged


def _mapping_is_monotone(
    current: Mapping[str, int],
    replacement: Mapping[str, int],
) -> bool:
    return all(
        step_id in replacement and replacement[step_id] >= value
        for step_id, value in current.items()
    )


def _freeze_counter_mapping(
    value: Mapping[str, int],
    field_name: str,
) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    normalized: dict[str, int] = {}
    for step_id, count in value.items():
        _require_safe_step_id(step_id, f"{field_name} key")
        _require_non_negative_int(count, f"{field_name} value")
        normalized[step_id] = count
    return MappingProxyType(normalized)


def _require_dimension_tuple(
    value: tuple[BudgetDimension, ...],
    field_name: str,
) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if any(not isinstance(item, BudgetDimension) for item in value):
        raise TypeError(f"{field_name} must contain BudgetDimension values")
    if len(set(value)) != len(value):
        raise ValueError(f"{field_name} must not contain duplicates")


def _require_state(value: BudgetState) -> None:
    if not isinstance(value, BudgetState):
        raise TypeError("state must be a BudgetState")


def _require_completeness(value: BudgetMetricCompleteness, field_name: str) -> None:
    if not isinstance(value, BudgetMetricCompleteness):
        raise TypeError(f"{field_name} must be a BudgetMetricCompleteness")


def _require_safe_step_id(value: str, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if not _SAFE_STEP_ID.fullmatch(value):
        raise ValueError(f"{field_name} must be a safe non-empty identifier")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _require_positive_int(value: int, field_name: str) -> None:
    _require_non_negative_int(value, field_name)
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")


def _require_optional_non_negative_int(value: int | None, field_name: str) -> None:
    if value is not None:
        _require_non_negative_int(value, field_name)


def _require_non_negative_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if value < _ZERO:
        raise ValueError(f"{field_name} must be >= 0")


def _require_optional_non_negative_decimal(
    value: Decimal | None,
    field_name: str,
) -> None:
    if value is not None:
        _require_non_negative_decimal(value, field_name)


def _require_instant(value: Instant, field_name: str) -> None:
    if not isinstance(value, Instant):
        raise TypeError(f"{field_name} must be an Instant")
