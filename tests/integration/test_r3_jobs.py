import time

import pytest

from backend.adapters.outbound.system.r3_job import InjectedR3Job, UnapprovedR3Job
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3JobRequest
from tests.support.r3_fakes import echo_worker, sleeping_worker
from tests.support.r3_synthetic import bundle


def request():
    return R3JobRequest("op:" + "a" * 32, "reviews", bundle=bundle(), dimensions=("REV-ACC",))


def collect(job):
    until = time.monotonic() + 8
    while time.monotonic() < until:
        result = job.poll()
        if result:
            return result
        time.sleep(.02)
    raise AssertionError("R3_CHILD_NOT_COLLECTED")


def test_real_synthetic_child_one_result_no_repeat():
    job = InjectedR3Job(echo_worker)
    try:
        job.start(request())
        child = job._process
        result = collect(job)
        assert result.state == "SUCCEEDED" and result.payload["synthetic"] is True
        assert not child.is_alive() and job.poll() is None
        with pytest.raises(ValueError):
            job.start(request())
    finally:
        job.close()


def test_timeout_and_close_leave_no_child_or_retry():
    for close in (False, True):
        job = InjectedR3Job(sleeping_worker, timeout=.15)
        job.start(request())
        child = job._process
        started = time.monotonic()
        if close:
            job.close()
        else:
            assert collect(job).state == "UNKNOWN"
        assert not child.is_alive() and time.monotonic() - started < 5
        with pytest.raises(ValueError):
            job.start(request())
        job.close()


def test_restart_default_cannot_reuse_any_prior_job():
    with pytest.raises(ValueError, match="R3_NOT_AUTHORIZED"):
        UnapprovedR3Job().start(request())


def test_worker_failure_and_oversized_output_are_terminal_without_private_text():
    from tests.support.r3_fakes import failing_worker, oversized_worker
    for handler in (failing_worker, oversized_worker):
        job = InjectedR3Job(handler)
        try:
            job.start(request())
            result = collect(job)
            assert result.state != "SUCCEEDED" and result.payload is None
            assert "SYNTHETIC_PRIVATE_MARKER" not in str(result)
            with pytest.raises(ValueError):
                job.start(request())
        finally:
            job.close()
