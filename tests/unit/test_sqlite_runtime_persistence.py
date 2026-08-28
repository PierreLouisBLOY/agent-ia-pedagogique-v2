from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import (
    MIGRATION_VERSION,
    MigrationArtifact,
)
from backend.infrastructure.config.loaders.sqlite import (
    RUNTIME_PATH_ENV,
    SEED_PATH_ENV,
    load_sqlite_paths,
)


def test_sqlite_paths_are_typed_and_loaded_without_defaults(tmp_path: Path) -> None:
    paths = load_sqlite_paths(
        {SEED_PATH_ENV: str(tmp_path / "seed.sqlite"), RUNTIME_PATH_ENV: str(tmp_path / "run.sqlite")}
    )

    assert paths.canonical_seed_path == tmp_path / "seed.sqlite"
    assert paths.runtime_database_path == tmp_path / "run.sqlite"


def test_sqlite_paths_require_both_explicit_settings() -> None:
    with pytest.raises(ValueError, match=RUNTIME_PATH_ENV):
        load_sqlite_paths({SEED_PATH_ENV: "seed.sqlite"})


def test_phase7_migration_artifact_has_stable_identity() -> None:
    artifact = MigrationArtifact.load(
        Path("database/migrations/001_document_sha256_check.sql")
    )

    assert artifact.version == MIGRATION_VERSION
    assert artifact.checksum == "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102"
    assert "CREATE TABLE document__p7_new" in artifact.sql
    assert "BEGIN IMMEDIATE" in artifact.sql
