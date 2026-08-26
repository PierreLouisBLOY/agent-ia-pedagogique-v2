from __future__ import annotations

from datetime import timedelta

import pytest

from backend.agent_runtime.contracts import ErrorCategory
from backend.agent_runtime.recovery import (
    CircuitBreakerEngine,
    CircuitBreakerError,
    CircuitBreakerErrorCode,
    CircuitBreakerPolicyConfig,
    CircuitBreakerStatus,
    CircuitBreakerStorePort,
    CircuitCheckDisposition,
    CircuitCheckRequest,
    CircuitOutcomeRecord,
)
from backend.shared_kernel.time import Instant
from tests.support.circuit_breaker_fakes import (
    CONFIG,
    NOW,
    InMemoryCircuitBreakerStore,
    make_closed_state,
    make_error,
    make_key,
    make_open_state,
)


def _request(*, run_id: str = "run-circuit", attempt: int = 1) -> CircuitCheckRequest:
    return CircuitCheckRequest(
        key=make_key(),
        run_id=run_id,
        step_id="step-circuit",
        attempt=attempt,
    )


def test_absent_state_is_conceptually_closed_without_creation() -> None:
    store = InMemoryCircuitBreakerStore()
    engine = CircuitBreakerEngine(store=store, config=CONFIG)

    decision = engine.check(request=_request(), now=NOW)

    assert isinstance(store, CircuitBreakerStorePort)
    assert decision.disposition is CircuitCheckDisposition.CLOSED
    assert decision.state_version == 0
    assert store.get_calls == 1
    assert store.create_calls == 0
    assert store.cas_calls == 0


def test_first_counted_failure_creates_state_once() -> None:
    config = CircuitBreakerPolicyConfig(
        failure_threshold=1,
        failure_window_seconds=60,
        open_duration_seconds=30,
        half_open_lease_seconds=10,
        half_open_success_threshold=1,
    )
    store = InMemoryCircuitBreakerStore()
    engine = CircuitBreakerEngine(store=store, config=config)

    state = engine.record_outcome(
        outcome=CircuitOutcomeRecord(
            key=make_key(),
            expected_version=0,
            observed_at=NOW,
            error=make_error(),
        )
    )

    assert state is not None
    assert state.status is CircuitBreakerStatus.OPEN
    assert store.get_calls == 1
    assert store.create_calls == 1
    assert store.cas_calls == 0


def test_absent_success_or_non_counted_failure_creates_nothing() -> None:
    for error in (None, make_error(ErrorCategory.PERMISSION)):
        store = InMemoryCircuitBreakerStore()
        result = CircuitBreakerEngine(store=store, config=CONFIG).record_outcome(
            outcome=CircuitOutcomeRecord(
                key=make_key(),
                expected_version=0,
                observed_at=NOW,
                error=error,
            )
        )
        assert result is None
        assert store.create_calls == 0
        assert store.cas_calls == 0


def test_open_before_cooldown_is_blocked_without_cas() -> None:
    state = make_open_state()
    store = InMemoryCircuitBreakerStore(initial_states=(state,))

    decision = CircuitBreakerEngine(store=store, config=CONFIG).check(
        request=_request(),
        now=NOW,
    )

    assert decision.disposition is CircuitCheckDisposition.OPEN_BLOCKED
    assert decision.lease is None
    assert store.cas_calls == 0


def test_open_at_boundary_grants_and_persists_one_lease() -> None:
    state = make_open_state()
    boundary = state.open_until
    assert boundary is not None
    store = InMemoryCircuitBreakerStore(initial_states=(state,))

    decision = CircuitBreakerEngine(store=store, config=CONFIG).check(
        request=_request(),
        now=boundary,
    )

    persisted = store.get(circuit_id=state.circuit_id)
    assert decision.disposition is CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED
    assert decision.lease is not None
    assert persisted is not None
    assert persisted.half_open_lease == decision.lease
    assert store.cas_calls == 1


def test_active_half_open_lease_is_busy_without_write() -> None:
    opened = make_open_state()
    boundary = opened.open_until
    assert boundary is not None
    store = InMemoryCircuitBreakerStore(initial_states=(opened,))
    engine = CircuitBreakerEngine(store=store, config=CONFIG)
    granted = engine.check(request=_request(), now=boundary)
    assert granted.lease is not None
    writes = store.cas_calls

    busy = engine.check(
        request=_request(run_id="run-other"),
        now=Instant(boundary.value + timedelta(seconds=1)),
    )

    assert busy.disposition is CircuitCheckDisposition.HALF_OPEN_BUSY
    assert busy.lease is None
    assert store.cas_calls == writes


def test_expired_lease_can_be_replaced_but_is_not_recorded_as_success() -> None:
    opened = make_open_state()
    boundary = opened.open_until
    assert boundary is not None
    store = InMemoryCircuitBreakerStore(initial_states=(opened,))
    engine = CircuitBreakerEngine(store=store, config=CONFIG)
    first = engine.check(request=_request(), now=boundary)
    lease = first.lease
    assert lease is not None

    second = engine.check(
        request=_request(run_id="run-next", attempt=2),
        now=lease.expires_at,
    )

    persisted = store.get(circuit_id=opened.circuit_id)
    assert second.disposition is CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED
    assert second.lease is not None
    assert second.lease.lease_id != lease.lease_id
    assert persisted is not None
    assert persisted.half_open_successes == 0


def test_engine_records_half_open_success_through_exact_lease_cas() -> None:
    opened = make_open_state()
    boundary = opened.open_until
    assert boundary is not None
    store = InMemoryCircuitBreakerStore(initial_states=(opened,))
    engine = CircuitBreakerEngine(store=store, config=CONFIG)
    granted = engine.check(request=_request(), now=boundary)
    lease = granted.lease
    assert lease is not None

    state = engine.record_outcome(
        outcome=CircuitOutcomeRecord(
            key=make_key(),
            expected_version=granted.state_version,
            observed_at=Instant(boundary.value + timedelta(seconds=1)),
            lease=lease,
        )
    )

    assert state is not None
    assert state.status is CircuitBreakerStatus.HALF_OPEN
    assert state.half_open_successes == 1
    assert state.half_open_lease is None


def test_stale_outcome_fails_closed_without_internal_retry() -> None:
    state = make_closed_state()
    store = InMemoryCircuitBreakerStore(initial_states=(state,))

    with pytest.raises(CircuitBreakerError) as raised:
        CircuitBreakerEngine(store=store, config=CONFIG).record_outcome(
            outcome=CircuitOutcomeRecord(
                key=make_key(),
                expected_version=999,
                observed_at=NOW,
                error=make_error(),
            )
        )

    assert raised.value.code is CircuitBreakerErrorCode.VERSION_CONFLICT
    assert store.get_calls == 1
    assert store.cas_calls == 0
