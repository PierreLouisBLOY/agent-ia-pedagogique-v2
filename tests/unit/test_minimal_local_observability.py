from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.infrastructure.filesystem import PermissionStatus, inspect_permission_status
from backend.infrastructure.observability import (
    MAX_LOG_FILE_COUNT,
    MAX_SHUTDOWN_FLUSH_SECONDS,
    RETENTION_DAYS,
    ROTATION_SIZE_BYTES,
    FailureIsolatedOperationalEventSink,
    LocalRotatingNdjsonWriter,
    OperationalEvent,
    OperationalEventCode,
    OperationalEventLevel,
    serialize_operational_event,
)

NOW = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)


class CollectingWriter:
    def __init__(self) -> None:
        self.records: list[str] = []
        self.flushed = 0
        self.closed = 0

    def write(self, record: str) -> int:
        self.records.append(record)
        return len(record)

    def flush(self) -> None:
        self.flushed += 1

    def close(self) -> None:
        self.closed += 1


class FailingWriter:
    def write(self, record: str) -> int:
        del record
        raise OSError("synthetic failure with private material")


def _startup() -> OperationalEvent:
    return OperationalEvent(
        NOW,
        OperationalEventLevel.INFO,
        OperationalEventCode.APP_STARTUP,
        {
            "app_version": "v2.0",
            "config_profile_id": "local.default",
            "sink_health": "HEALTHY",
            "runtime_mode": "LOCAL",
            "outcome": "SUCCEEDED",
        },
    )


def test_operational_event_serialization_is_valid_bounded_ndjson() -> None:
    serialized = serialize_operational_event(_startup())
    payload = json.loads(serialized)

    assert serialized.endswith("\n")
    assert payload == {
        "app_version": "v2.0",
        "component": "application",
        "config_profile_id": "local.default",
        "event": "app.startup",
        "level": "INFO",
        "message": "app.startup",
        "outcome": "SUCCEEDED",
        "runtime_mode": "LOCAL",
        "sink_health": "HEALTHY",
        "ts": "2026-09-04T18:00:00.000000Z",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization_header", "Bearer-fake"),
        ("payload", "synthetic"),
        ("authorization_id", "sk-" + "X" * 32),
        ("authorization_id", "C:\\Users\\Example\\secret"),
    ],
)
def test_closed_schema_rejects_sensitive_keys_and_values(field: str, value: str) -> None:
    fields: dict[str, str | int | float | bool] = {
        "provider_id": "anthropic",
        "model_profile_id": "claude-sonnet-5",
        "call_id": "call-1",
        "authorization_id": "auth-1",
        "attempt_number": 1,
        "outcome": "STARTED",
    }
    fields[field] = value

    with pytest.raises(ValueError):
        OperationalEvent(
            NOW,
            OperationalEventLevel.INFO,
            OperationalEventCode.PROVIDER_CALL_STARTED,
            fields,
        )


def test_sink_failure_is_isolated_and_bounded() -> None:
    sink = FailureIsolatedOperationalEventSink(FailingWriter())

    sink.emit(_startup())

    health = sink.health_snapshot()
    assert health.healthy is False
    assert health.delivered_event_count == 0
    assert health.dropped_event_count == 1
    assert "private material" not in repr(health)


def test_writer_rotates_at_five_mib_and_keeps_five_files_maximum(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    writer = LocalRotatingNdjsonWriter(root, clock=lambda: NOW)
    record = '{"event":"synthetic","padding":"' + "x" * 1_048_000 + '"}\n'

    for _ in range(26):
        assert writer.write(record) == len(record)

    files = sorted((root / "logs").glob("observability.ndjson*"))
    assert len(files) == MAX_LOG_FILE_COUNT
    assert all(path.stat().st_size <= ROTATION_SIZE_BYTES for path in files)
    assert (root / "logs" / "observability.ndjson.4").is_file()
    assert (
        inspect_permission_status(files[0], allowed_root=root)
        is PermissionStatus.PRIVATE_OWNER_ONLY
    )


def test_writer_rejects_a_data_root_inside_a_repository(tmp_path: Path) -> None:
    repository = tmp_path / "checkout"
    (repository / ".git").mkdir(parents=True)

    with pytest.raises(ValueError, match="outside the repository"):
        LocalRotatingNdjsonWriter(repository / "runtime")

    assert not (repository / "runtime").exists()


def test_retention_purges_only_rotated_files_strictly_older_than_fourteen_days(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    log_dir = root / "logs"
    log_dir.mkdir(parents=True)
    expired = log_dir / "observability.ndjson.1"
    retained = log_dir / "observability.ndjson.2"
    expired.write_text("{}\n", encoding="utf-8")
    retained.write_text("{}\n", encoding="utf-8")
    expired_time = NOW - timedelta(days=RETENTION_DAYS, seconds=1)
    retained_time = NOW - timedelta(days=RETENTION_DAYS)
    os.utime(expired, (expired_time.timestamp(), expired_time.timestamp()))
    os.utime(retained, (retained_time.timestamp(), retained_time.timestamp()))

    LocalRotatingNdjsonWriter(root, clock=lambda: NOW)

    assert not expired.exists()
    assert retained.exists()


def test_local_policy_constants_are_exact_owner_decision() -> None:
    assert ROTATION_SIZE_BYTES == 5 * 1_024 * 1_024
    assert MAX_LOG_FILE_COUNT == 5
    assert RETENTION_DAYS == 14
    assert MAX_SHUTDOWN_FLUSH_SECONDS == 2
