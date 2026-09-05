from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
import time
from dataclasses import replace
from pathlib import Path

import pytest

from backend.adapters.inbound.application.local_search import LocalSearchUseCaseInbound
from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    _application_searcher,
    build_local_read15,
)
from tests.integration.test_local_browser_product_composition import (
    events,
    fetch,
    free_loopback_port,
    running,
    synthetic_target,
)
from tests.integration.test_local_browser_read15_http import raw_request
from tests.integration.test_local_search_sqlite import RESOURCE, TEXT, synthetic_search_target


def test_http_search_then_read15_traverses_application_and_preserves_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = synthetic_search_target(tmp_path, count=2)
    before = target.runtime_path.read_bytes()
    calls = []
    invoke = LocalSearchUseCaseInbound.invoke
    def traced(self, *, request):
        calls.append(request.use_case_id)
        return invoke(self, request=request)
    monkeypatch.setattr(LocalSearchUseCaseInbound, "invoke", traced)
    with running(target) as composition:
        status, headers, raw = fetch(composition, "/api/v2/search?q=bilan&limit=10")
        assert status == 200
        data = json.loads(raw)
        items = data["data"]["items"]
        assert len(items) == 2 and items[0]["open_status"] == "OPENABLE"
        assert items[1]["read15"] is None and items[1]["open_status"] == "NOT_RESOURCE"
        assert data["meta"]["correlation_id"] == headers["X-Correlation-Id"]
        status, _, raw = fetch(composition, "/api/v2/resources/" + items[0]["read15"]["resource_ref"])
        assert status == 200 and json.loads(raw)["data"] == items[0]["read15"]
        status, _, raw = fetch(composition, "/api/v2/search?q=introuvable")
        assert status == 200 and json.loads(raw)["data"]["items"] == []
        assert calls == ["application.search_local_passages"] * 2
    assert target.runtime_path.read_bytes() == before
    rows = events(target)
    serialized = json.dumps(rows)
    for forbidden in (TEXT, "bilan", RESOURCE, "chunk:r1", "version:0", str(target.runtime_path), "SELECT"):
        assert forbidden not in serialized
    assert any(row.get("route_template") == "/api/v2/search" or
               row.get("fields", {}).get("route_template") == "/api/v2/search" for row in rows) or (
                   '"/api/v2/search"' in serialized
               )


@pytest.mark.parametrize("query", [
    "", "q=", "q=%20", "q=a&limit=21", "q=a&q=b", "q=a&version_ref=x",
    "q=%E2%80%AE", "q=" + "x" * 65, "q=a%00b",
])
def test_invalid_search_does_not_access_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str,
) -> None:
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        def forbidden(self):
            raise AssertionError("TARGET_METADATA_MUST_NOT_BE_ACCESSED")
        monkeypatch.setattr(Read15RuntimeTarget, "validate", forbidden)
        status, _, raw = fetch(composition, "/api/v2/search?" + query)
        assert status == 400
        assert "TARGET_METADATA" not in raw.decode()


@pytest.mark.parametrize("headers", [
    {"Host": "example.invalid"}, {"Origin": "https://example.invalid"},
])
def test_security_denial_before_search_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, headers: dict[str, str],
) -> None:
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        def forbidden(*args):
            pytest.fail("application must not run")
        monkeypatch.setattr(composition.server.service.search_endpoint, "_invoke", forbidden)
        status, _, raw = fetch(composition, "/api/v2/search?q=bilan", headers=headers)
        assert status == 403 and "bilan" not in raw.decode()


def test_reader_validation_does_not_discover_any_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Construct a target in memory only. Path methods are forbidden during invalid input.
    target = Read15RuntimeTarget(Path("never-accessed"), Path("never-accessed"), "0" * 64)
    def forbidden(*args, **kwargs):
        pytest.fail("path metadata or open invoked")
    for method in ("exists", "is_file", "stat", "open", "read_bytes"):
        monkeypatch.setattr(Path, method, forbidden)
    endpoint = _application_searcher(target)
    assert endpoint.get("", 10, "r1-correlation").status == 400
    assert endpoint.get("valid", True, "r1-correlation").status == 400


def test_missing_fts_technical_error_does_not_break_read15(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        assert fetch(composition, "/api/v2/resources/resource:h2-active")[0] == 200
        status, _, raw = fetch(composition, "/api/v2/search?q=bilan")
        assert status == 500
        assert json.loads(raw)["error"]["code"] == "INTERNAL_ERROR"
        assert "sqlite" not in raw.decode().lower()


def test_deleted_resource_between_requests_is_not_recalled_or_cached(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        status, _, raw = fetch(composition, "/api/v2/search?q=bilan")
        assert status == 200 and json.loads(raw)["data"]["items"][0]["open_status"] == "OPENABLE"
    # Separate fixture-writing phase, after all reader resources are closed.
    connection = sqlite3.connect(target.runtime_path)
    try:
        connection.execute("DELETE FROM resource")
        connection.commit()
    finally:
        connection.close()
    target = replace(target, expected_sha256=hashlib.sha256(target.runtime_path.read_bytes()).hexdigest())
    with running(target) as composition:
        assert fetch(composition, "/api/v2/resources/" + RESOURCE)[0] == 404
        status, _, raw = fetch(composition, "/api/v2/search?q=bilan")
        assert status == 200
        assert json.loads(raw)["data"]["items"][0]["open_status"] == "RESOURCE_NOT_FOUND"


def test_twelve_search_lifecycle_cycles_on_synthetic_snapshot(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path)
    before = target.runtime_path.read_bytes()
    port = free_loopback_port()
    observed = []
    correlations = set()
    for _ in range(12):
        with running(target, port=port) as composition:
            status, _, raw = fetch(composition, "/api/v2/search?q=bilan")
            assert status == 200
            envelope = json.loads(raw)
            observed.append(envelope["data"])
            correlations.add(envelope["meta"]["correlation_id"])
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    assert all(data == observed[0] for data in observed)
    assert len(correlations) == 12
    assert target.runtime_path.read_bytes() == before
    assert not target.runtime_path.with_name("search.sqlite-wal").exists()
    assert not target.runtime_path.with_name("search.sqlite-shm").exists()


def test_search_service_without_injected_reader_fails_closed(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        composition.server.service.search_endpoint = None
        assert fetch(composition, "/api/v2/search?q=bilan")[0] == 500


def test_sink_failure_does_not_change_search_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        writer = composition.observability._sink._writer
        def unavailable(*args, **kwargs):
            raise OSError("PRIVATE_SINK_FAILURE")
        monkeypatch.setattr(writer, "write", unavailable)
        status, _, raw = fetch(composition, "/api/v2/search?q=bilan")
        assert status == 200 and json.loads(raw)["data"]["items"]
        assert "PRIVATE_SINK_FAILURE" not in raw.decode()
        assert not composition.observability._sink.health_snapshot().healthy


def test_search_port_occupied_then_stop_incomplete_request_and_restart(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path)
    port = free_loopback_port()
    with running(target, port=port) as composition:
        with pytest.raises(OSError):
            build_local_read15(composition.server.service.configuration, target)
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            client.sendall(b"GET /api/v2/search?q=PRIVATE_QUERY HTTP/1.1\r\nHost: local")
            deadline = time.monotonic() + 2
            while composition.server._active is None and time.monotonic() < deadline:
                time.sleep(0.005)
            assert composition.server._active is not None
            started = time.monotonic()
            assert composition.close() <= 2
            assert time.monotonic() - started <= 2
    with running(target, port=port) as composition:
        assert fetch(composition, "/api/v2/search?q=bilan")[0] == 200
    assert "PRIVATE_QUERY" not in json.dumps(events(target))


def test_search_actual_input_deadline_and_minimized_timeout(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        with socket.create_connection(
            ("127.0.0.1", composition.server.service.configuration.port), timeout=7,
        ) as client:
            started = time.monotonic()
            client.sendall(b"GET /api/v2/search?q=PRIVATE_QUERY HTTP/1.1\r\nHost: local")
            time.sleep(3)
            client.sendall(b"h")
            assert client.recv(100).startswith(b"HTTP/1.0 400 ")
            assert 4.5 <= time.monotonic() - started < 6.5
    assert "PRIVATE_QUERY" not in json.dumps(events(target))


@pytest.mark.parametrize("suffix", [
    b"Content-Length: 1\r\n\r\nx", b"Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
])
def test_search_body_rejected_before_invoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: bytes,
) -> None:
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        def forbidden(*args):
            pytest.fail("body must be rejected before query")
        monkeypatch.setattr(composition.server.service.search_endpoint, "_invoke", forbidden)
        status, _, raw = raw_request(composition.server.service.configuration.port,
            b"GET /api/v2/search?q=PRIVATE_QUERY HTTP/1.1\r\nHost: localhost\r\n" + suffix)
        assert status == 400 and "PRIVATE_QUERY" not in raw.decode()


def test_search_wrong_hash_prevents_open_and_closes_connection_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
    from backend.infrastructure.composition.factories import local_browser as factory
    target = synthetic_search_target(tmp_path)
    opened = []
    original_connect = factory.connect_sqlite
    def record(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection
    monkeypatch.setattr(factory, "connect_sqlite", record)
    bad = replace(target, expected_sha256="0" * 64)
    assert _application_searcher(bad).get("bilan", 10, "r1-test").status == 500
    assert opened == []
    def fail(*args, **kwargs):
        raise ValueError("PRIVATE_FAILURE")
    monkeypatch.setattr(SQLiteLocalSearchAdapter, "admitted_window", fail)
    result = _application_searcher(target).get("bilan", 10, "r1-test")
    assert result.status == 500 and "PRIVATE_FAILURE" not in str(result.payload)
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")


def test_search_has_no_external_network_or_configuration_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    target = synthetic_search_target(tmp_path)
    with running(target) as composition:
        original_connect = socket.socket.connect
        original_lookup = socket.getaddrinfo
        def local_connect(self, address):
            assert address[0] in {"127.0.0.1", "::1"}
            return original_connect(self, address)
        def local_lookup(host, *args, **kwargs):
            assert host in {"127.0.0.1", "::1"}
            return original_lookup(host, *args, **kwargs)
        def no_settings(*args, **kwargs):
            pytest.fail("ambient settings or credentials must not be read")
        monkeypatch.setattr(socket.socket, "connect", local_connect)
        monkeypatch.setattr(socket, "getaddrinfo", local_lookup)
        monkeypatch.setattr(os, "getenv", no_settings)
        assert fetch(composition, "/api/v2/search?q=bilan")[0] == 200
