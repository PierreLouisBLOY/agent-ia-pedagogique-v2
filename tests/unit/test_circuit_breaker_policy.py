from __future__ import annotations

from datetime import timedelta

import pytest

from backend.agent_runtime.contracts import ErrorCategory
from backend.agent_runtime.recovery import (
    CircuitBreakerError,
    CircuitBreakerErrorCode,
    CircuitBreakerPolicy,
    CircuitBreakerPolicyConfig,
    CircuitBreakerState,
    CircuitBreakerStatus,
    CircuitCheckDisposition,
    CircuitCheckRequest,
    CircuitProbeLease,
)
from backend.shared_kernel.time import Instant
from tests.support.circuit_breaker_fakes import (
    CONFIG,
    NOW,
    make_closed_state,
    make_error,
    make_key,
    make_open_state,
)

POLICY = CircuitBreakerPolicy()


def _request(*, run_id: str = "run-circuit", attempt: int = 1) -> CircuitCheckRequest:
    return CircuitCheckRequest(
        key=make_key(),
        run_id=run_id,
        step_id="step-circuit",
        attempt=attempt,
    )


def _half_open() -> CircuitBreakerState:
    opened = make_open_state()
    boundary = opened.open_until
    assert boundary is not None
    return POLICY.prepare_half_open_lease(
        state=opened,
        request=_request(),
        now=boundary,
        config=CONFIG,
    )


@pytest.mark.parametrize(
    "category",
    [ErrorCategory.TRANSIENT, ErrorCategory.PROVIDER, ErrorCategory.TOOL],
)
def test_only_technical_categories_are_counted(category: ErrorCategory) -> None:
    assert POLICY.classify_error(make_error(category))


@pytest.mark.parametrize(
    "category",
    [
        ErrorCategory.DOMAIN,
        ErrorCategory.PERMISSION,
        ErrorCategory.GATE,
        ErrorCategory.BUDGET,
        ErrorCategory.CANCELLED,
        ErrorCategory.VALIDATION,
        ErrorCategory.QUALITY,
        ErrorCategory.CONFLICT,
        ErrorCategory.UNKNOWN,
    ],
)
def test_non_technical_categories_are_not_counted(category: ErrorCategory) -> None:
    assert not POLICY.classify_error(make_error(category))


def test_closed_check_does_not_mutate_state() -> None:
    state = make_closed_state()

    disposition = POLICY.classify_check(state=state, now=NOW)

    assert disposition is CircuitCheckDisposition.CLOSED
    assert state == make_closed_state()


def test_failure_window_is_pruned_and_history_is_bounded() -> None:
    old = Instant(NOW.value - timedelta(seconds=61))
    recent = Instant(NOW.value - timedelta(seconds=20))
    state = make_closed_state(failures=(old, recent))

    replacement = POLICY.prepare_failure(
        state=state,
        error=make_error(),
        now=NOW,
        config=CONFIG,
    )

    assert replacement.status is CircuitBreakerStatus.CLOSED
    assert replacement.recent_failure_times == (recent, NOW)
    assert len(replacement.recent_failure_times) <= CONFIG.failure_threshold


def test_threshold_failure_opens_circuit() -> None:
    first = Instant(NOW.value - timedelta(seconds=20))
    second = Instant(NOW.value - timedelta(seconds=10))
    state = make_closed_state(failures=(first, second))

    replacement = POLICY.prepare_failure(
        state=state,
        error=make_error(),
        now=NOW,
        config=CONFIG,
    )

    assert replacement.status is CircuitBreakerStatus.OPEN
    assert replacement.opened_at == NOW
    assert replacement.open_until == Instant(
        NOW.value + timedelta(seconds=CONFIG.open_duration_seconds)
    )
    assert replacement.half_open_lease is None


def test_non_counted_failure_never_opens_circuit() -> None:
    state = make_closed_state(
        failures=(
            Instant(NOW.value - timedelta(seconds=10)),
            Instant(NOW.value - timedelta(seconds=5)),
        )
    )

    replacement = POLICY.prepare_failure(
        state=state,
        error=make_error(ErrorCategory.PERMISSION),
        now=NOW,
        config=CONFIG,
    )

    assert replacement.status is CircuitBreakerStatus.CLOSED
    assert replacement.recent_failure_times == state.recent_failure_times


def test_open_is_blocked_before_and_eligible_at_exact_boundary() -> None:
    state = make_open_state()
    boundary = state.open_until
    assert boundary is not None

    before = POLICY.classify_check(
        state=state,
        now=Instant(boundary.value - timedelta(microseconds=1)),
    )
    at_boundary = POLICY.classify_check(state=state, now=boundary)

    assert before is CircuitCheckDisposition.OPEN_BLOCKED
    assert at_boundary is CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED
    assert state.status is CircuitBreakerStatus.OPEN


def test_first_half_open_lease_is_atomic_transition_candidate() -> None:
    half_open = _half_open()

    assert half_open.status is CircuitBreakerStatus.HALF_OPEN
    assert half_open.version == 2
    assert half_open.half_open_lease is not None
    assert half_open.half_open_lease.state_version == half_open.version
    assert (
        POLICY.classify_check(state=half_open, now=half_open.updated_at)
        is CircuitCheckDisposition.HALF_OPEN_BUSY
    )


def test_expired_lease_is_not_success_and_can_be_replaced() -> None:
    half_open = _half_open()
    lease = half_open.half_open_lease
    assert lease is not None

    replacement = POLICY.prepare_lease_expiry(
        state=half_open,
        request=_request(run_id="run-next", attempt=2),
        now=lease.expires_at,
        config=CONFIG,
    )

    assert replacement.status is CircuitBreakerStatus.HALF_OPEN
    assert replacement.half_open_successes == 0
    assert replacement.half_open_lease is not None
    assert replacement.half_open_lease.lease_id != lease.lease_id


def test_half_open_success_threshold_closes_sequentially() -> None:
    first_probe = _half_open()
    first_lease = first_probe.half_open_lease
    assert first_lease is not None
    after_first = POLICY.prepare_success(
        state=first_probe,
        lease=first_lease,
        now=Instant(first_probe.updated_at.value + timedelta(seconds=1)),
        config=CONFIG,
    )
    assert after_first.status is CircuitBreakerStatus.HALF_OPEN
    assert after_first.half_open_successes == 1
    assert after_first.half_open_lease is None

    second_probe = POLICY.prepare_half_open_lease(
        state=after_first,
        request=_request(attempt=2),
        now=Instant(after_first.updated_at.value + timedelta(seconds=1)),
        config=CONFIG,
    )
    second_lease = second_probe.half_open_lease
    assert second_lease is not None
    closed = POLICY.prepare_success(
        state=second_probe,
        lease=second_lease,
        now=Instant(second_probe.updated_at.value + timedelta(seconds=1)),
        config=CONFIG,
    )

    assert closed.status is CircuitBreakerStatus.CLOSED
    assert closed.recent_failure_times == ()
    assert closed.half_open_successes == 0
    assert closed.half_open_lease is None


def test_counted_half_open_failure_reopens_immediately() -> None:
    half_open = _half_open()
    lease = half_open.half_open_lease
    assert lease is not None
    observed = Instant(half_open.updated_at.value + timedelta(seconds=1))

    reopened = POLICY.prepare_failure(
        state=half_open,
        error=make_error(),
        lease=lease,
        now=observed,
        config=CONFIG,
    )

    assert reopened.status is CircuitBreakerStatus.OPEN
    assert reopened.opened_at == observed
    assert reopened.half_open_lease is None
    assert reopened.half_open_successes == 0


def test_non_counted_half_open_failure_releases_without_reopening() -> None:
    half_open = _half_open()
    lease = half_open.half_open_lease
    assert lease is not None

    replacement = POLICY.prepare_failure(
        state=half_open,
        error=make_error(ErrorCategory.DOMAIN),
        lease=lease,
        now=Instant(half_open.updated_at.value + timedelta(seconds=1)),
        config=CONFIG,
    )

    assert replacement.status is CircuitBreakerStatus.HALF_OPEN
    assert replacement.half_open_lease is None


def test_wrong_expired_or_mismatched_lease_is_rejected() -> None:
    half_open = _half_open()
    lease = half_open.half_open_lease
    assert lease is not None
    other = CircuitProbeLease.create(
        circuit_id=lease.circuit_id,
        state_version=lease.state_version,
        run_id="another-run",
        step_id=lease.step_id,
        attempt=lease.attempt,
        acquired_at=lease.acquired_at,
        expires_at=lease.expires_at,
    )

    with pytest.raises(CircuitBreakerError) as wrong:
        POLICY.prepare_success(
            state=half_open,
            lease=other,
            now=half_open.updated_at,
            config=CONFIG,
        )
    assert wrong.value.code is CircuitBreakerErrorCode.LEASE_MISMATCH

    with pytest.raises(CircuitBreakerError) as expired:
        POLICY.prepare_success(
            state=half_open,
            lease=lease,
            now=lease.expires_at,
            config=CONFIG,
        )
    assert expired.value.code is CircuitBreakerErrorCode.LEASE_EXPIRED

    with pytest.raises(CircuitBreakerError) as mismatch:
        POLICY.prepare_failure(
            state=half_open,
            error=make_error(step_id="wrong-step"),
            lease=lease,
            now=half_open.updated_at,
            config=CONFIG,
        )
    assert mismatch.value.code is CircuitBreakerErrorCode.OUTCOME_MISMATCH

    with pytest.raises(CircuitBreakerError) as wrong_attempt:
        POLICY.prepare_failure(
            state=half_open,
            error=make_error(attempt=2),
            lease=lease,
            now=half_open.updated_at,
            config=CONFIG,
        )
    assert wrong_attempt.value.code is CircuitBreakerErrorCode.OUTCOME_MISMATCH


def test_lease_cannot_be_reused_after_close_and_reopen() -> None:
    one_success = CircuitBreakerPolicyConfig(
        failure_threshold=1,
        failure_window_seconds=60,
        open_duration_seconds=30,
        half_open_lease_seconds=10,
        half_open_success_threshold=1,
    )
    first_probe = _half_open()
    old_lease = first_probe.half_open_lease
    assert old_lease is not None
    closed = POLICY.prepare_success(
        state=first_probe,
        lease=old_lease,
        now=Instant(first_probe.updated_at.value + timedelta(seconds=1)),
        config=one_success,
    )
    reopened = POLICY.prepare_failure(
        state=closed,
        error=make_error(),
        now=Instant(closed.updated_at.value + timedelta(seconds=1)),
        config=one_success,
    )
    boundary = reopened.open_until
    assert boundary is not None
    second_probe = POLICY.prepare_half_open_lease(
        state=reopened,
        request=_request(attempt=2),
        now=boundary,
        config=one_success,
    )

    with pytest.raises(CircuitBreakerError) as raised:
        POLICY.prepare_success(
            state=second_probe,
            lease=old_lease,
            now=boundary,
            config=one_success,
        )
    assert raised.value.code is CircuitBreakerErrorCode.LEASE_MISMATCH
