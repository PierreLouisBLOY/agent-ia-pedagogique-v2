from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence import migrations
from backend.infrastructure.composition.bootstrap.observability import (
    MINIMUM_OBSERVABILITY_SIGNAL_COUNT,
    LocalObservabilitySession,
)
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.infrastructure.observability import (
    FailureIsolatedOperationalEventSink,
    OperationalEventCode,
)

NOW = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)


class MemoryWriter:
    def __init__(self) -> None:
        self.records: list[str] = []
        self.flush_count = 0
        self.close_count = 0

    def write(self, record: str) -> int:
        self.records.append(record)
        return len(record)

    def flush(self) -> None:
        self.flush_count += 1

    def close(self) -> None:
        self.close_count += 1


def _session(writer: MemoryWriter) -> LocalObservabilitySession:
    monotonic_values = iter((10.0, 10.1))
    return LocalObservabilitySession(
        FailureIsolatedOperationalEventSink(writer),
        clock=lambda: NOW,
        monotonic=lambda: next(monotonic_values),
        correlation_id_factory=lambda: "corr-generated",
    )


def test_all_twelve_minimum_signal_families_are_covered_without_raw_data() -> None:
    writer = MemoryWriter()
    session = _session(writer)
    digest = "a" * 64

    session.startup(
        app_version="v2.0",
        config_profile_id="local.default",
        runtime_mode="LOCAL",
    )
    generated = session.http_request(
        method="get",
        route_template="/resources/{resource_ref}",
        status_code=200,
        duration_ms=12,
        incoming_correlation_id="../../private?query=secret",
    )
    session.http_request(
        method="POST",
        route_template="/reviews",
        status_code=500,
        duration_ms=19,
        incoming_correlation_id="corr-valid",
    )
    session.validation_rejected(
        boundary="HTTP",
        rule_code="INVALID_FIELD",
        field_code="resource_ref",
        correlation_id=generated,
    )
    session.sqlite_bootstrap_started(schema_version="002")
    session.sqlite_bootstrap_completed(
        schema_version="002",
        seed_identity_digest=digest,
        runtime_identity_digest="b" * 64,
    )
    session.sqlite_migration(
        started=True,
        succeeded=False,
        from_version="001",
        to_version="002",
        migration_id="restore-document-invariants",
        migration_checksum="c" * 64,
    )
    session.sqlite_migration(
        started=False,
        succeeded=True,
        from_version="001",
        to_version="002",
        migration_id="restore-document-invariants",
        migration_checksum="c" * 64,
    )
    session.sqlite_artifact_operation(
        recovery=False,
        succeeded=True,
        artifact_digest="d" * 64,
    )
    session.sqlite_artifact_operation(
        recovery=True,
        succeeded=True,
        artifact_digest="e" * 64,
    )
    session.provider_call(
        state="STARTED",
        provider_id="anthropic",
        model_profile_id="claude-sonnet-5",
        call_id="call-1",
        authorization_id="auth-1",
    )
    session.provider_call(
        state="COMPLETED",
        provider_id="anthropic",
        call_id="call-1",
        input_tokens=100,
        cached_input_tokens=25,
        output_tokens=10,
        cost_usd="0.000450",
        duration_ms=20,
    )
    session.provider_call(
        state="FAILED",
        provider_id="anthropic",
        call_id="call-2",
        duration_ms=7,
        provider_error_code="PROVIDER_UNAVAILABLE",
        authorization_consumed=True,
    )
    session.security_rejected(
        runtime_boundary=False,
        boundary="FILESYSTEM",
        policy_code="OUTSIDE_ALLOWED_ROOT",
    )
    session.security_rejected(
        runtime_boundary=True,
        boundary="RUNTIME",
        policy_code="AUTHORITY_KEY_REJECTED",
        correlation_id="corr-valid",
    )
    secret_message = "unhandled with sk-" + "Z" * 32
    session.unhandled_exception(
        RuntimeError(secret_message),
        boundary="APPLICATION_TOP_LEVEL",
        correlation_id="corr-valid",
    )
    elapsed = session.shutdown()

    payloads = [json.loads(record) for record in writer.records]
    codes = {payload["event"] for payload in payloads}
    required_codes = {
        OperationalEventCode.APP_STARTUP.value,
        OperationalEventCode.APP_SHUTDOWN.value,
        OperationalEventCode.APP_UNHANDLED_EXCEPTION.value,
        OperationalEventCode.HTTP_REQUEST_COMPLETED.value,
        OperationalEventCode.HTTP_REQUEST_FAILED.value,
        OperationalEventCode.HTTP_VALIDATION_REJECTED.value,
        OperationalEventCode.SQLITE_BOOTSTRAP_COMPLETED.value,
        OperationalEventCode.SQLITE_MIGRATION_COMPLETED.value,
        OperationalEventCode.SQLITE_BACKUP_COMPLETED.value,
        OperationalEventCode.SQLITE_RECOVERY_COMPLETED.value,
        OperationalEventCode.PROVIDER_CALL_STARTED.value,
        OperationalEventCode.PROVIDER_CALL_COMPLETED.value,
        OperationalEventCode.PROVIDER_CALL_FAILED.value,
        OperationalEventCode.SECURITY_PATH_REJECTED.value,
    }
    assert MINIMUM_OBSERVABILITY_SIGNAL_COUNT == 12
    assert required_codes <= codes
    assert generated == "corr-generated"
    assert elapsed == pytest.approx(0.1)
    assert elapsed <= 2
    assert writer.flush_count == 2
    assert writer.close_count == 1
    serialized = "".join(writer.records)
    assert secret_message not in serialized
    assert "../../private" not in serialized
    assert "query=secret" not in serialized


def test_http_surface_remains_a_contract_without_server_or_raw_request() -> None:
    writer = MemoryWriter()
    session = _session(writer)

    correlation_id = session.http_request(
        method="GET",
        route_template="/health",
        status_code=204,
        duration_ms=1,
        incoming_correlation_id="corr-incoming",
    )

    payload = json.loads(writer.records[-1])
    assert correlation_id == "corr-incoming"
    assert payload["route_template"] == "/health"
    assert set(payload).isdisjoint({"url", "query", "headers", "cookies", "body", "ip"})


def test_sqlite_composition_emits_bootstrap_migration_backup_and_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = tmp_path / "seed.sqlite"
    with sqlite3.connect(seed) as connection:
        connection.executescript(
            """
            CREATE TABLE document (
                id TEXT PRIMARY KEY,
                document_type TEXT NOT NULL,
                title TEXT NOT NULL,
                file_name TEXT,
                mime_type TEXT,
                publication_date TEXT,
                accessed_at TEXT,
                url TEXT,
                size_bytes INTEGER,
                sha256 TEXT,
                storage_uri TEXT,
                language_code TEXT NOT NULL,
                license_code TEXT,
                document_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX idx_document_sha256 ON document(sha256);
            CREATE INDEX idx_document_url ON document(url);
            INSERT INTO document(
                id, document_type, title, language_code, document_status, created_at
            ) VALUES ('document:seed', 'OTHER', 'seed', 'fr', 'ACTIVE', '2026-01-01');
            """
        )
    seed_sha256 = hashlib.sha256(seed.read_bytes()).hexdigest()
    monkeypatch.setattr(migrations, "CANONICAL_SEED_SIZE", seed.stat().st_size)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_SHA256", seed_sha256)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_TABLES", 1)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_EXPLICIT_INDEXES", 2)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_TRIGGERS", 0)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_VIEWS", 0)
    before = hashlib.sha256(seed.read_bytes()).hexdigest()
    writer = MemoryWriter()
    session = _session(writer)
    data_root = tmp_path / "data"
    runtime = data_root / "runtime" / "runtime.sqlite"
    paths = SQLiteDatabasePaths(seed, runtime, data_directory=data_root)

    composition = build_sqlite_runtime(
        paths,
        Path("database/migrations/001_document_sha256_check.sql"),
        observability=session,
    )
    backup = data_root / "backups" / "runtime.sqlite"
    backup_report = composition.create_backup(backup)
    restored = composition.restore_backup(
        backup,
        data_root / "restored" / "runtime.sqlite",
    )

    codes = {json.loads(record)["event"] for record in writer.records}
    assert {
        OperationalEventCode.SQLITE_BOOTSTRAP_STARTED.value,
        OperationalEventCode.SQLITE_BOOTSTRAP_COMPLETED.value,
        OperationalEventCode.SQLITE_MIGRATION_STARTED.value,
        OperationalEventCode.SQLITE_MIGRATION_COMPLETED.value,
        OperationalEventCode.SQLITE_BACKUP_COMPLETED.value,
        OperationalEventCode.SQLITE_RECOVERY_COMPLETED.value,
    } <= codes
    assert restored.sha256 == backup_report.backup_sha256
    assert hashlib.sha256(seed.read_bytes()).hexdigest() == before
    assert str(seed) not in "".join(writer.records)
    assert str(runtime) not in "".join(writer.records)
