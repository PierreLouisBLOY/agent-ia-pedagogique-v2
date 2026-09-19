"""Closed, bounded polling: deterministic clock, no network or real sleep."""
from types import SimpleNamespace

import pytest

from tests.support import conversation_fakes as harness


class Clock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        assert seconds > 0
        self.sleeps.append(seconds)
        self.value += seconds


@pytest.fixture
def polling(monkeypatch):
    clock = Clock()
    calls = []
    response = {"state": "IN_PROGRESS", "status": 200, "latency": 0.0}

    def http_call(composition, *, timeout):
        calls.append(timeout)
        clock.value += response["latency"]
        state = response["state"]
        if callable(state):
            state = state(clock.value)
        active = None if state is None else {"generation_id": "gen:synthetic", "state": state}
        return response["status"], {}, {"data": {"conversation": {
            "active_generation": active, "private_text": "DO_NOT_LOG_SYNTHETIC_PAYLOAD"}}}

    monkeypatch.setattr(harness, "time", clock)
    monkeypatch.setattr(harness, "http_call", http_call)
    return clock, calls, response


@pytest.mark.parametrize("state", ["CANDIDATE_READY", "FAILED_OUTPUT", "UNKNOWN"])
def test_wait_returns_exact_terminal_state_without_promoting_failures(polling, state):
    clock, calls, response = polling
    response["state"] = state
    view = harness.wait_terminal(None)
    assert view["active_generation"]["state"] == state
    assert calls == [7] and clock.sleeps == []


def test_wait_observes_worker_after_old_12_second_harness_cutoff(polling):
    clock, calls, response = polling
    response["state"] = lambda now: "CANDIDATE_READY" if now >= 13 else "IN_PROGRESS"
    assert harness.wait_terminal(None)["active_generation"]["state"] == "CANDIDATE_READY"
    assert 13 <= clock.value < 13.1 and all(0 < bound <= 7 for bound in calls)


@pytest.mark.parametrize("state", ["IN_PROGRESS", None])
def test_wait_expires_at_default_bound_and_diagnostic_has_no_payload(polling, state):
    clock, calls, response = polling
    response["state"] = state
    with pytest.raises(AssertionError, match="synthetic worker did not terminate within 125s") as error:
        harness.wait_terminal(None)
    assert clock.value == 125
    assert calls and all(0 < bound <= 7 for bound in calls)
    assert "DO_NOT_LOG" not in str(error.value) and "gen:synthetic" not in str(error.value)
    assert f"state={state or 'NO_ACTIVE_GENERATION'}" in str(error.value)


def test_wait_clamps_http_and_sleep_to_remaining_budget(polling):
    clock, calls, _ = polling
    with pytest.raises(AssertionError, match="did not terminate"):
        harness.wait_terminal(None, timeout=.11)
    assert calls == pytest.approx([.11, .06, .01])
    assert clock.sleeps == pytest.approx([.05, .05, .01])
    assert clock.value == .11


@pytest.mark.parametrize("latency", [.1, .11])
def test_wait_rejects_terminal_response_at_or_after_deadline(polling, latency):
    clock, calls, response = polling
    response.update(state="CANDIDATE_READY", latency=latency)
    with pytest.raises(AssertionError, match="did not terminate"):
        harness.wait_terminal(None, timeout=.1)
    assert calls == [.1] and not clock.sleeps


@pytest.mark.parametrize("timeout", [0, -1, 126, float("inf"), float("nan"), True, "125", None])
def test_wait_rejects_invalid_or_unbounded_timeout_before_http(polling, timeout):
    _, calls, _ = polling
    with pytest.raises(ValueError, match="INVALID_SYNTHETIC_WAIT_TIMEOUT"):
        harness.wait_terminal(None, timeout=timeout)
    assert calls == []


def test_wait_rejects_unknown_state_without_logging_it(polling):
    _, calls, response = polling
    response["state"] = "PRIVATE_UNKNOWN_STATE"
    with pytest.raises(AssertionError, match="^INVALID_SYNTHETIC_GENERATION_STATE$"):
        harness.wait_terminal(None)
    assert len(calls) == 1


def test_wait_does_not_retry_failed_http(polling):
    _, calls, response = polling
    response["status"] = 503
    with pytest.raises(AssertionError):
        harness.wait_terminal(None)
    assert len(calls) == 1


def test_wait_does_not_retry_transport_exception(polling, monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(kwargs)
        raise TimeoutError("synthetic transport timeout")

    monkeypatch.setattr(harness, "http_call", fail)
    with pytest.raises(TimeoutError):
        harness.wait_terminal(None)
    assert len(calls) == 1


def test_http_call_passes_remaining_timeout_and_always_closes(monkeypatch):
    calls = []

    class Connection:
        def __init__(self, host, port, *, timeout):
            calls.append((host, port, timeout))

        def request(self, *args, **kwargs):
            raise TimeoutError("synthetic transport timeout")

        def close(self):
            calls.append("CLOSED")

    composition = SimpleNamespace(server=SimpleNamespace(service=SimpleNamespace(
        configuration=SimpleNamespace(port=12345))))
    monkeypatch.setattr(harness.http.client, "HTTPConnection", Connection)
    with pytest.raises(TimeoutError):
        harness.http_call(composition, timeout=.125)
    assert calls == [("127.0.0.1", 12345, .125), "CLOSED"]


@pytest.fixture
def collection(monkeypatch):
    from tests.integration import test_conversation_job_lifecycle as lifecycle
    clock = Clock()
    monkeypatch.setattr(lifecycle, "time", clock)
    return lifecycle.collect, clock


@pytest.mark.parametrize("ready_at", [9, 16])
def test_collect_observes_job_after_old_startup_cutoffs(collection, ready_at):
    collect, clock = collection
    expected = object()
    job = SimpleNamespace(poll=lambda: expected if clock.value >= ready_at else None)
    assert collect(job) is expected and ready_at <= clock.value < ready_at + .1


def test_collect_default_timeout_is_finite_and_no_result_is_synthesized(collection):
    collect, clock = collection
    with pytest.raises(AssertionError, match="bounded child not collected"):
        collect(SimpleNamespace(poll=lambda: None))
    assert clock.value == 125


def test_collect_preserves_short_explicit_timeout(collection):
    collect, clock = collection
    with pytest.raises(AssertionError, match="bounded child not collected"):
        collect(SimpleNamespace(poll=lambda: None), timeout=.05)
    assert clock.value == .05 and clock.sleeps == pytest.approx([.02, .02, .01])


@pytest.mark.parametrize("timeout", [0, -1, 126, float("inf"), float("nan"), True, "125", None])
def test_collect_rejects_invalid_or_unbounded_wait_before_poll(collection, timeout):
    collect, _ = collection
    calls = []
    with pytest.raises(ValueError, match="INVALID_SYNTHETIC_WAIT_TIMEOUT"):
        collect(SimpleNamespace(poll=lambda: calls.append(True)), timeout=timeout)
    assert not calls


@pytest.mark.parametrize("latency", [.1, .11])
def test_collect_rejects_result_at_or_after_deadline(collection, latency):
    collect, clock = collection

    def poll():
        clock.value += latency
        return object()

    with pytest.raises(AssertionError, match="bounded child not collected"):
        collect(SimpleNamespace(poll=poll), timeout=.1)
    assert not clock.sleeps


def test_collect_does_not_retry_poll_exception(collection):
    collect, _ = collection
    calls = []

    def poll():
        calls.append(True)
        raise RuntimeError("synthetic failure")

    with pytest.raises(RuntimeError, match="synthetic failure"):
        collect(SimpleNamespace(poll=poll))
    assert calls == [True]
