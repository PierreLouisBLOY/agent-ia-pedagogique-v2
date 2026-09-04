from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence import migrations
from backend.adapters.outbound.persistence.migrations import (
    DEFERRED_UNKNOWN_MIGRATIONS,
    MIGRATION_002_SHA256,
    MigrationNotAllowed,
    MigrationRegistry,
    RuntimeProvisioningError,
    SeedAuthenticationError,
    apply_migrations,
    create_runtime_backup,
    inspect_database,
    migration_registry,
    provision_runtime,
    restore_runtime_backup,
    snapshot_sqlite_files,
)

MIGRATION = Path("database/migrations/001_document_sha256_check.sql")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def canonical_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
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

    monkeypatch.setattr(migrations, "CANONICAL_SEED_SIZE", seed.stat().st_size)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_SHA256", _sha256(seed))
    monkeypatch.setattr(migrations, "CANONICAL_SEED_TABLES", 1)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_EXPLICIT_INDEXES", 2)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_TRIGGERS", 0)
    monkeypatch.setattr(migrations, "CANONICAL_SEED_VIEWS", 0)
    yield seed


def test_authenticated_seed_is_opened_without_mutating_main_or_sidecars(
    canonical_seed: Path,
) -> None:
    before = snapshot_sqlite_files(canonical_seed)

    evidence = inspect_database(canonical_seed, authenticate_seed=True)

    assert evidence.integrity == evidence.quick == "ok"
    assert evidence.foreign_key_violations == 0
    assert snapshot_sqlite_files(canonical_seed) == before


def test_missing_seed_fails_before_runtime_creation(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime.sqlite"

    with pytest.raises(SeedAuthenticationError, match="missing"):
        provision_runtime(tmp_path / "missing.sqlite", runtime, MIGRATION)

    assert not runtime.exists()


def test_invalid_seed_identity_fails_before_runtime_creation(
    canonical_seed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime.sqlite"
    monkeypatch.setattr(migrations, "CANONICAL_SEED_SHA256", "0" * 64)

    with pytest.raises(SeedAuthenticationError, match="mismatch"):
        provision_runtime(canonical_seed, runtime, MIGRATION)

    assert not runtime.exists()


def test_runtime_absent_is_copied_migrated_and_atomically_published(
    canonical_seed: Path, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime" / "runtime.sqlite"

    report = provision_runtime(canonical_seed, runtime, MIGRATION)

    assert report.runtime_created is True
    assert report.runtime_existing is False
    assert report.migration_applied is True
    assert report.migration_checksum == MIGRATION_002_SHA256
    assert report.migration_versions == ("001", "002")
    assert report.migrations_applied == ("001", "002")
    assert report.migrations_skipped == ()
    assert report.documents_before == report.documents_after == 1
    assert report.journal_mode == "wal"
    assert {"wal", "shm"} <= set(report.runtime_sidecars_observed)
    assert report.seed_pre_snapshot == report.seed_post_snapshot
    assert report.seed_sidecar_created_by_b08 is False
    assert report.deferred_migrations == DEFERRED_UNKNOWN_MIGRATIONS
    assert report.domain_tables == 1
    assert report.explicit_indexes == 2


def test_runtime_can_be_provisioned_from_an_explicit_registry(
    canonical_seed: Path, tmp_path: Path
) -> None:
    report = provision_runtime(
        canonical_seed,
        tmp_path / "registry-runtime.sqlite",
        migration_registry(MIGRATION),
    )

    assert report.migration_versions == ("001", "002")
    assert report.migrations_applied == ("001", "002")


def test_existing_runtime_is_not_overwritten_and_replay_is_idempotent(
    canonical_seed: Path, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime.sqlite"
    first = provision_runtime(canonical_seed, runtime, MIGRATION)
    file_identity = runtime.stat().st_ino
    before = _sha256(runtime)

    second = provision_runtime(canonical_seed, runtime, MIGRATION)

    assert first.migration_applied is True
    assert second.runtime_created is False
    assert second.runtime_existing is True
    assert second.migration_applied is False
    assert second.migration_versions == ("001", "002")
    assert second.migrations_applied == ()
    assert second.migrations_skipped == ("001", "002")
    assert runtime.stat().st_ino == file_identity
    assert _sha256(runtime) == before
    with sqlite3.connect(runtime) as connection:
        assert connection.execute("SELECT count(*) FROM document").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT count(*) FROM _runtime_migration_ledger"
            ).fetchone()[0]
            == 2
        )


def test_existing_001_runtime_is_advanced_only_to_002(
    canonical_seed: Path, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime-at-001.sqlite"
    shutil.copy2(canonical_seed, runtime)
    full_registry = migration_registry(MIGRATION)
    with sqlite3.connect(runtime, isolation_level=None) as connection:
        apply_migrations(connection, MigrationRegistry((full_registry.specs[0],)))

    report = provision_runtime(canonical_seed, runtime, MIGRATION)

    assert report.runtime_created is False
    assert report.runtime_existing is True
    assert report.migrations_applied == ("002",)
    assert report.migrations_skipped == ("001",)
    with sqlite3.connect(runtime) as connection:
        assert connection.execute(
            "SELECT version FROM _runtime_migration_ledger ORDER BY version"
        ).fetchall() == [("001",), ("002",)]


def test_seed_and_runtime_identity_must_be_distinct(canonical_seed: Path) -> None:
    with pytest.raises(RuntimeProvisioningError, match="distinct"):
        provision_runtime(canonical_seed, canonical_seed, MIGRATION)


def test_non_allowlisted_migration_is_blocked_without_runtime(
    canonical_seed: Path, tmp_path: Path
) -> None:
    altered = tmp_path / "unknown.sql"
    altered.write_text(MIGRATION.read_text(encoding="utf-8") + "\n-- unknown\n")
    runtime = tmp_path / "runtime.sqlite"

    with pytest.raises(MigrationNotAllowed, match="allowlisted"):
        provision_runtime(canonical_seed, runtime, altered)

    assert not runtime.exists()


def test_preexisting_seed_sidecars_are_attributed_and_preserved(
    canonical_seed: Path, tmp_path: Path
) -> None:
    Path(f"{canonical_seed}-wal").write_bytes(b"")
    Path(f"{canonical_seed}-shm").write_bytes(b"pre-existing")
    before = snapshot_sqlite_files(canonical_seed)

    report = provision_runtime(canonical_seed, tmp_path / "runtime.sqlite", MIGRATION)

    assert before.wal.exists is True
    assert before.shm.exists is True
    assert report.seed_pre_snapshot == report.seed_post_snapshot == before
    assert report.seed_sidecar_created_by_b08 is False


def test_publication_race_never_overwrites_the_winner(
    canonical_seed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime.sqlite"
    original_link = os.link

    def race_link(source: Path, destination: Path) -> None:
        if destination == runtime:
            destination.write_bytes(b"race-winner")
            raise FileExistsError
        original_link(source, destination)

    monkeypatch.setattr(os, "link", race_link)

    with pytest.raises(RuntimeProvisioningError, match="already exists"):
        provision_runtime(canonical_seed, runtime, MIGRATION)

    assert runtime.read_bytes() == b"race-winner"


def test_runtime_backup_and_fresh_restore_are_authenticated(
    canonical_seed: Path, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime.sqlite"
    provision_runtime(canonical_seed, runtime, MIGRATION)
    backup = tmp_path / "backups" / "runtime-backup.sqlite"

    backup_report = create_runtime_backup(runtime, backup)
    restored_path = tmp_path / "restored" / "runtime.sqlite"
    restored = restore_runtime_backup(
        backup, restored_path, canonical_seed_path=canonical_seed
    )

    assert backup_report.backup_sha256 == _sha256(backup)
    assert backup_report.manifest_sha256 == _sha256(
        backup.with_name(f"{backup.name}.manifest.json")
    )
    assert restored.sha256 == backup_report.backup_sha256
    assert restored.integrity == restored.quick == "ok"
    assert restored.foreign_key_violations == 0


def test_restore_to_seed_is_blocked(canonical_seed: Path, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime.sqlite"
    provision_runtime(canonical_seed, runtime, MIGRATION)
    backup = tmp_path / "backup.sqlite"
    create_runtime_backup(runtime, backup)

    with pytest.raises(RuntimeProvisioningError, match="distinct"):
        restore_runtime_backup(
            backup, canonical_seed, canonical_seed_path=canonical_seed
        )
