from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    RecommendedAction,
)
from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)
from backend.agent_runtime.recovery import (
    BudgetCheckDisposition,
    BudgetState,
    DeterministicBackoffPolicy,
    EffectLedgerRecord,
    ReplayGuard,
    ReplayGuardDecision,
    RetryDisposition,
    RetryPolicy,
    RetryPolicyRequest,
    RetryReasonCode,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.reconciliation_fakes import make_finalized_record
from tests.support.retry_replay_fakes import (
    DEADLINE,
    NOW,
    make_budget_check,
    make_budget_state,
    make_error,
    make_none_record,
    make_preconditions,
    make_replay_decision,
)


def _request(
    *,
    record: EffectLedgerRecord | None = None,
    error: ErrorEnvelope | None = None,
    budget: BudgetState | None = None,
    budget_disposition: BudgetCheckDisposition = BudgetCheckDisposition.WITHIN_LIMIT,
    replay: ReplayGuardDecision | None = None,
    now: Instant = NOW,
    runtime_policy: AgentRuntimePolicy = BASELINE_AGENT_RUNTIME_POLICY,
) -> RetryPolicyRequest:
    target = record or make_none_record()
    return RetryPolicyRequest(
        error=error or make_error(attempt=target.attempt),
        record=target,
        budget_state=budget or make_budget_state(),
        budget_check=make_budget_check(budget_disposition),
        replay_decision=replay or make_replay_decision(target),
        now=now,
        runtime_policy=runtime_policy,
    )


def _record(effect: EffectState) -> EffectLedgerRecord:
    return make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=effect,
        created_at=Instant(NOW.value - timedelta(minutes=2)),
        expires_at=Instant(NOW.value - timedelta(minutes=1)),
        finalized_at=Instant(NOW.value - timedelta(seconds=30)),
    )


@pytest.mark.parametrize(
    "category",
    [ErrorCategory.TRANSIENT, ErrorCategory.PROVIDER, ErrorCategory.TOOL],
)
def test_safe_none_effect_retries_for_allowed_categories(
    category: ErrorCategory,
) -> None:
    decision = RetryPolicy().decide(
        _request(error=make_error(category=category))
    )

    assert decision.disposition is RetryDisposition.RETRY
    assert decision.reason_codes == (RetryReasonCode.SAFE_RETRY,)
    assert decision.next_attempt == 2
    assert decision.schedule is not None
    assert decision.schedule.retry_ordinal == 1
    assert decision.not_before == Instant(NOW.value + timedelta(seconds=1))
    assert decision.requires_circuit_check is True


@pytest.mark.parametrize(
    "category",
    [
        ErrorCategory.DOMAIN,
        ErrorCategory.PERMISSION,
        ErrorCategory.GATE,
        ErrorCategory.BUDGET,
        ErrorCategory.CANCELLED,
    ],
)
def test_firm_categories_never_retry_even_when_marked_retryable(
    category: ErrorCategory,
) -> None:
    decision = RetryPolicy().decide(
        _request(error=make_error(category=category, retryable=True))
    )

    assert decision.disposition is RetryDisposition.STOP
    assert decision.schedule is None


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (RecommendedAction.REPLAN, RetryDisposition.REPLAN),
        (RecommendedAction.ESCALATE, RetryDisposition.ESCALATE),
        (RecommendedAction.STOP, RetryDisposition.STOP),
        (RecommendedAction.INSPECT, RetryDisposition.NO_RETRY),
    ],
)
def test_recommended_action_is_respected(
    action: RecommendedAction,
    expected: RetryDisposition,
) -> None:
    assert (
        RetryPolicy().decide(_request(error=make_error(action=action))).disposition
        is expected
    )


@pytest.mark.parametrize(
    ("effect", "expected"),
    [
        (EffectState.UNKNOWN, RetryDisposition.RECONCILE_FIRST),
        (EffectState.PARTIAL, RetryDisposition.STOP),
        (EffectState.COMMITTED, RetryDisposition.NO_RETRY),
    ],
)
def test_non_none_effects_never_retry(
    effect: EffectState,
    expected: RetryDisposition,
) -> None:
    record = _record(effect)
    replay = ReplayGuard().evaluate(
        record=record,
        preconditions=make_preconditions(identity=record.identity),
    )

    decision = RetryPolicy().decide(_request(record=record, replay=replay))

    assert decision.disposition is expected
    assert decision.schedule is None


def test_non_retryable_error_is_refused() -> None:
    decision = RetryPolicy().decide(
        _request(error=make_error(retryable=False))
    )

    assert decision.disposition is RetryDisposition.NO_RETRY
    assert decision.reason_codes == (RetryReasonCode.ERROR_NOT_RETRYABLE,)


@pytest.mark.parametrize(
    "budget_disposition",
    [
        BudgetCheckDisposition.LIMIT_EXCEEDED,
        BudgetCheckDisposition.USAGE_UNKNOWN,
    ],
)
def test_budget_failure_is_fail_closed(
    budget_disposition: BudgetCheckDisposition,
) -> None:
    decision = RetryPolicy().decide(
        _request(budget_disposition=budget_disposition)
    )

    assert decision.disposition is RetryDisposition.NO_RETRY


@pytest.mark.parametrize(
    ("budget", "runtime_policy"),
    [
        (make_budget_state(max_retries_per_envelope=0), AgentRuntimePolicy()),
        (make_budget_state(max_retries_per_step=0), AgentRuntimePolicy()),
        (make_budget_state(), AgentRuntimePolicy(max_retries_per_step=0)),
    ],
)
def test_each_retry_limit_scope_is_enforced(
    budget: BudgetState,
    runtime_policy: AgentRuntimePolicy,
) -> None:
    decision = RetryPolicy().decide(
        _request(budget=budget, runtime_policy=runtime_policy)
    )

    assert decision.disposition is RetryDisposition.NO_RETRY
    assert decision.reason_codes == (RetryReasonCode.RETRY_LIMIT_REACHED,)


def test_attempt_and_step_coordinates_are_exact() -> None:
    for error in (
        make_error(attempt=2),
        make_error(step_id="another-step"),
    ):
        decision = RetryPolicy().decide(_request(error=error))
        assert decision.disposition is RetryDisposition.NO_RETRY
        assert decision.reason_codes == (RetryReasonCode.ATTEMPT_MISMATCH,)


def test_replay_decision_must_match_current_record_version() -> None:
    replay = replace(make_replay_decision(), record_version=999)

    decision = RetryPolicy().decide(_request(replay=replay))

    assert decision.reason_codes == (RetryReasonCode.INVALID_REPLAY_CONTEXT,)


def test_expired_deadline_stops_and_backoff_cannot_cross_deadline() -> None:
    expired = make_budget_state(deadline=NOW)
    too_short = make_budget_state(
        deadline=Instant(NOW.value + timedelta(seconds=5))
    )
    policy = RetryPolicy(
        DeterministicBackoffPolicy(
            initial_delay_seconds=10,
            multiplier=2,
            max_delay_seconds=60,
        )
    )

    expired_decision = RetryPolicy().decide(_request(budget=expired))
    crossing_decision = policy.decide(_request(budget=too_short))

    assert expired_decision.disposition is RetryDisposition.STOP
    assert expired_decision.reason_codes == (RetryReasonCode.DEADLINE_EXPIRED,)
    assert crossing_decision.disposition is RetryDisposition.NO_RETRY
    assert crossing_decision.reason_codes == (
        RetryReasonCode.BACKOFF_EXCEEDS_DEADLINE,
    )


def test_backoff_equal_to_deadline_is_allowed() -> None:
    budget = make_budget_state(
        deadline=Instant(NOW.value + timedelta(seconds=5))
    )
    policy = RetryPolicy(
        DeterministicBackoffPolicy(
            initial_delay_seconds=5,
            multiplier=2,
            max_delay_seconds=60,
        )
    )

    decision = policy.decide(_request(budget=budget))

    assert decision.disposition is RetryDisposition.RETRY
    assert decision.not_before == budget.limits.deadline


def test_retry_decision_does_not_mutate_budget_state() -> None:
    budget = make_budget_state(deadline=DEADLINE)
    before = budget

    RetryPolicy().decide(_request(budget=budget))

    assert budget == before
