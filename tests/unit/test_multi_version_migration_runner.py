from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import (
    LEDGER_TABLE,
    MIGRATION_001_SHA256,
    MIGRATION_002_SHA256,
    MigrationChecksumMismatch,
    MigrationNotAllowed,
    MigrationOrderError,
    MigrationRegistry,
    MigrationRegistryError,
    MigrationSpec,
    apply_migrations,
    migration_registry,
)

MIGRATION_001 = Path("database/migrations/001_document_sha256_check.sql")


def _write_migration(path: Path, sql: str) -> str:
    path.write_text(sql, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _spec(path: Path, version: str, order: int) -> MigrationSpec:
    return MigrationSpec(
        version=version,
        name=f"synthetic-{version}",
        order=order,
        path=path,
        checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    database = tmp_path / "migration-runner.sqlite"
    opened = sqlite3.connect(database, isolation_level=None)
    opened.execute(
        "CREATE TABLE document(id TEXT PRIMARY KEY, title TEXT NOT NULL)"
    )
    opened.execute("INSERT INTO document(id, title) VALUES ('seed', 'seed')")
    try:
        yield opened
    finally:
        opened.close()


def test_approved_registry_discovers_immutable_001_and_002() -> None:
    registry = migration_registry(MIGRATION_001)

    assert registry.versions == ("001", "002")
    first, second = registry.load_artifacts()
    assert (first.version, first.order, first.checksum, first.applicable) == (
        "001",
        1,
        MIGRATION_001_SHA256,
        True,
    )
    assert (second.version, second.order, second.checksum, second.applicable) == (
        "002",
        2,
        MIGRATION_002_SHA256,
        True,
    )


def test_registry_sorts_multiple_migrations_before_execution(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    first = tmp_path / "001.sql"
    second = tmp_path / "002.sql"
    _write_migration(first, "CREATE TABLE first_marker(id INTEGER);\n")
    _write_migration(
        second,
        "INSERT INTO first_marker(id) VALUES (1);\n"
        "CREATE TABLE second_marker(id INTEGER);\n",
    )
    registry = MigrationRegistry((_spec(second, "002", 2), _spec(first, "001", 1)))

    result = apply_migrations(connection, registry)

    assert registry.versions == ("001", "002")
    assert result.applied == ("001", "002")
    assert result.skipped == ()
    assert connection.execute("SELECT count(*) FROM first_marker").fetchone()[0] == 1


def test_registry_rejects_duplicate_version(tmp_path: Path) -> None:
    first = tmp_path / "first.sql"
    second = tmp_path / "second.sql"
    _write_migration(first, "SELECT 1;\n")
    _write_migration(second, "SELECT 2;\n")

    with pytest.raises(MigrationRegistryError, match="duplicate migration version"):
        MigrationRegistry((_spec(first, "001", 1), _spec(second, "001", 2)))


def test_registry_rejects_invalid_identifier(tmp_path: Path) -> None:
    migration = tmp_path / "invalid.sql"
    _write_migration(migration, "SELECT 1;\n")

    with pytest.raises(MigrationRegistryError, match="invalid migration version"):
        MigrationRegistry((_spec(migration, "version-one", 1),))


@pytest.mark.parametrize(
    ("versions", "orders", "message"),
    [
        (("001", "002"), (1, 3), "order must be contiguous"),
        (("001", "003"), (1, 2), "versions must be contiguous"),
    ],
)
def test_registry_rejects_order_or_version_gap(
    tmp_path: Path,
    versions: tuple[str, str],
    orders: tuple[int, int],
    message: str,
) -> None:
    first = tmp_path / "first.sql"
    second = tmp_path / "second.sql"
    _write_migration(first, "SELECT 1;\n")
    _write_migration(second, "SELECT 2;\n")

    with pytest.raises(MigrationOrderError, match=message):
        MigrationRegistry(
            (
                _spec(first, versions[0], orders[0]),
                _spec(second, versions[1], orders[1]),
            )
        )


def test_registry_checksum_mismatch_fails_before_ledger_write(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    migration = tmp_path / "001.sql"
    _write_migration(migration, "CREATE TABLE marker(id INTEGER);\n")
    invalid = MigrationSpec(
        version="001",
        name="invalid-checksum",
        order=1,
        path=migration,
        checksum="0" * 64,
    )

    with pytest.raises(MigrationChecksumMismatch, match="001"):
        apply_migrations(connection, MigrationRegistry((invalid,)))

    assert (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (LEDGER_TABLE,),
        ).fetchone()
        is None
    )


def test_applied_identical_migrations_are_skipped_idempotently(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    migration = tmp_path / "001.sql"
    _write_migration(migration, "CREATE TABLE marker(id INTEGER);\n")
    registry = MigrationRegistry((_spec(migration, "001", 1),))

    first = apply_migrations(connection, registry)
    history_before = connection.execute(
        f"SELECT version, checksum, applied_at FROM {LEDGER_TABLE}"
    ).fetchall()
    second = apply_migrations(connection, registry)

    assert first.applied == ("001",)
    assert second.applied == ()
    assert second.skipped == ("001",)
    assert connection.execute(
        f"SELECT version, checksum, applied_at FROM {LEDGER_TABLE}"
    ).fetchall() == history_before


def test_applied_checksum_mismatch_is_fail_closed(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    migration = tmp_path / "001.sql"
    _write_migration(migration, "CREATE TABLE marker(id INTEGER);\n")
    registry = MigrationRegistry((_spec(migration, "001", 1),))
    apply_migrations(connection, registry)
    connection.execute(
        f"UPDATE {LEDGER_TABLE} SET checksum = ? WHERE version = '001'",
        ("f" * 64,),
    )

    with pytest.raises(MigrationChecksumMismatch, match="001"):
        apply_migrations(connection, registry)


def test_failure_rolls_back_and_stops_before_later_migration(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    first = tmp_path / "001.sql"
    failing = tmp_path / "002.sql"
    later = tmp_path / "003.sql"
    _write_migration(first, "CREATE TABLE first_marker(id INTEGER);\n")
    _write_migration(
        failing,
        "CREATE TABLE failed_marker(id INTEGER);\n"
        "INSERT INTO missing_table(id) VALUES (1);\n",
    )
    _write_migration(later, "CREATE TABLE later_marker(id INTEGER);\n")
    registry = MigrationRegistry(
        (
            _spec(first, "001", 1),
            _spec(failing, "002", 2),
            _spec(later, "003", 3),
        )
    )

    with pytest.raises(sqlite3.OperationalError, match="missing_table"):
        apply_migrations(connection, registry)

    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "first_marker" in tables
    assert "failed_marker" not in tables
    assert "later_marker" not in tables
    assert connection.execute(
        f"SELECT version FROM {LEDGER_TABLE} ORDER BY version"
    ).fetchall() == [("001",)]


def test_history_gap_is_rejected_before_missing_migration_runs(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    first = tmp_path / "001.sql"
    second = tmp_path / "002.sql"
    _write_migration(first, "CREATE TABLE first_marker(id INTEGER);\n")
    _write_migration(second, "CREATE TABLE second_marker(id INTEGER);\n")
    registry = MigrationRegistry((_spec(first, "001", 1), _spec(second, "002", 2)))
    connection.execute(
        f"CREATE TABLE {LEDGER_TABLE}("
        "version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    connection.execute(
        f"INSERT INTO {LEDGER_TABLE}(version, checksum, applied_at) "
        "VALUES ('002', ?, datetime('now'))",
        (registry.specs[1].checksum,),
    )

    with pytest.raises(MigrationOrderError, match="ordered prefix"):
        apply_migrations(connection, registry)

    assert "first_marker" not in {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def test_unknown_history_version_is_rejected(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    migration = tmp_path / "001.sql"
    _write_migration(migration, "CREATE TABLE marker(id INTEGER);\n")
    registry = MigrationRegistry((_spec(migration, "001", 1),))
    apply_migrations(connection, registry)
    connection.execute(
        f"INSERT INTO {LEDGER_TABLE}(version, checksum, applied_at) "
        "VALUES ('999', ?, datetime('now'))",
        ("9" * 64,),
    )

    with pytest.raises(MigrationNotAllowed, match="unregistered version 999"):
        apply_migrations(connection, registry)


def test_registered_non_applicable_migration_is_not_executed(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    migration = tmp_path / "001.sql"
    _write_migration(migration, "CREATE TABLE forbidden_marker(id INTEGER);\n")
    spec = _spec(migration, "001", 1)
    deferred = MigrationSpec(
        version=spec.version,
        name=spec.name,
        order=spec.order,
        path=spec.path,
        checksum=spec.checksum,
        applicable=False,
    )

    with pytest.raises(MigrationNotAllowed, match="not applicable"):
        apply_migrations(connection, MigrationRegistry((deferred,)))

    assert "forbidden_marker" not in {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
