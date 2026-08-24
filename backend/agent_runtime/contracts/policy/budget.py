from dataclasses import dataclass
from decimal import Decimal

from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class BudgetSpec:
    """Declarative limits only; consumption and enforcement live downstream."""

    max_tokens: int | None = None
    max_cost: Decimal | None = None
    max_runtime_seconds: int | None = None
    deadline: Instant | None = None
    max_retries: int | None = None
    max_steps: int | None = None
    max_tool_calls: int | None = None

    def __post_init__(self) -> None:
        _require_optional_non_negative_int(self.max_tokens, "max_tokens")
        _require_optional_non_negative_decimal(self.max_cost, "max_cost")
        _require_optional_non_negative_int(self.max_runtime_seconds, "max_runtime_seconds")
        if self.deadline is not None and not isinstance(self.deadline, Instant):
            raise TypeError("deadline must be an Instant")
        _require_optional_non_negative_int(self.max_retries, "max_retries")
        _require_optional_non_negative_int(self.max_steps, "max_steps")
        _require_optional_non_negative_int(self.max_tool_calls, "max_tool_calls")


def _require_optional_non_negative_int(value: int | None, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _require_optional_non_negative_decimal(value: Decimal | None, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal")
    if value < Decimal("0"):
        raise ValueError(f"{field_name} must be >= 0")
