from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from backend.agent_runtime.recovery import (
    CircuitBreakerEngine,
    CircuitBreakerError,
    CircuitBreakerErrorCode,
    CircuitCheckDisposition,
    CircuitCheckRequest,
)
from tests.support.circuit_breaker_fakes import (
    CONFIG,
    InMemoryCircuitBreakerStore,
    make_key,
    make_open_state,
)


def test_concurrent_open_checks_persist_exactly_one_half_open_lease() -> None:
    opened = make_open_state()
    boundary = opened.open_until
    assert boundary is not None
    barrier = Barrier(2)
    counter_lock = Lock()
    get_count = 0

    def synchronize_initial_reads() -> None:
        nonlocal get_count
        with counter_lock:
            get_count += 1
            should_wait = get_count <= 2
        if should_wait:
            barrier.wait()

    store = InMemoryCircuitBreakerStore(
        initial_states=(opened,),
        on_get=synchronize_initial_reads,
    )
    engine = CircuitBreakerEngine(store=store, config=CONFIG)
    requests = (
        CircuitCheckRequest(
            key=make_key(),
            run_id="run-a",
            step_id="step-circuit",
            attempt=1,
        ),
        CircuitCheckRequest(
            key=make_key(),
            run_id="run-b",
            step_id="step-circuit",
            attempt=1,
        ),
    )

    def check(request: CircuitCheckRequest) -> str:
        try:
            decision = engine.check(request=request, now=boundary)
        except CircuitBreakerError as error:
            return error.code.value
        return decision.disposition.value

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(check, requests))

    persisted = store.get(circuit_id=opened.circuit_id)
    assert outcomes.count(CircuitCheckDisposition.HALF_OPEN_PROBE_GRANTED.value) == 1
    assert outcomes.count(CircuitBreakerErrorCode.VERSION_CONFLICT.value) == 1
    assert persisted is not None
    assert persisted.half_open_lease is not None
    assert persisted.half_open_lease.run_id in {"run-a", "run-b"}
    assert store.cas_calls == 2
