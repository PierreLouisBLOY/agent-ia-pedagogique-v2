from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from backend.agent_runtime.observability.delivery_model import (
    DeliveryOverflowPolicy,
)

MAX_BUFFER_ITEMS: Final = 4_096
MAX_BUFFER_BYTES: Final = 64 * 1_024 * 1_024
MAX_FLUSH_ITEMS: Final = 1_024


@dataclass(frozen=True, slots=True)
class ObservabilityDeliveryPolicy:
    max_items: int = 256
    max_bytes: int = 4 * 1_024 * 1_024
    max_flush_items: int = 256
    overflow_policy: DeliveryOverflowPolicy = DeliveryOverflowPolicy.DROP_NEWEST
    enabled: bool = True

    def __post_init__(self) -> None:
        _require_bounded_positive_int(
            self.max_items,
            "max_items",
            maximum=MAX_BUFFER_ITEMS,
        )
        _require_bounded_positive_int(
            self.max_bytes,
            "max_bytes",
            maximum=MAX_BUFFER_BYTES,
        )
        _require_bounded_positive_int(
            self.max_flush_items,
            "max_flush_items",
            maximum=MAX_FLUSH_ITEMS,
        )
        if not isinstance(self.overflow_policy, DeliveryOverflowPolicy):
            raise TypeError("overflow_policy must be a DeliveryOverflowPolicy")
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be a bool")


def _require_bounded_positive_int(
    value: int,
    field_name: str,
    *,
    maximum: int,
) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if not 1 <= value <= maximum:
        raise ValueError(f"{field_name} must be between 1 and {maximum}")


BASELINE_OBSERVABILITY_DELIVERY_POLICY: Final = ObservabilityDeliveryPolicy()
