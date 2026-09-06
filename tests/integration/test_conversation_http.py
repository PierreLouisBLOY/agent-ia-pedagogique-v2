import json
import socket

import pytest

from tests.support.conversation_fakes import (
    CONTEXT,
    PILOT,
    FakeJobs,
    http_call,
    http_command,
    running_conversation,
    wait_terminal,
)


def test_http_admission_context_confirmation_generation_and_exact_read(tmp_path):
    jobs = FakeJobs()
    with running_conversation(tmp_path, jobs=jobs) as (composition, target):
        before = target.runtime_path.read_bytes()
        (status, _, data), _ = http_command(composition, 1, text=PILOT)
        assert status == 200 and "level" in data["data"]["missing_fields"] and not jobs.calls
        (status, _, data), _ = http_command(composition, 2, text="Précisions confirmées", context_patch=CONTEXT, confirm_context=True)
        assert status == 200 and data["data"]["context"]["status"] == "CONFIRMED"
        sha = data["data"]["confirmed_context_sha256"]
        (status, headers, accepted), body = http_command(composition, 3, operation="generations", confirmed_context_sha256=sha)
        assert status == 202 and headers["Cache-Control"] == "no-store"
        assert http_call(composition, "/api/v2/conversation/generations", body=body)[2]["data"] == accepted["data"]
        assert len(jobs.calls) == 1
        assert http_command(composition, 4, text="autre")[0][0] == 409
        jobs.succeed()
        view = wait_terminal(composition)
        assert view["active_generation"]["state"] == "CANDIDATE_READY"
        refs = view["current_candidate"]
        route = "/api/v2/productions/" + refs["production_ref"] + "/versions/" + refs["version_ref"]
        first = http_call(composition, route)
        assert first[0] == 200
        assert first[2]["data"] == http_call(composition, route)[2]["data"]
        assert first[2]["data"]["validation_state"] == "CANDIDATE"
        assert http_call(composition, route.replace(refs["version_ref"], "ver:" + "f" * 32))[0] == 404
        assert len(jobs.calls) == 1 and target.runtime_path.read_bytes() == before


def test_disabled_r2_and_unapproved_product_do_not_generate(tmp_path):
    with running_conversation(tmp_path / "disabled", enabled=False) as (composition, _):
        assert http_call(composition)[0] == 404
    with running_conversation(tmp_path / "unapproved") as (composition, _):
        (_, _, data), _ = http_command(composition, 1, text=PILOT, context_patch=CONTEXT, confirm_context=True)
        response, _ = http_command(composition, 2, operation="generations",
                                   confirmed_context_sha256=data["data"]["confirmed_context_sha256"])
        assert response[0] == 403 and response[2]["error"]["code"] == "GENERATION_NOT_AUTHORIZED"


@pytest.mark.parametrize("extra,raw,status", [
    (b"", b"", 411), (b"Content-Length: 0\r\n", b"", 400),
    (b"Content-Length: 02\r\n", b"{}", 400),
    (b"Content-Length: 16385\r\n", b"", 413),
    (b"Content-Length: 2\r\nContent-Length: 2\r\n", b"{}", 400),
    (b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n", b"{}", 400),
    (b"Content-Length: 2\r\n", b"{}EXTRA", 400),
    (b"Content-Length: 2\r\nContent-Encoding: gzip\r\n", b"{}", 400),
])
def test_raw_post_framing_is_bounded_before_application(tmp_path, extra, raw, status):
    with running_conversation(tmp_path) as (composition, _):
        port = composition.server.service.configuration.port
        packet = (b"POST /api/v2/conversation/messages HTTP/1.1\r\n" +
            f"Host: 127.0.0.1:{port}\r\n".encode() + b"Content-Type: application/json; charset=utf-8\r\n" + extra + b"\r\n" + raw)
        with socket.create_connection(("127.0.0.1", port), timeout=7) as client:
            client.sendall(packet)
            response = bytearray()
            while chunk := client.recv(4096):
                response.extend(chunk)
        assert int(response.split(b" ")[1]) == status
        body = json.loads(response.split(b"\r\n\r\n", 1)[1])
        assert body["meta"]["contract_id"] == "CONVERSATION-HTTP-LOCAL-1.0"
        assert composition.conversation.service.snapshot()["revision"] == 1


@pytest.mark.parametrize("headers", [{"Origin":"http://other.invalid"}, {"X-R2-Nonce":"wrong"},
    {"Host":"localhost:8123"}, {"Sec-Fetch-Site":"cross-site"}, {"X-Local-Intent":"wrong"}])
def test_post_security_rejected_before_mutation(tmp_path, headers):
    with running_conversation(tmp_path) as (composition, _):
        body = {"command_id":"00000000-0000-0000-0000-000000000001", "conversation_id":composition.conversation.service.snapshot()["conversation_id"],
                "expected_revision":1, "text":PILOT}
        assert http_call(composition, "/api/v2/conversation/messages", body=body, headers=headers)[0] == 403
        assert composition.conversation.service.snapshot()["revision"] == 1


@pytest.mark.parametrize("truncate", [True, False])
def test_truncated_and_slow_body_respect_global_deadline(tmp_path, truncate):
    import time
    with running_conversation(tmp_path) as (composition, _):
        port = composition.server.service.configuration.port
        packet = (f"POST /api/v2/conversation/messages HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Content-Type: application/json; charset=utf-8\r\nContent-Length: 20\r\n\r\n{").encode()
        started = time.monotonic()
        with socket.create_connection(("127.0.0.1", port), timeout=7) as client:
            client.sendall(packet)
            if truncate:
                client.shutdown(socket.SHUT_WR)
            response = bytearray()
            while chunk := client.recv(4096):
                response.extend(chunk)
        assert time.monotonic() - started < 6.5
        assert int(response.split(b" ")[1]) == 400
        assert composition.conversation.service.snapshot()["revision"] == 1


@pytest.mark.parametrize("header", ["Authorization", "Proxy-Authorization", "Cookie", "Expect"])
def test_credential_headers_are_rejected_without_reflection(tmp_path, header):
    with running_conversation(tmp_path) as (composition, _):
        response = http_call(composition, "/api/v2/conversation/messages", body={},
                             headers={header:"SYNTHETIC_PRIVATE_MARKER"})
        assert response[0] == 400
        assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(response)
        assert composition.conversation.service.snapshot()["revision"] == 1


def test_technical_usage_is_not_exposed_in_http_candidate_or_conversation(tmp_path):
    from dataclasses import replace

    from backend.modules.work_orchestration.ports.outbound.generation_job import GenerationUsage
    jobs = FakeJobs()
    with running_conversation(tmp_path, jobs=jobs) as (composition, _):
        (_, _, data), _ = http_command(composition, 1, text=PILOT, context_patch=CONTEXT, confirm_context=True)
        response, _ = http_command(composition, 2, operation="generations",
            confirmed_context_sha256=data["data"]["confirmed_context_sha256"])
        assert response[0] == 202
        jobs.succeed()
        jobs.result = replace(jobs.result, usage=GenerationUsage(provider_attempted=True,
            response_received=True, input_tokens=111, output_tokens=222, parsing="SUCCEEDED"))
        view = wait_terminal(composition)
        refs = view["current_candidate"]
        route = "/api/v2/productions/" + refs["production_ref"] + "/versions/" + refs["version_ref"]
        raw = json.dumps([view, http_call(composition, route)[2]])
        assert "input_tokens" not in raw and "provider_attempted" not in raw and "technical" not in raw
        assert len(jobs.calls) == 1
