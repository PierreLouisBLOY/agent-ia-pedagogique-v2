import socket
import threading
import time
from contextlib import contextmanager

import pytest

from backend.infrastructure.composition.factories.local_browser import build_local_read15
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.support.conversation_fakes import http_call
from tests.support.conversation_synthetic import synthetic_target
from tests.support.r3_fakes import ImmediateJobs, command, seed


@contextmanager
def running(tmp_path, *, enabled=True):
    target = synthetic_target(tmp_path / "new-synthetic-only")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    jobs = ImmediateJobs()
    composition = build_local_read15(LocalBrowserHttpConfiguration(port=port), target,
        enable_conversation=True, enable_review_modify=enabled, r3_jobs=jobs if enabled else None)
    prod = seed(composition.conversation)
    thread = threading.Thread(target=composition.serve_forever, daemon=True)
    thread.start()
    assert composition.server._running.wait(2)
    try:
        yield composition, prod, jobs
    finally:
        composition.close()
        thread.join(3)
        assert not thread.is_alive()


def post(composition, prod, operation, **kwargs):
    cmd = command(composition.conversation, composition.r3, operation, prod)
    return http_call(composition, "/api/v2/conversation/" + operation,
                     body=as_plain(cmd.body), **kwargs), cmd


def collect(composition, op):
    until = time.monotonic() + 5
    while time.monotonic() < until:
        status, _, response = http_call(composition, "/api/v2/conversation/operations/" + op)
        assert status == 200
        if response["data"]["state"] != "RUNNING":
            return response["data"]
        time.sleep(.03)
    raise AssertionError("HTTP_JOB_NOT_COLLECTED")


def test_http_full_flow_review_v1_cap_a01_then_new_unreviewed_v2(tmp_path):
    with running(tmp_path) as (composition, prod, jobs):
        base = "/api/v2/productions/" + prod.production_ref + "/versions/"
        initial = http_call(composition, base + prod.version_ref)[2]["data"]
        prepared, cmd = post(composition, prod, "assessment-preparations")
        assert prepared[0] == 202 and prepared[1]["Cache-Control"] == "no-store"
        result = collect(composition, prepared[2]["data"]["operation_ref"])
        assert result["state"] == "SUCCEEDED"
        assert http_call(composition, "/api/v2/conversation/assessment-preparations",
                         body=as_plain(cmd.body))[2]["data"]["operation_ref"] == result["operation_ref"]
        review, _ = post(composition, prod, "reviews")
        assert collect(composition, review[2]["data"]["operation_ref"])["state"] == "SUCCEEDED"
        report = http_call(composition, "/api/v2/conversation/reviews/" + review[2]["data"]["review_ref"])
        assert report[0] == 200 and report[2]["data"]["version_ref"] == prod.version_ref
        validation, _ = post(composition, prod, "validations")
        assert validation[0] == 200
        assert len(validation[2]["data"]["validation"]["checks"]) == 16
        changed, _ = post(composition, prod, "modifications")
        final = collect(composition, changed[2]["data"]["operation_ref"])
        assert final["state"] == "SUCCEEDED"
        v2 = http_call(composition, base + final["version_ref"] + "/assessment")[2]["data"]
        assert v2["review_status"] == "REVIEW_NOT_RUN" and v2["reviews"] == []
        assert v2["validation_state"] == "CANDIDATE"
        assert http_call(composition, base + prod.version_ref)[2]["data"] == initial
        assert len(jobs.generation.calls) == 2 and len(jobs.reviewer.calls) == 1


@pytest.mark.parametrize("headers", ({"Origin": "http://other.invalid"},
    {"X-R2-Nonce": "wrong"}, {"Host": "localhost:8123"}, {"Sec-Fetch-Site": "cross-site"},
    {"X-Local-Intent": "wrong"}))
def test_r3_security_before_dispatch_and_mutation(tmp_path, headers):
    with running(tmp_path) as (composition, prod, jobs):
        revision = composition.conversation.service.snapshot()["revision"]
        response, _ = post(composition, prod, "assessment-preparations", headers=headers)
        assert response[0] == 403 and jobs.requests == []
        assert composition.conversation.service.snapshot()["revision"] == revision


def test_r3_disabled_and_unknown_version_are_safe(tmp_path):
    with running(tmp_path, enabled=False) as (composition, prod, jobs):
        path = "/api/v2/productions/" + prod.production_ref + "/versions/" + prod.version_ref + "/assessment"
        assert http_call(composition, path)[0] == 404 and jobs.requests == []
