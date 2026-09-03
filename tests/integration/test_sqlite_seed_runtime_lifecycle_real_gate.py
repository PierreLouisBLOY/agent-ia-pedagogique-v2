from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import (
    CANONICAL_SEED_EXPLICIT_INDEXES,
    CANONICAL_SEED_TABLES,
    CANONICAL_SEED_TRIGGERS,
    CANONICAL_SEED_VIEWS,
    create_runtime_backup,
    restore_runtime_backup,
    snapshot_sqlite_files,
)
from backend.infrastructure.composition.factories.sqlite import (
    build_configured_sqlite_runtime,
)
from backend.infrastructure.config.loaders.sqlite import (
    CANONICAL_DB_ENV,
    DATA_DIR_ENV,
    LEGACY_SEED_PATH_ENV,
    RUNTIME_DB_ENV,
)

SEED_VALUE = os.environ.get(CANONICAL_DB_ENV) or os.environ.get(
    LEGACY_SEED_PATH_ENV
)
pytestmark = pytest.mark.skipif(
    SEED_VALUE is None, reason="canonical SQLite seed is not configured"
)
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")


def test_real_seed_runtime_sidecars_backup_and_restore(tmp_path: Path) -> None:
    assert SEED_VALUE is not None
    seed = Path(SEED_VALUE)
    runtime = tmp_path / "runtime" / "application.sqlite"
    environment = {
        DATA_DIR_ENV: str(tmp_path),
        CANONICAL_DB_ENV: str(seed),
        RUNTIME_DB_ENV: str(runtime),
    }
    seed_pre = snapshot_sqlite_files(seed)

    composition = build_configured_sqlite_runtime(environment, MIGRATION)
    report = composition.readiness
    backup = composition.paths.backups_directory / "application.sqlite"
    backup_report = create_runtime_backup(runtime, backup)
    restored = restore_runtime_backup(
        backup,
        tmp_path / "restored" / "application.sqlite",
        canonical_seed_path=seed,
    )

    assert report.runtime_created is True
    assert report.runtime_existing is False
    assert report.migration_applied is True
    assert report.journal_mode == "wal"
    assert {"wal", "shm"} <= set(report.runtime_sidecars_observed)
    assert report.seed_pre_snapshot == report.seed_post_snapshot == seed_pre
    assert report.seed_sidecar_created_by_b08 is False
    assert (
        report.domain_tables,
        report.explicit_indexes,
        report.triggers,
        report.views,
    ) == (
        CANONICAL_SEED_TABLES,
        CANONICAL_SEED_EXPLICIT_INDEXES,
        CANONICAL_SEED_TRIGGERS,
        CANONICAL_SEED_VIEWS,
    )
    assert restored.sha256 == backup_report.backup_sha256
    assert restored.integrity == restored.quick == "ok"
    assert restored.foreign_key_violations == 0
    assert snapshot_sqlite_files(seed) == seed_pre
