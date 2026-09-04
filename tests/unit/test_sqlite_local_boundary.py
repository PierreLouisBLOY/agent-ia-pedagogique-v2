from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence import migrations
from backend.adapters.outbound.persistence.migrations import (
    RuntimeProvisioningError,
    create_runtime_backup,
    provision_runtime,
    restore_runtime_backup,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.infrastructure.config.schemas.sqlite import (
    SQLiteDatabasePaths,
    SQLitePathConfigurationError,
    SQLitePathErrorCode,
)
from backend.infrastructure.filesystem import LocalFileSecurityCode, LocalFileSecurityError

MIGRATION = Path("database/migrations/001_document_sha256_check.sql")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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
    return seed


def test_runtime_must_remain_below_local_data_root(tmp_path: Path) -> None:
    root = (tmp_path / "data").resolve()
    seed = (tmp_path / "seed.sqlite").resolve()
    outside = (tmp_path / "outside" / "runtime.sqlite").resolve()

    with pytest.raises(SQLitePathConfigurationError) as raised:
        SQLiteDatabasePaths(seed, outside, data_directory=root)

    assert raised.value.code is SQLitePathErrorCode.RUNTIME_OUTSIDE_DATA_DIRECTORY


def test_runtime_symlink_is_rejected_by_configuration_and_connection(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "data").resolve()
    root.mkdir()
    seed = tmp_path / "seed.sqlite"
    target = root / "target.sqlite"
    seed.write_bytes(b"seed")
    target.write_bytes(b"runtime")
    alias = root / "runtime.sqlite"
    try:
        alias.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable")

    with pytest.raises(SQLitePathConfigurationError) as configured:
        SQLiteDatabasePaths(seed.resolve(), alias, data_directory=root)
    assert configured.value.code is SQLitePathErrorCode.PATH_REDIRECTION_FORBIDDEN

    with pytest.raises(LocalFileSecurityError) as connected:
        connect_sqlite(alias, readonly=True, allowed_root=root)
    assert connected.value.code is LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN


def test_provisioning_hardens_runtime_and_keeps_temp_files_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = _synthetic_seed(tmp_path, monkeypatch)
    data_root = (tmp_path / "data").resolve()
    runtime = data_root / "runtime" / "runtime.sqlite"

    report = provision_runtime(seed, runtime, MIGRATION, data_root=data_root)

    assert report.seed_permission_status in {
        "EXTERNAL_READABLE_RESTRICTED",
        "PRIVATE_OWNER_ONLY",
        "WINDOWS_DACL_PRESENT",
    }
    assert report.runtime_permission_status == "PRIVATE_OWNER_ONLY"
    assert runtime.is_file()
    assert tuple(data_root.rglob("*.tmp")) == ()
    assert {"wal", "shm"} <= set(report.runtime_sidecars_observed)


def test_backup_restore_stay_in_root_and_never_accept_seed_as_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = _synthetic_seed(tmp_path, monkeypatch)
    data_root = (tmp_path / "data").resolve()
    runtime = data_root / "runtime" / "runtime.sqlite"
    provision_runtime(seed, runtime, MIGRATION, data_root=data_root)
    backup = data_root / "backups" / "runtime.sqlite"

    report = create_runtime_backup(
        runtime,
        backup,
        data_root=data_root,
        canonical_seed_path=seed,
    )
    restored = data_root / "restore" / "runtime.sqlite"
    evidence = restore_runtime_backup(
        backup,
        restored,
        canonical_seed_path=seed,
        data_root=data_root,
    )

    assert report.backup_permission_status == "PRIVATE_OWNER_ONLY"
    assert report.backup_sha256 == evidence.sha256
    assert tuple(data_root.rglob("*.tmp")) == ()

    with pytest.raises(RuntimeProvisioningError, match="distinct"):
        create_runtime_backup(
            runtime,
            seed,
            data_root=tmp_path.resolve(),
            canonical_seed_path=seed,
        )


def test_backup_destination_outside_explicit_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = _synthetic_seed(tmp_path, monkeypatch)
    data_root = (tmp_path / "data").resolve()
    runtime = data_root / "runtime.sqlite"
    provision_runtime(seed, runtime, MIGRATION, data_root=data_root)
    outside = (tmp_path / "outside" / "backup.sqlite").resolve()

    with pytest.raises(RuntimeProvisioningError, match="boundary rejected"):
        create_runtime_backup(runtime, outside, data_root=data_root)

    assert not outside.exists()


def test_hardlink_collision_is_rejected_before_provisioning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = _synthetic_seed(tmp_path, monkeypatch)
    alias = tmp_path / "runtime.sqlite"
    os.link(seed, alias)

    with pytest.raises(RuntimeProvisioningError, match="distinct"):
        provision_runtime(seed, alias, MIGRATION, data_root=tmp_path.resolve())
