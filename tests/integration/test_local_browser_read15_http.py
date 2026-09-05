from __future__ import annotations

import hashlib
import json
import socket
import time
from pathlib import Path

import pytest

from backend.adapters.inbound.api.server import MAX_HEADER_BYTES, SOCKET_TIMEOUT_SECONDS
from backend.adapters.inbound.application.resource_library import ResourceLibraryUseCaseInbound
from backend.agent_runtime.contracts import UseCaseRequest, UseCaseResult
from tests.integration.test_local_browser_product_composition import (
    events,
    fetch,
    free_loopback_port,
    running,
    synthetic_target,
)


def raw_request(port: int, request: bytes, *, timeout: float = 3) -> tuple[int, bytes, bytes]:
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as client:
        client.sendall(request)
        client.shutdown(socket.SHUT_WR)
        chunks = []
        while chunk := client.recv(65_536):
            chunks.append(chunk)
    head, separator, body = b"".join(chunks).partition(b"\r\n\r\n")
    assert separator
    return int(head.split(b" ")[1]), head, body


@pytest.mark.parametrize("reference,status,availability", [
    ("resource:h2-active", 200, "ACTIVE"), ("resource:h2-legacy", 200, "UNKNOWN"),
    ("absent", 404, None), ("_invalid", 400, None), (".", 400, None),
    ("..", 400, None), ("a%00", 400, None), ("a" * 129, 400, None),
])
def test_real_application_transport_projection(
    tmp_path: Path, reference: str, status: int, availability: str | None,
) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        actual, headers, body = fetch(composition, "/api/v2/resources/" + reference)
        assert actual == status
        payload = json.loads(body)
        assert payload["meta"] == {"correlation_id": headers["X-Correlation-Id"]}
        if availability is not None:
            assert set(payload["data"]) == {
                "resource_ref", "resource_type", "canonical_title", "availability_status"
            }
            assert payload["data"]["availability_status"] == availability
            assert "canonicality_status" not in payload["data"]
        else:
            assert set(payload["error"]) == {"category", "code"}
            assert payload["error"]["code"] == (
                "RES_NOT_FOUND" if status == 404 else "READ15_REQUEST_REJECTED"
            )


@pytest.mark.parametrize("path,media", [
    ("/", "text/html"), ("/assets/app.js", "text/javascript"),
    ("/assets/styles.css", "text/css"),
])
def test_exact_assets_get_head_and_security_headers(tmp_path: Path, path: str, media: str) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        status, headers, body = fetch(composition, path)
        head_status, head_headers, head_body = fetch(composition, path, "HEAD")
        assert status == head_status == 200
        assert body and head_body == b""
        assert int(headers["Content-Length"]) == len(body)
        assert head_headers["Content-Length"] == headers["Content-Length"]
        assert media in headers["Content-Type"]
        assert headers["Connection"] == "close"
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert "Server" not in headers
        if path == "/":
            assert b'src="/assets/app.js"' in body
            assert b'href="/assets/styles.css"' in body
            assert b'<form id="resource-form">' in body
        if path == "/assets/app.js":
            assert b"fetch(" in body and b"textContent" in body
            assert b"innerHTML" not in body and b"credentials: \"omit\"" in body


@pytest.mark.parametrize("wire,status,code", [
    (b"GET / HTTP/1.1\r\n\r\n", 403, "HOST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nHost: localhost\r\n\r\n", 403, "HOST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: remote.invalid\r\n\r\n", 403, "HOST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost:1\r\n\r\n", 403, "HOST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nOrigin: https://remote.invalid\r\n\r\n",
     403, "ORIGIN_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nOrigin: x\r\nOrigin: y\r\n\r\n",
     403, "ORIGIN_REJECTED"),
    (b"OPTIONS / HTTP/1.1\r\nHost: localhost\r\n\r\n", 403, "PREFLIGHT_REJECTED"),
    (b"POST / HTTP/1.1\r\nHost: localhost\r\n\r\n", 405, "METHOD_REJECTED"),
    (b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n", 404, "ROUTE_NOT_FOUND"),
    (b"GET http://localhost/ HTTP/1.1\r\nHost: localhost\r\n\r\n", 400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 1\r\n\r\nx",
     400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n",
     400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\nContent-Length: 0\r\n\r\n",
     400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\n x: folded\r\n\r\n",
     400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost : localhost\r\n\r\n", 400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nCookie: PRIVATE_SENTINEL\r\n\r\n",
     400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nAuthorization: PRIVATE_SENTINEL\r\n\r\n",
     400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\r\nHost: localhost\r\nExpect: 100-continue\r\n\r\n",
     400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/2.0\r\nHost: localhost\r\n\r\n", 400, "READ15_REQUEST_REJECTED"),
    (b"GET / HTTP/1.1\nHost: localhost\n\n", 400, "READ15_REQUEST_REJECTED"),
])
def test_raw_rejections_before_application_without_leaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wire: bytes, status: int, code: str,
) -> None:
    target = synthetic_target(tmp_path)
    calls = []
    def forbidden(self: ResourceLibraryUseCaseInbound, *, request: UseCaseRequest
                  ) -> UseCaseResult[object, object]:
        calls.append(request)
        raise AssertionError("UNEXPECTED_APPLICATION_INVOCATION")
    monkeypatch.setattr(ResourceLibraryUseCaseInbound, "invoke", forbidden)
    with running(target) as composition:
        actual, _, body = raw_request(composition.server.service.configuration.port, wire)
        assert actual == status
        assert json.loads(body)["error"]["code"] == code
        assert calls == []
    raw = json.dumps(events(target))
    assert "PRIVATE_SENTINEL" not in raw
    assert "remote.invalid" not in raw
    assert str(target.runtime_path) not in raw


def test_application_is_actually_traversed_once_and_no_permission_from_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = synthetic_target(tmp_path)
    calls: list[UseCaseRequest] = []
    original = ResourceLibraryUseCaseInbound.invoke
    def recording(self: ResourceLibraryUseCaseInbound, *, request: UseCaseRequest
                  ) -> UseCaseResult[object, object]:
        calls.append(request)
        return original(self, request=request)
    monkeypatch.setattr(ResourceLibraryUseCaseInbound, "invoke", recording)
    with running(target) as composition:
        status, headers, _ = fetch(
            composition, "/api/v2/resources/resource:h2-active",
            headers={"X-Correlation-Id": "PRIVATE_SENTINEL", "X-Permission": "admin"},
        )
        assert status == 200 and len(calls) == 1
        assert calls[0].payload == {"resource_ref": "resource:h2-active"}
        assert calls[0].requested_effect == {}
        assert calls[0].idempotency_key is None
        assert calls[0].precondition_refs == ()
        assert calls[0].meta.actor.actor_id == "local-read15"
        assert calls[0].meta.correlation_id.value == headers["X-Correlation-Id"]
        assert headers["X-Correlation-Id"] != "PRIVATE_SENTINEL"


def test_head_api_and_head_malformed_headers_have_no_body(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        status, _, body = fetch(composition, "/api/v2/resources/resource:h2-active", "HEAD")
        assert status == 405 and body == b""
        status, _, body = raw_request(
            composition.server.service.configuration.port,
            b"HEAD / HTTP/1.1\r\nHost: x\r\nHost: y\r\n\r\n",
        )
        assert status == 403 and body == b""


def test_header_budget_exact_and_plus_one(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    assert MAX_HEADER_BYTES == 65_536
    prefix = b"Host: localhost\r\nX-Pad: "
    exact = prefix + b"x" * (MAX_HEADER_BYTES - len(prefix) - 4) + b"\r\n\r\n"
    assert len(exact) == MAX_HEADER_BYTES
    with running(target) as composition:
        port = composition.server.service.configuration.port
        assert raw_request(port, b"GET / HTTP/1.1\r\n" + exact)[0] == 200
        assert raw_request(port, b"GET / HTTP/1.1\r\n" + exact.replace(b"X-Pad: ", b"X-Pad: x"))[0] == 400


def test_target_budget_rejects_before_waiting_for_headers(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        port = composition.server.service.configuration.port
        with socket.create_connection(("127.0.0.1", port), timeout=1) as client:
            client.sendall(b"GET /" + b"x" * 8_192 + b" HTTP/1.1\r\n")
            assert client.recv(100).startswith(b"HTTP/1.0 400 ")


def test_actual_five_second_input_deadline(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    assert SOCKET_TIMEOUT_SECONDS == 5.0
    with running(target) as composition:
        port = composition.server.service.configuration.port
        with socket.create_connection(("127.0.0.1", port), timeout=7) as client:
            started = time.monotonic()
            client.sendall(b"GET / HTTP/1.1\r\nHost: local")
            time.sleep(3)
            client.sendall(b"h")
            assert client.recv(100).startswith(b"HTTP/1.0 400 ")
            elapsed = time.monotonic() - started
            assert 4.5 <= elapsed < 6.5


def test_tampered_runtime_returns_technical_failure_no_migration(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        with target.runtime_path.open("ab") as fixture:
            fixture.write(b"synthetic tamper")
        status, _, body = fetch(composition, "/api/v2/resources/resource:h2-active")
        assert status == 500
        assert json.loads(body)["error"] == {"category": "technical", "code": "INTERNAL_ERROR"}
    assert hashlib.sha256(target.runtime_path.read_bytes()).hexdigest() != target.expected_sha256


def test_ipv6_loopback_when_explicitly_selected(tmp_path: Path) -> None:
    # No new skip: inability to bind IPv6 is a visible capability failure of this increment.
    target = synthetic_target(tmp_path)
    port = free_loopback_port("::1")
    with running(target, host="::1", port=port) as composition:
        assert composition.url == f"http://[::1]:{port}/"
        assert fetch(composition, "/")[0] == 200
