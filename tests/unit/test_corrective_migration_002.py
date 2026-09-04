from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import (
    DOCUMENT_INVARIANTS_POSTCONDITION,
    LEDGER_TABLE,
    MIGRATION_001_SHA256,
    MIGRATION_002_NAME,
    MIGRATION_002_SHA256,
    MigrationChecksumMismatch,
    MigrationRegistry,
    MigrationSpec,
    apply_migrations,
    migration_registry,
)

MIGRATION_001 = Path("database/migrations/001_document_sha256_check.sql")
MIGRATION_002 = Path("database/migrations/002_restore_document_invariants.sql")


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    database = tmp_path / "b03.sqlite"
    opened = sqlite3.connect(database, isolation_level=None)
    opened.execute("PRAGMA foreign_keys = ON")
    opened.executescript(
        """
        CREATE TABLE document (
            id TEXT PRIMARY KEY,
            document_type TEXT NOT NULL DEFAULT 'OTHER',
            title TEXT NOT NULL,
            file_name TEXT,
            mime_type TEXT,
            publication_date TEXT,
            accessed_at TEXT,
            url TEXT,
            size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
            sha256 TEXT,
            storage_uri TEXT,
            language_code TEXT NOT NULL DEFAULT 'fr',
            license_code TEXT,
            document_status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_document_sha256 ON document(sha256);
        CREATE INDEX idx_document_url ON document(url);
        CREATE TABLE document_link (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES document(id)
        );
        INSERT INTO document(id, title, size_bytes)
        VALUES ('document:one', 'one', 1), ('document:two', 'two', 2);
        INSERT INTO document_link(id, document_id)
        VALUES ('link:one', 'document:one');
        """
    )
    try:
        yield opened
    finally:
        opened.close()


def _full_registry() -> MigrationRegistry:
    return migration_registry(MIGRATION_001)


def _ledger(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    return [
        (str(row[0]), str(row[1]))
        for row in connection.execute(
            f"SELECT version, checksum FROM {LEDGER_TABLE} ORDER BY version"
        ).fetchall()
    ]


def _assert_target_schema(connection: sqlite3.Connection) -> None:
    defaults = {
        str(row[1]): row[4]
        for row in connection.execute("PRAGMA table_info(document)").fetchall()
    }
    assert defaults["document_type"] == "'OTHER'"
    assert defaults["language_code"] == "'fr'"
    assert defaults["document_status"] == "'ACTIVE'"
    assert defaults["created_at"] == "CURRENT_TIMESTAMP"

    table_sql = str(
        connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='document'"
        ).fetchone()[0]
    )
    normalized = " ".join(table_sql.split())
    assert "size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0)" in normalized
    assert "length(sha256) = 64" in normalized
    assert "sha256 NOT GLOB '*[^0-9A-Fa-f]*'" in normalized

    indexes = {
        str(row[1]) for row in connection.execute("PRAGMA index_list(document)")
    }
    assert {"idx_document_sha256", "idx_document_url"} <= indexes
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_fresh_seed_applies_001_then_002_and_preserves_rows(
    connection: sqlite3.Connection,
) -> None:
    before_ids = connection.execute("SELECT id FROM document ORDER BY id").fetchall()

    result = apply_migrations(connection, _full_registry())

    assert result.applied == ("001", "002")
    assert result.skipped == ()
    assert _ledger(connection) == [
        ("001", MIGRATION_001_SHA256),
        ("002", MIGRATION_002_SHA256),
    ]
    assert connection.execute("SELECT id FROM document ORDER BY id").fetchall() == before_ids
    assert connection.execute("SELECT count(*) FROM document_link").fetchone()[0] == 1
    _assert_target_schema(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO document(id, title, size_bytes) VALUES ('negative', 'x', -1)"
        )
    connection.execute("INSERT INTO document(id, title) VALUES ('defaults', 'x')")
    assert connection.execute(
        "SELECT document_type, language_code, document_status, created_at "
        "FROM document WHERE id='defaults'"
    ).fetchone()[:3] == ("OTHER", "fr", "ACTIVE")


def test_existing_001_applies_only_002(connection: sqlite3.Connection) -> None:
    full = _full_registry()
    first_only = MigrationRegistry((full.specs[0],))
    apply_migrations(connection, first_only)

    post_001_columns = {
        str(row[1]): row[4]
        for row in connection.execute("PRAGMA table_info(document)").fetchall()
    }
    assert post_001_columns["document_type"] is None
    assert "size_bytes >= 0" not in str(
        connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='document'"
        ).fetchone()[0]
    )

    result = apply_migrations(connection, full)

    assert result.applied == ("002",)
    assert result.skipped == ("001",)
    _assert_target_schema(connection)


def test_complete_runtime_replay_is_noop(connection: sqlite3.Connection) -> None:
    registry = _full_registry()
    apply_migrations(connection, registry)
    history_before = connection.execute(
        f"SELECT version, checksum, applied_at FROM {LEDGER_TABLE} ORDER BY version"
    ).fetchall()
    ids_before = connection.execute("SELECT id FROM document ORDER BY id").fetchall()

    replay = apply_migrations(connection, registry)

    assert replay.applied == ()
    assert replay.skipped == ("001", "002")
    assert connection.execute(
        f"SELECT version, checksum, applied_at FROM {LEDGER_TABLE} ORDER BY version"
    ).fetchall() == history_before
    assert connection.execute("SELECT id FROM document ORDER BY id").fetchall() == ids_before


def test_applied_002_checksum_mismatch_is_fail_closed(
    connection: sqlite3.Connection,
) -> None:
    registry = _full_registry()
    apply_migrations(connection, registry)
    connection.execute(
        f"UPDATE {LEDGER_TABLE} SET checksum=? WHERE version='002'", ("f" * 64,)
    )

    with pytest.raises(MigrationChecksumMismatch, match="002"):
        apply_migrations(connection, registry)


def test_failing_002_rebuild_rolls_back_and_does_not_mark_success(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    full = _full_registry()
    first_only = MigrationRegistry((full.specs[0],))
    apply_migrations(connection, first_only)
    original_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='document'"
    ).fetchone()[0]
    original_ids = connection.execute("SELECT id FROM document ORDER BY id").fetchall()

    failing_path = tmp_path / "002_failing.sql"
    failing_path.write_text(
        MIGRATION_002.read_text(encoding="utf-8").replace(
            "DROP TABLE document;",
            "INSERT INTO missing_b03_table(id) VALUES (1);\n\nDROP TABLE document;",
        ),
        encoding="utf-8",
    )
    failing_spec = MigrationSpec(
        version="002",
        name=MIGRATION_002_NAME,
        order=2,
        path=failing_path,
        checksum=hashlib.sha256(failing_path.read_bytes()).hexdigest(),
        postcondition=DOCUMENT_INVARIANTS_POSTCONDITION,
    )

    with pytest.raises(sqlite3.OperationalError, match="missing_b03_table"):
        apply_migrations(connection, MigrationRegistry((full.specs[0], failing_spec)))

    assert _ledger(connection) == [("001", MIGRATION_001_SHA256)]
    assert connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='document'"
    ).fetchone()[0] == original_sql
    assert connection.execute("SELECT id FROM document ORDER BY id").fetchall() == original_ids
    assert connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='document__p12_17_05b_new'"
    ).fetchone() is None
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
