from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import (
    MIGRATION_VERSION,
    MigrationArtifact,
)
from backend.infrastructure.config.loaders.sqlite import (
    CANONICAL_DB_ENV,
    DATA_DIR_ENV,
    RUNTIME_DB_ENV,
    load_sqlite_paths,
)
from backend.infrastructure.config.schemas.sqlite import (
    SQLitePathConfigurationError,
    SQLitePathErrorCode,
)


def test_sqlite_paths_are_typed_and_loaded_without_defaults(tmp_path: Path) -> None:
    paths = load_sqlite_paths(
        {
            DATA_DIR_ENV: str(tmp_path),
            CANONICAL_DB_ENV: str(tmp_path / "seed.sqlite"),
            RUNTIME_DB_ENV: str(tmp_path / "run.sqlite"),
        }
    )

    assert paths.data_directory == tmp_path
    assert paths.canonical_seed_path == tmp_path / "seed.sqlite"
    assert paths.runtime_database_path == tmp_path / "run.sqlite"


def test_sqlite_paths_fail_closed_when_os_data_directory_is_unavailable() -> None:
    with pytest.raises(SQLitePathConfigurationError) as raised:
        load_sqlite_paths({}, platform_name="win32")

    assert raised.value.code is SQLitePathErrorCode.MISSING_OS_DATA_DIRECTORY


def test_phase7_migration_artifact_has_stable_identity() -> None:
    artifact = MigrationArtifact.load(
        Path("database/migrations/001_document_sha256_check.sql")
    )

    assert artifact.version == MIGRATION_VERSION
    assert artifact.checksum == "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102"
    assert "CREATE TABLE document__p7_new" in artifact.sql
    assert "BEGIN IMMEDIATE" in artifact.sql
