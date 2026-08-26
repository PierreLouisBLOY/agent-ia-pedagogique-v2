from __future__ import annotations

from dataclasses import fields

from backend.agent_runtime.recovery import (
    CircuitBreakerEngine,
    CircuitCheckDisposition,
    CircuitCheckRequest,
    RetryDecision,
    RetryDisposition,
    RetryPolicy,
    RetryPolicyRequest,
)
from tests.support.circuit_breaker_fakes import (
    CONFIG,
    InMemoryCircuitBreakerStore,
    make_key,
    make_open_state,
)
from tests.support.circuit_breaker_fakes import (
    NOW as CIRCUIT_NOW,
)
from tests.support.retry_replay_fakes import (
    NOW as RETRY_NOW,
)
from tests.support.retry_replay_fakes import (
    make_budget_check,
    make_budget_state,
    make_error,
    make_none_record,
    make_replay_decision,
)


def _retry_decision() -> RetryDecision:
    record = make_none_record()
    return RetryPolicy().decide(
        RetryPolicyRequest(
            error=make_error(),
            record=record,
            budget_state=make_budget_state(),
            budget_check=make_budget_check(),
            replay_decision=make_replay_decision(record),
            now=RETRY_NOW,
        )
    )


def _circuit_request() -> CircuitCheckRequest:
    return CircuitCheckRequest(
        key=make_key(),
        run_id="run-reconcile",
        step_id="step-reconcile",
        attempt=2,
    )


def test_retry_decision_remains_blocked_by_open_circuit() -> None:
    retry = _retry_decision()
    retry_before = retry
    opened = make_open_state()
    store = InMemoryCircuitBreakerStore(initial_states=(opened,))

    circuit = CircuitBreakerEngine(store=store, config=CONFIG).check(
        request=_circuit_request(),
        now=CIRCUIT_NOW,
    )

    assert retry.disposition is RetryDisposition.RETRY
    assert retry.requires_circuit_check is True
    assert circuit.disposition is CircuitCheckDisposition.OPEN_BLOCKED
    assert retry == retry_before
    assert store.cas_calls == 0


def test_closed_circuit_satisfies_only_circuit_stage_without_execution() -> None:
    retry = _retry_decision()
    store = InMemoryCircuitBreakerStore()
    engine = CircuitBreakerEngine(store=store, config=CONFIG)

    circuit = engine.check(request=_circuit_request(), now=CIRCUIT_NOW)

    assert retry.disposition is RetryDisposition.RETRY
    assert circuit.disposition is CircuitCheckDisposition.CLOSED
    assert {item.name for item in fields(CircuitBreakerEngine)} == {
        "store",
        "config",
        "policy",
    }
    assert store.create_calls == 0
    assert store.cas_calls == 0


def test_half_open_grants_one_probe_candidate_without_executing_it() -> None:
    opened = make_open_state()
    boundary = opened.open_until
    assert boundary is not None
    store = InMemoryCircuitBreakerStore(initial_states=(opened,))

    decision = CircuitBreakerEngine(store=store, config=CONFIG).check(
        request=_circuit_request(),
        now=boundary,
    )

    assert decision.disposition is CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED
    assert decision.lease is not None
    assert decision.lease.run_id == "run-reconcile"
    assert decision.lease.step_id == "step-reconcile"
    assert decision.lease.attempt == 2
    assert store.cas_calls == 1
