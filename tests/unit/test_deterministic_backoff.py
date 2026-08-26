from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.recovery import DeterministicBackoffPolicy
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 10, 0, tzinfo=UTC))


def test_exponential_schedule_is_deterministic_and_capped() -> None:
    policy = DeterministicBackoffPolicy(
        initial_delay_seconds=2,
        multiplier=3,
        max_delay_seconds=20,
    )

    schedules = tuple(
        policy.schedule(retry_ordinal=ordinal, now=NOW)
        for ordinal in range(1, 5)
    )

    assert tuple(item.delay_seconds for item in schedules) == (2, 6, 18, 20)
    assert tuple(item.not_before.value for item in schedules) == tuple(
        NOW.value + timedelta(seconds=delay) for delay in (2, 6, 18, 20)
    )
    assert policy.schedule(retry_ordinal=3, now=NOW) == schedules[2]


@pytest.mark.parametrize(
    "changes",
    [
        {"initial_delay_seconds": -1},
        {"multiplier": 0},
        {"max_delay_seconds": -1},
        {"initial_delay_seconds": 2, "max_delay_seconds": 1},
    ],
)
def test_invalid_configuration_is_rejected(changes: dict[str, int]) -> None:
    with pytest.raises((TypeError, ValueError)):
        DeterministicBackoffPolicy(**changes)


def test_retry_ordinal_starts_at_one() -> None:
    with pytest.raises(ValueError, match="retry_ordinal"):
        DeterministicBackoffPolicy().schedule(retry_ordinal=0, now=NOW)


def test_large_retry_ordinal_reaches_cap_without_large_exponentiation() -> None:
    schedule = DeterministicBackoffPolicy().schedule(
        retry_ordinal=1_000_000,
        now=NOW,
    )

    assert schedule.delay_seconds == 60
