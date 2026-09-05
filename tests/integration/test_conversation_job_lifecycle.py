import json
import time

import pytest

from backend.adapters.outbound.system.conversation_job import decode_frame, encode_frame
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from tests.support.conversation_fakes import process_job
from tests.unit.test_conversation_generation import draft_request


def collect(job, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = job.poll()
        if result is not None:
            return result
        time.sleep(.02)
    raise AssertionError("bounded child not collected")


@pytest.mark.parametrize("mode,state", [("candidate","CANDIDATE_READY"),
    ("invalid-output","FAILED_OUTPUT"), ("oversize","UNKNOWN"), ("malformed","UNKNOWN")])
def test_real_child_bounded_result_and_one_shot_receipt(tmp_path, mode, state):
    job = process_job(tmp_path, mode=mode)
    request = draft_request()
    try:
        job.authorize(request)
        job.start(request)
        result = collect(job)
        assert result.state == state
        with pytest.raises(ConversationRejected):
            job.authorize(request)
        assert job.poll() is None
    finally:
        job.close()
    assert job._child.poll() is not None
    text = "".join(p.read_text("utf-8") for p in (tmp_path / "receipts").glob("*.json"))
    assert "RESERVED" in text and "DISPATCHED" in text
    for forbidden in (request.brief, "PRIVATE_TEST_MARKER", str(tmp_path), "secret", "content"):
        assert forbidden not in text
    resumed = process_job(tmp_path, mode=mode)
    resumed.authorize(request)
    with pytest.raises(ConversationRejected):
        resumed.start(request)
    assert resumed._child is None
    resumed.close()


def test_watchdog_independent_of_any_http_request_and_no_child_survives(tmp_path):
    job = process_job(tmp_path, mode="blocked", timeout=.3)
    job.authorize(draft_request())
    job.start(draft_request())
    started = time.monotonic()
    result = collect(job)
    job.close()
    assert result.state == "UNKNOWN" and time.monotonic() - started < 4
    assert job._child.poll() is not None


def test_close_bounded_while_child_waits(tmp_path):
    job = process_job(tmp_path, mode="blocked")
    job.authorize(draft_request())
    job.start(draft_request())
    started = time.monotonic()
    job.close()
    assert time.monotonic() - started < 3.5
    assert job.poll().state == "UNKNOWN"
    assert job._child.poll() is not None


@pytest.mark.parametrize("raw", [b"", b"\x00\x00\x00\x00", b"\x00\x04\x00\x01", encode_frame({}) + b"x",
    b'\x00\x00\x00\x0d{"a":1,"a":2}'])
def test_ipc_closed_frame(raw):
    with pytest.raises(ValueError):
        decode_frame(raw)


def test_receipts_are_closed_metadata_not_payload(tmp_path):
    job = process_job(tmp_path)
    job.authorize(draft_request())
    job.start(draft_request())
    collect(job)
    job.close()
    for file in (tmp_path / "receipts").glob("*.json"):
        value = json.loads(file.read_text("utf-8"))
        assert set(value) == {"authorization_sha256", "state", "generation_id", "request_id",
                               "reserved_usd", "observed_usd", "timestamp"}


def test_worker_environment_rejects_endpoint_proxy_and_credential_inputs(tmp_path):
    import sys
    from decimal import Decimal
    from pathlib import Path

    from backend.adapters.outbound.system.conversation_job import (
        ConversationProcessJob,
        OneShotReceipt,
    )
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "HTTPS_PROXY", "PROJET_V2_CANONICAL_DB"):
        with pytest.raises(ValueError, match="WORKER_CONFIGURATION_REJECTED"):
            ConversationProcessJob(executable=Path(sys.executable), working_directory=tmp_path,
                environment={"PYTHONDONTWRITEBYTECODE":"1", key:"SYNTHETIC_NOT_READ"},
                authorize=lambda request: None,
                receipt=OneShotReceipt(tmp_path / "receipts", "c" * 64, Decimal("0")))


def test_denied_authorization_has_no_receipt_child_or_retry(tmp_path):
    job = process_job(tmp_path)
    def denied(request):
        raise ConversationRejected("BUDGET_UNAVAILABLE")
    job.check = denied
    with pytest.raises(ConversationRejected, match="BUDGET_UNAVAILABLE"):
        job.authorize(draft_request())
    with pytest.raises(ConversationRejected):
        job.start(draft_request())
    assert job._child is None and not job.receipt.root.exists()
    job.close()
