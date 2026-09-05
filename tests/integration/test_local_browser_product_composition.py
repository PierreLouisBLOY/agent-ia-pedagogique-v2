from __future__ import annotations

import hashlib
import http.client
import json
import socket
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from backend.adapters.inbound.cli.local_browser import main
from backend.infrastructure.composition.factories.local_browser import (
    LocalRead15Composition,
    Read15RuntimeTarget,
    build_local_read15,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration

SYNTHETIC_TITLE = "Titre synthétique <script>PRIVATE_SENTINEL</script>"


def synthetic_target(tmp_path: Path) -> Read15RuntimeTarget:
    root = tmp_path / "synthetic"
    root.mkdir()
    database = root / "fixture.sqlite"
    assert not database.exists()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE resource (id TEXT PRIMARY KEY, resource_type TEXT NOT NULL, "
            "canonical_title TEXT NOT NULL, identity_status TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO resource VALUES (?, ?, ?, ?)",
            [
                ("resource:h2-active", "COURSE", SYNTHETIC_TITLE, "ACTIVE"),
                ("resource:h2-legacy", "COURSE", "Titre historique synthétique", "CANONICAL"),
            ],
        )
    connection.close()
    return Read15RuntimeTarget(database, root, hashlib.sha256(database.read_bytes()).hexdigest())


def free_loopback_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


@contextmanager
def running(
    target: Read15RuntimeTarget, *, host: str = "127.0.0.1", port: int | None = None,
) -> Iterator[LocalRead15Composition]:
    composition = build_local_read15(
        LocalBrowserHttpConfiguration(port=port or free_loopback_port(host), bind_host=host), target
    )
    thread = threading.Thread(target=composition.serve_forever, name="h2-loopback-test")
    thread.start()
    assert composition.server._running.wait(2)
    try:
        yield composition
    finally:
        started = time.monotonic()
        elapsed = composition.close()
        thread.join(2)
        assert not thread.is_alive()
        assert elapsed <= 2
        assert time.monotonic() - started <= 2


def fetch(
    composition: LocalRead15Composition, target: str, method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    config = composition.server.service.configuration
    client = http.client.HTTPConnection(config.bind_host, config.port, timeout=3)
    try:
        client.request(method, target, headers=headers or {})
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


def events(target: Read15RuntimeTarget) -> list[dict[str, object]]:
    return [json.loads(line) for line in
            (target.data_root / "logs/observability.ndjson").read_text(encoding="utf-8").splitlines()]


def test_composition_real_adapter_readonly_lifecycle_restart(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    before = target.runtime_path.read_bytes()
    port = free_loopback_port()
    for _ in range(2):
        with running(target, port=port) as composition:
            assert composition.url == f"http://127.0.0.1:{port}/"
            status, headers, body = fetch(composition, "/api/v2/resources/resource:h2-active")
            assert status == 200
            payload = json.loads(body)
            assert payload["data"] == {
                "resource_ref": "resource:h2-active", "resource_type": "COURSE",
                "canonical_title": SYNTHETIC_TITLE, "availability_status": "ACTIVE",
            }
            assert payload["meta"]["correlation_id"] == headers["X-Correlation-Id"]
            assert "Server" not in headers and "Python" not in str(headers)
        assert composition.close() == 0
    assert target.runtime_path.read_bytes() == before
    assert not target.runtime_path.with_name("fixture.sqlite-wal").exists()
    assert not target.runtime_path.with_name("fixture.sqlite-shm").exists()
    records = events(target)
    assert sum(row["event"] == "app.startup" for row in records) == 2
    assert sum(row["event"] == "app.shutdown" for row in records) == 2
    raw = json.dumps(records)
    for forbidden in (SYNTHETIC_TITLE, "PRIVATE_SENTINEL", "resource:h2-active",
                      str(target.runtime_path), "sqlite.migration", "provider.call"):
        assert forbidden not in raw


def test_bad_digest_and_missing_target_rejected_without_bootstrap(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    configuration = LocalBrowserHttpConfiguration(port=free_loopback_port())
    with pytest.raises(ValueError, match="RUNTIME_IDENTITY_MISMATCH"):
        build_local_read15(configuration, Read15RuntimeTarget(
            target.runtime_path, target.data_root, "0" * 64
        ))
    with pytest.raises(ValueError, match="EXISTING_RUNTIME_REQUIRED"):
        build_local_read15(configuration, Read15RuntimeTarget(
            target.data_root / "missing.sqlite", target.data_root, "0" * 64
        ))
    assert not (target.data_root / "missing.sqlite").exists()
    assert not (target.data_root / "logs").exists()


def test_port_occupied_is_closed_and_sink_is_closed(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        with pytest.raises(OSError):
            build_local_read15(composition.server.service.configuration, target)


def test_stop_interrupts_incomplete_request_and_flushes(tmp_path: Path) -> None:
    target = synthetic_target(tmp_path)
    with running(target) as composition:
        client = socket.create_connection(
            ("127.0.0.1", composition.server.service.configuration.port), timeout=2
        )
        try:
            client.sendall(b"GET / HTTP/1.1\r\n")
            deadline = time.monotonic() + 2
            while composition.server._active is None and time.monotonic() < deadline:
                time.sleep(0.005)
            assert composition.server._active is not None
            started = time.monotonic()
            composition.close()
            assert time.monotonic() - started <= 2
        finally:
            client.close()


def test_cli_rejects_configuration_without_exposing_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    target = synthetic_target(tmp_path)
    assert main([
        "--port", "0", "--runtime", str(target.runtime_path),
        "--data-root", str(target.data_root), "--runtime-sha256", target.expected_sha256,
    ]) == 1
    output = capsys.readouterr()
    assert output.out == "LOCAL_READ15_STARTUP_REJECTED\n"
    assert str(tmp_path) not in output.out + output.err
