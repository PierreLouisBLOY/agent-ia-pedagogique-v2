from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.recovery import (
    BudgetAccountingPolicy,
    BudgetState,
    BudgetStateError,
    BudgetStateErrorCode,
    BudgetStatePort,
    BudgetUsageDelta,
    EffectiveBudgetLimits,
)
from backend.shared_kernel.time import Instant
from tests.support.budget_state_fakes import InMemoryBudgetStatePort

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(seconds=1))


def _state() -> BudgetState:
    return BudgetState(
        run_id="run-1",
        version=1,
        limits=EffectiveBudgetLimits(max_tokens=100),
        created_at=NOW,
        updated_at=NOW,
    )


def test_budget_fake_satisfies_port_and_accepts_current_version() -> None:
    current = _state()
    port = InMemoryBudgetStatePort(current)
    replacement = BudgetAccountingPolicy().apply_delta(
        state=current,
        delta=BudgetUsageDelta(tokens=5),
        now=LATER,
    )

    assert isinstance(port, BudgetStatePort)
    assert port.compare_and_set(
        run_id="run-1",
        expected_version=1,
        replacement=replacement,
    ) == replacement
    assert port.get(run_id="run-1") == replacement


def test_budget_fake_rejects_stale_write() -> None:
    current = _state()
    port = InMemoryBudgetStatePort(current)
    replacement = BudgetAccountingPolicy().apply_delta(
        state=current,
        delta=BudgetUsageDelta(tokens=1),
        now=LATER,
    )
    port.compare_and_set(
        run_id="run-1",
        expected_version=1,
        replacement=replacement,
    )

    with pytest.raises(BudgetStateError) as raised:
        port.compare_and_set(
            run_id="run-1",
            expected_version=1,
            replacement=replacement,
        )
    assert raised.value.code is BudgetStateErrorCode.VERSION_CONFLICT


def test_concurrent_budget_cas_allows_exactly_one_writer() -> None:
    current = _state()
    port = InMemoryBudgetStatePort(current)
    policy = BudgetAccountingPolicy()
    candidates = tuple(
        policy.apply_delta(
            state=current,
            delta=BudgetUsageDelta(tokens=tokens),
            now=LATER,
        )
        for tokens in (1, 2)
    )

    def write(candidate: BudgetState) -> str:
        try:
            port.compare_and_set(
                run_id="run-1",
                expected_version=1,
                replacement=candidate,
            )
        except BudgetStateError as error:
            return error.code.value
        return "SAVED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(write, candidates))

    assert outcomes.count("SAVED") == 1
    assert outcomes.count(BudgetStateErrorCode.VERSION_CONFLICT.value) == 1
    assert port.get(run_id="run-1") is not None
    assert port.get(run_id="run-1").version == 2  # type: ignore[union-attr]


def test_budget_fake_rejects_unknown_run_without_creating_state() -> None:
    port = InMemoryBudgetStatePort(_state())
    replacement = BudgetAccountingPolicy().apply_delta(
        state=_state(),
        delta=BudgetUsageDelta(),
        now=LATER,
    )

    with pytest.raises(BudgetStateError) as raised:
        port.compare_and_set(
            run_id="missing-run",
            expected_version=1,
            replacement=replacement,
        )
    assert raised.value.code is BudgetStateErrorCode.INVALID_STATE
    assert port.get(run_id="missing-run") is None
