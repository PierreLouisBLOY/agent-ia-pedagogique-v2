"""Deterministic seed authentication and runtime migration provisioning."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from backend.adapters.outbound.persistence.sqlite import connect_sqlite

CANONICAL_SEED_SIZE = 105_553_920
CANONICAL_SEED_SHA256 = "38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134"
MIGRATION_VERSION = "001"
LEDGER_TABLE = "_runtime_migration_ledger"


class SeedAuthenticationError(RuntimeError):
    pass


class MigrationChecksumMismatch(RuntimeError):
    pass


class RuntimeProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DatabaseEvidence:
    size_bytes: int
    sha256: str
    tables: int
    explicit_indexes: int
    triggers: int
    views: int
    integrity: str
    quick: str
    foreign_key_violations: int


@dataclass(frozen=True, slots=True)
class MigrationArtifact:
    version: str
    path: Path
    checksum: str
    sql: str

    @classmethod
    def load(cls, path: Path) -> MigrationArtifact:
        raw = path.read_bytes()
        return cls(MIGRATION_VERSION, path, hashlib.sha256(raw).hexdigest(), raw.decode("utf-8"))


@dataclass(frozen=True, slots=True)
class RuntimeProvisioningReport:
    seed: DatabaseEvidence
    runtime_sha256: str
    migration_version: str
    migration_checksum: str
    migration_applied: bool
    documents_before: int
    documents_after: int
    domain_tables: int
    explicit_indexes: int
    triggers: int
    views: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_database(path: Path, *, authenticate_seed: bool = False) -> DatabaseEvidence:
    size = path.stat().st_size
    digest = _sha256(path)
    with closing(connect_sqlite(path, readonly=True)) as connection:
        evidence = DatabaseEvidence(
            size,
            digest,
            int(connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE '_runtime_%'").fetchone()[0]),
            int(connection.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchone()[0]),
            int(connection.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0]),
            int(connection.execute("SELECT count(*) FROM sqlite_master WHERE type='view'").fetchone()[0]),
            str(connection.execute("PRAGMA integrity_check").fetchone()[0]),
            str(connection.execute("PRAGMA quick_check").fetchone()[0]),
            len(connection.execute("PRAGMA foreign_key_check").fetchall()),
        )
    if authenticate_seed and evidence != DatabaseEvidence(
        CANONICAL_SEED_SIZE, CANONICAL_SEED_SHA256, 98, 20, 7, 2, "ok", "ok", 0
    ):
        raise SeedAuthenticationError("canonical seed evidence mismatch")
    return evidence


def _statements(sql: str) -> tuple[str, ...]:
    statements: list[str] = []
    current = ""
    for line in sql.splitlines(keepends=True):
        current += line
        if sqlite3.complete_statement(current):
            statements.append(current.strip())
            current = ""
    if current.strip():
        raise RuntimeProvisioningError("incomplete migration SQL")
    return tuple(statements)


def _keyword(statement: str) -> str:
    lines = [line for line in statement.splitlines() if not line.lstrip().startswith("--")]
    return " ".join(lines).strip().upper()


def _assert_sha_constraint(connection: sqlite3.Connection) -> None:
    connection.execute("SAVEPOINT c0_sha_invalid")
    rejected = False
    try:
        connection.execute(
            "INSERT INTO document(id, document_type, title, sha256, language_code, document_status, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            ("c0:invalid-sha", "OTHER", "invalid", "badsha", "fr", "ACTIVE"),
        )
    except sqlite3.IntegrityError:
        rejected = True
    finally:
        connection.execute("ROLLBACK TO c0_sha_invalid")
        connection.execute("RELEASE c0_sha_invalid")
    if not rejected:
        raise RuntimeProvisioningError("migration did not reject invalid sha256")

    connection.execute("SAVEPOINT c0_sha_valid")
    try:
        connection.execute(
            "INSERT INTO document(id, document_type, title, sha256, language_code, document_status, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            ("c0:valid-sha", "OTHER", "valid", "a" * 64, "fr", "ACTIVE"),
        )
    finally:
        connection.execute("ROLLBACK TO c0_sha_valid")
        connection.execute("RELEASE c0_sha_valid")


def apply_migration(connection: sqlite3.Connection, artifact: MigrationArtifact) -> bool:
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
               version TEXT PRIMARY KEY,
               checksum TEXT NOT NULL,
               applied_at TEXT NOT NULL
           )"""
    )
    existing = connection.execute(
        f"SELECT checksum FROM {LEDGER_TABLE} WHERE version = ?", (artifact.version,)
    ).fetchone()
    if existing is not None:
        if str(existing[0]) != artifact.checksum:
            raise MigrationChecksumMismatch(artifact.version)
        _assert_sha_constraint(connection)
        return False

    documents_before = int(connection.execute("SELECT count(*) FROM document").fetchone()[0])
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in _statements(artifact.sql):
            keyword = _keyword(statement)
            if keyword.startswith("PRAGMA FOREIGN_KEYS") or keyword in {
                "BEGIN IMMEDIATE;",
                "COMMIT;",
            }:
                continue
            connection.execute(statement)
        if int(connection.execute("SELECT count(*) FROM document").fetchone()[0]) != documents_before:
            raise RuntimeProvisioningError("document count changed during migration")
        _assert_sha_constraint(connection)
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeProvisioningError("foreign key check failed during migration")
        connection.execute(
            f"INSERT INTO {LEDGER_TABLE}(version, checksum, applied_at) VALUES (?, ?, datetime('now'))",
            (artifact.version, artifact.checksum),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
    return True


def provision_runtime(
    seed_path: Path, runtime_path: Path, migration_path: Path
) -> RuntimeProvisioningReport:
    seed = inspect_database(seed_path, authenticate_seed=True)
    if seed_path.resolve() == runtime_path.resolve():
        raise RuntimeProvisioningError("runtime path must differ from canonical seed")
    if runtime_path.exists():
        raise RuntimeProvisioningError("runtime database already exists")
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed_path, runtime_path)
    artifact = MigrationArtifact.load(migration_path)
    try:
        with closing(connect_sqlite(runtime_path)) as connection:
            documents_before = int(connection.execute("SELECT count(*) FROM document").fetchone()[0])
            applied = apply_migration(connection, artifact)
            documents_after = int(connection.execute("SELECT count(*) FROM document").fetchone()[0])
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        runtime = inspect_database(runtime_path)
        if runtime.integrity != "ok" or runtime.quick != "ok" or runtime.foreign_key_violations:
            raise RuntimeProvisioningError("runtime postchecks failed")
        return RuntimeProvisioningReport(
            seed,
            runtime.sha256,
            artifact.version,
            artifact.checksum,
            applied,
            documents_before,
            documents_after,
            runtime.tables,
            runtime.explicit_indexes,
            runtime.triggers,
            runtime.views,
        )
    except BaseException:
        runtime_path.unlink(missing_ok=True)
        raise
