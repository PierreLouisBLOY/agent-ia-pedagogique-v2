from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class RetrySchedule:
    """A data-only retry schedule; it never waits or executes work."""

    retry_ordinal: int
    delay_seconds: int
    not_before: Instant

    def __post_init__(self) -> None:
        _require_positive_int(self.retry_ordinal, "retry_ordinal")
        _require_non_negative_int(self.delay_seconds, "delay_seconds")
        if not isinstance(self.not_before, Instant):
            raise TypeError("not_before must be an Instant")


@dataclass(frozen=True, slots=True)
class DeterministicBackoffPolicy:
    """Bounded exponential backoff without jitter, sleeping, or mutable state."""

    initial_delay_seconds: int = 1
    multiplier: int = 2
    max_delay_seconds: int = 60

    def __post_init__(self) -> None:
        _require_non_negative_int(
            self.initial_delay_seconds,
            "initial_delay_seconds",
        )
        _require_positive_int(self.multiplier, "multiplier")
        _require_non_negative_int(self.max_delay_seconds, "max_delay_seconds")
        if self.initial_delay_seconds > self.max_delay_seconds:
            raise ValueError(
                "initial_delay_seconds must be <= max_delay_seconds"
            )

    def schedule(self, *, retry_ordinal: int, now: Instant) -> RetrySchedule:
        _require_positive_int(retry_ordinal, "retry_ordinal")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")
        delay_seconds = self._bounded_delay(retry_ordinal)
        return RetrySchedule(
            retry_ordinal=retry_ordinal,
            delay_seconds=delay_seconds,
            not_before=Instant(now.value + timedelta(seconds=delay_seconds)),
        )

    def _bounded_delay(self, retry_ordinal: int) -> int:
        delay = self.initial_delay_seconds
        if delay == 0 or self.multiplier == 1:
            return delay
        for _ in range(retry_ordinal - 1):
            if delay > self.max_delay_seconds // self.multiplier:
                return self.max_delay_seconds
            delay *= self.multiplier
        return delay


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
