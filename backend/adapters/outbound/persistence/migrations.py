"""Authenticated seed, atomic runtime lifecycle, migrations, and backups."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from backend.adapters.outbound.persistence.sqlite import connect_sqlite

CANONICAL_SEED_SIZE = 105_553_920
CANONICAL_SEED_SHA256 = "38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134"
CANONICAL_SEED_TABLES = 98
CANONICAL_SEED_EXPLICIT_INDEXES = 20
CANONICAL_SEED_TRIGGERS = 7
CANONICAL_SEED_VIEWS = 2
MIGRATION_VERSION = "001"
MIGRATION_001_SHA256 = "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102"
APPROVED_RUNTIME_MIGRATIONS: Mapping[str, str] = MappingProxyType(
    {MIGRATION_VERSION: MIGRATION_001_SHA256}
)
DEFERRED_UNKNOWN_MIGRATIONS = (
    "resource.active-canonical",
    "pedagogical-context.origin",
)
LEDGER_TABLE = "_runtime_migration_ledger"
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


class SeedAuthenticationError(RuntimeError):
    pass


class SeedMutationDetected(RuntimeError):
    pass


class MigrationChecksumMismatch(RuntimeError):
    pass


class MigrationNotAllowed(RuntimeError):
    pass


class RuntimeProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FileEvidence:
    exists: bool
    size_bytes: int | None
    mtime_ns: int | None
    sha256: str | None
    device: int | None
    inode: int | None


@dataclass(frozen=True, slots=True)
class SQLiteFileSetSnapshot:
    main: FileEvidence
    wal: FileEvidence
    shm: FileEvidence
    journal: FileEvidence


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
        return cls(
            MIGRATION_VERSION,
            path,
            hashlib.sha256(raw).hexdigest(),
            raw.decode("utf-8"),
        )


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
    runtime_created: bool
    runtime_existing: bool
    journal_mode: str
    seed_pre_snapshot: SQLiteFileSetSnapshot
    seed_post_snapshot: SQLiteFileSetSnapshot
    runtime_pre_snapshot: SQLiteFileSetSnapshot
    runtime_active_snapshot: SQLiteFileSetSnapshot
    runtime_post_snapshot: SQLiteFileSetSnapshot
    seed_sidecar_created_by_b08: bool
    runtime_sidecars_observed: tuple[str, ...]
    deferred_migrations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeBackupReport:
    runtime_sha256: str
    backup_sha256: str
    migration_version: str
    manifest_sha256: str
    created_at: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_evidence(path: Path) -> FileEvidence:
    if not path.is_file():
        return FileEvidence(False, None, None, None, None, None)
    stat = path.stat()
    return FileEvidence(
        True,
        stat.st_size,
        stat.st_mtime_ns,
        _sha256(path),
        stat.st_dev,
        stat.st_ino,
    )


def snapshot_sqlite_files(path: Path) -> SQLiteFileSetSnapshot:
    """Capture main DB and every SQLite sidecar before opening a connection."""

    return SQLiteFileSetSnapshot(
        main=_file_evidence(path),
        wal=_file_evidence(Path(f"{path}-wal")),
        shm=_file_evidence(Path(f"{path}-shm")),
        journal=_file_evidence(Path(f"{path}-journal")),
    )


def inspect_database(path: Path, *, authenticate_seed: bool = False) -> DatabaseEvidence:
    snapshot = snapshot_sqlite_files(path)
    if not snapshot.main.exists:
        if authenticate_seed:
            raise SeedAuthenticationError("canonical seed is missing")
        raise RuntimeProvisioningError("runtime database is missing")
    assert snapshot.main.size_bytes is not None
    assert snapshot.main.sha256 is not None
    with closing(
        connect_sqlite(path, readonly=True, immutable=authenticate_seed)
    ) as connection:
        evidence = DatabaseEvidence(
            snapshot.main.size_bytes,
            snapshot.main.sha256,
            int(
                connection.execute(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE '_runtime_%'"
                ).fetchone()[0]
            ),
            int(
                connection.execute(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type='index' AND sql IS NOT NULL"
                ).fetchone()[0]
            ),
            int(
                connection.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='trigger'"
                ).fetchone()[0]
            ),
            int(
                connection.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='view'"
                ).fetchone()[0]
            ),
            str(connection.execute("PRAGMA integrity_check").fetchone()[0]),
            str(connection.execute("PRAGMA quick_check").fetchone()[0]),
            len(connection.execute("PRAGMA foreign_key_check").fetchall()),
        )
    expected = DatabaseEvidence(
        CANONICAL_SEED_SIZE,
        CANONICAL_SEED_SHA256,
        CANONICAL_SEED_TABLES,
        CANONICAL_SEED_EXPLICIT_INDEXES,
        CANONICAL_SEED_TRIGGERS,
        CANONICAL_SEED_VIEWS,
        "ok",
        "ok",
        0,
    )
    if authenticate_seed and evidence != expected:
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
    lines = [
        line for line in statement.splitlines() if not line.lstrip().startswith("--")
    ]
    return " ".join(lines).strip().upper()


def _assert_sha_constraint(connection: sqlite3.Connection) -> None:
    connection.execute("SAVEPOINT c0_sha_invalid")
    rejected = False
    try:
        connection.execute(
            "INSERT INTO document(id, document_type, title, sha256, "
            "language_code, document_status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
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
            "INSERT INTO document(id, document_type, title, sha256, "
            "language_code, document_status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
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

    documents_before = int(
        connection.execute("SELECT count(*) FROM document").fetchone()[0]
    )
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
        if (
            int(connection.execute("SELECT count(*) FROM document").fetchone()[0])
            != documents_before
        ):
            raise RuntimeProvisioningError("document count changed during migration")
        _assert_sha_constraint(connection)
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeProvisioningError("foreign key check failed during migration")
        connection.execute(
            f"INSERT INTO {LEDGER_TABLE}(version, checksum, applied_at) "
            "VALUES (?, ?, datetime('now'))",
            (artifact.version, artifact.checksum),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
    return True


def _assert_migration_allowed(artifact: MigrationArtifact) -> None:
    expected = APPROVED_RUNTIME_MIGRATIONS.get(artifact.version)
    if expected is None or expected != artifact.checksum:
        raise MigrationNotAllowed("runtime migration is not allowlisted")


def _assert_distinct(left: Path, right: Path) -> None:
    try:
        if left.resolve(strict=False) == right.resolve(strict=False):
            raise RuntimeProvisioningError("SQLite file identities must be distinct")
        if left.exists() and right.exists() and os.path.samefile(left, right):
            raise RuntimeProvisioningError("SQLite file identities must be distinct")
    except OSError as error:
        raise RuntimeProvisioningError("SQLite file identity check failed") from error


def _assert_runtime_compatible(evidence: DatabaseEvidence) -> None:
    actual = (
        evidence.tables,
        evidence.explicit_indexes,
        evidence.triggers,
        evidence.views,
    )
    expected = (
        CANONICAL_SEED_TABLES,
        CANONICAL_SEED_EXPLICIT_INDEXES,
        CANONICAL_SEED_TRIGGERS,
        CANONICAL_SEED_VIEWS,
    )
    if actual != expected:
        raise RuntimeProvisioningError("runtime schema inventory mismatch")
    if evidence.integrity != "ok" or evidence.quick != "ok":
        raise RuntimeProvisioningError("runtime integrity checks failed")
    if evidence.foreign_key_violations:
        raise RuntimeProvisioningError("runtime foreign key check failed")


def _assert_runtime_writable(connection: sqlite3.Connection) -> None:
    connection.execute("SAVEPOINT b08_runtime_write_probe")
    try:
        connection.execute("CREATE TABLE _b08_runtime_write_probe(id INTEGER)")
    finally:
        connection.execute("ROLLBACK TO b08_runtime_write_probe")
        connection.execute("RELEASE b08_runtime_write_probe")


def _open_and_migrate(
    path: Path, artifact: MigrationArtifact
) -> tuple[int, int, bool, str, SQLiteFileSetSnapshot]:
    with closing(connect_sqlite(path)) as connection:
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        documents_before = int(
            connection.execute("SELECT count(*) FROM document").fetchone()[0]
        )
        applied = apply_migration(connection, artifact)
        documents_after = int(
            connection.execute("SELECT count(*) FROM document").fetchone()[0]
        )
        _assert_runtime_writable(connection)
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        active_snapshot = snapshot_sqlite_files(path)
    return (
        documents_before,
        documents_after,
        applied,
        journal_mode,
        active_snapshot,
    )


def _existing_migration_is_current(path: Path, artifact: MigrationArtifact) -> bool:
    with closing(connect_sqlite(path, readonly=True)) as connection:
        ledger_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (LEDGER_TABLE,),
        ).fetchone()
        if ledger_exists is None:
            return False
        existing = connection.execute(
            f"SELECT checksum FROM {LEDGER_TABLE} WHERE version = ?",
            (artifact.version,),
        ).fetchone()
        if existing is None:
            return False
        if str(existing[0]) != artifact.checksum:
            raise MigrationChecksumMismatch(artifact.version)
        return True


def _temporary_path(parent: Path, *, prefix: str) -> Path:
    descriptor, raw_path = tempfile.mkstemp(dir=parent, prefix=prefix, suffix=".tmp")
    os.close(descriptor)
    return Path(raw_path)


def _remove_fresh_file_set(path: Path) -> None:
    path.unlink(missing_ok=True)
    for suffix in SIDECAR_SUFFIXES:
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _publish_fresh(source: Path, destination: Path) -> None:
    """Atomically publish without an overwrite window, then remove the temp name."""

    try:
        os.link(source, destination)
    except FileExistsError as error:
        raise RuntimeProvisioningError("publication destination already exists") from error
    except OSError as error:
        raise RuntimeProvisioningError("atomic publication failed") from error
    try:
        source.unlink()
    except OSError as error:
        destination.unlink(missing_ok=True)
        raise RuntimeProvisioningError("atomic publication cleanup failed") from error


def _observed_sidecars(snapshot: SQLiteFileSetSnapshot) -> tuple[str, ...]:
    return tuple(
        suffix
        for suffix, evidence in (
            ("wal", snapshot.wal),
            ("shm", snapshot.shm),
            ("journal", snapshot.journal),
        )
        if evidence.exists
    )


def provision_runtime(
    seed_path: Path, runtime_path: Path, migration_path: Path
) -> RuntimeProvisioningReport:
    """Authenticate a seed and idempotently establish its distinct runtime."""

    seed_pre = snapshot_sqlite_files(seed_path)
    if not seed_pre.main.exists:
        raise SeedAuthenticationError("canonical seed is missing")
    _assert_distinct(seed_path, runtime_path)
    seed = inspect_database(seed_path, authenticate_seed=True)
    artifact = MigrationArtifact.load(migration_path)
    _assert_migration_allowed(artifact)

    runtime_pre = snapshot_sqlite_files(runtime_path)
    runtime_created = not runtime_pre.main.exists
    runtime_existing = runtime_pre.main.exists
    temporary: Path | None = None
    published_fresh = False
    working_path = runtime_path
    seed_post = seed_pre

    try:
        if runtime_existing:
            _assert_runtime_compatible(inspect_database(runtime_path))
        else:
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = _temporary_path(
                runtime_path.parent, prefix=".projet-v2-runtime-"
            )
            shutil.copy2(seed_path, temporary)
            copied = snapshot_sqlite_files(temporary)
            if (
                copied.main.size_bytes != seed_pre.main.size_bytes
                or copied.main.sha256 != seed_pre.main.sha256
            ):
                raise RuntimeProvisioningError("runtime copy authentication failed")
            working_path = temporary

        if runtime_existing and _existing_migration_is_current(
            working_path, artifact
        ):
            with closing(connect_sqlite(working_path, readonly=True)) as connection:
                documents_before = documents_after = int(
                    connection.execute("SELECT count(*) FROM document").fetchone()[0]
                )
                journal_mode = str(
                    connection.execute("PRAGMA journal_mode").fetchone()[0]
                )
            applied = False
            runtime_active = runtime_pre
        else:
            (
                documents_before,
                documents_after,
                applied,
                journal_mode,
                runtime_active,
            ) = _open_and_migrate(working_path, artifact)
        _assert_runtime_compatible(inspect_database(working_path))

        if runtime_created:
            assert temporary is not None
            _publish_fresh(temporary, runtime_path)
            published_fresh = True
            temporary = None

        runtime = inspect_database(runtime_path)
        _assert_runtime_compatible(runtime)
        runtime_post = snapshot_sqlite_files(runtime_path)
        seed_post = snapshot_sqlite_files(seed_path)
        if seed_post != seed_pre:
            raise SeedMutationDetected("canonical seed or sidecar changed")

        return RuntimeProvisioningReport(
            seed=seed,
            runtime_sha256=runtime.sha256,
            migration_version=artifact.version,
            migration_checksum=artifact.checksum,
            migration_applied=applied,
            documents_before=documents_before,
            documents_after=documents_after,
            domain_tables=runtime.tables,
            explicit_indexes=runtime.explicit_indexes,
            triggers=runtime.triggers,
            views=runtime.views,
            runtime_created=runtime_created,
            runtime_existing=runtime_existing,
            journal_mode=journal_mode,
            seed_pre_snapshot=seed_pre,
            seed_post_snapshot=seed_post,
            runtime_pre_snapshot=runtime_pre,
            runtime_active_snapshot=runtime_active,
            runtime_post_snapshot=runtime_post,
            seed_sidecar_created_by_b08=False,
            runtime_sidecars_observed=_observed_sidecars(runtime_active),
            deferred_migrations=DEFERRED_UNKNOWN_MIGRATIONS,
        )
    except BaseException:
        if temporary is not None:
            _remove_fresh_file_set(temporary)
        if runtime_created and published_fresh:
            _remove_fresh_file_set(runtime_path)
        raise
    finally:
        final_seed_snapshot = snapshot_sqlite_files(seed_path)
        if final_seed_snapshot != seed_pre:
            raise SeedMutationDetected("canonical seed or sidecar changed")


def _manifest_path(backup_path: Path) -> Path:
    return backup_path.with_name(f"{backup_path.name}.manifest.json")


def create_runtime_backup(
    runtime_path: Path,
    backup_path: Path,
    *,
    migration_version: str = MIGRATION_VERSION,
) -> RuntimeBackupReport:
    """Checkpoint and atomically publish a self-authenticating runtime backup."""

    _assert_distinct(runtime_path, backup_path)
    if backup_path.exists() or _manifest_path(backup_path).exists():
        raise RuntimeProvisioningError("backup destination already exists")
    runtime = inspect_database(runtime_path)
    _assert_runtime_compatible(runtime)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(backup_path.parent, prefix=".projet-v2-backup-")
    manifest_temporary = _temporary_path(
        backup_path.parent, prefix=".projet-v2-backup-manifest-"
    )
    backup_published = False
    try:
        with closing(connect_sqlite(runtime_path)) as source:
            source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            with closing(sqlite3.connect(temporary)) as destination:
                source.backup(destination)
        backup = inspect_database(temporary)
        _assert_runtime_compatible(backup)
        created_at = datetime.now(UTC).isoformat()
        payload = {
            "schema_version": "runtime-backup-v1",
            "runtime_sha256": inspect_database(runtime_path).sha256,
            "backup_sha256": backup.sha256,
            "migration_version": migration_version,
            "created_at": created_at,
        }
        manifest_temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _publish_fresh(temporary, backup_path)
        backup_published = True
        _publish_fresh(manifest_temporary, _manifest_path(backup_path))
        return RuntimeBackupReport(
            runtime_sha256=payload["runtime_sha256"],
            backup_sha256=backup.sha256,
            migration_version=migration_version,
            manifest_sha256=_sha256(_manifest_path(backup_path)),
            created_at=created_at,
        )
    except BaseException:
        _remove_fresh_file_set(temporary)
        manifest_temporary.unlink(missing_ok=True)
        if backup_published:
            backup_path.unlink(missing_ok=True)
        raise


def restore_runtime_backup(
    backup_path: Path,
    target_path: Path,
    *,
    canonical_seed_path: Path,
) -> DatabaseEvidence:
    """Restore a verified backup to a fresh non-seed target."""

    _assert_distinct(canonical_seed_path, target_path)
    _assert_distinct(backup_path, target_path)
    if target_path.exists():
        raise RuntimeProvisioningError("restore destination already exists")
    manifest_path = _manifest_path(backup_path)
    try:
        payload = cast(
            dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
        )
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise RuntimeProvisioningError("backup manifest is invalid") from error
    if payload.get("backup_sha256") != _sha256(backup_path):
        raise RuntimeProvisioningError("backup authentication failed")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target_path.parent, prefix=".projet-v2-restore-")
    published = False
    try:
        shutil.copy2(backup_path, temporary)
        if _sha256(temporary) != payload["backup_sha256"]:
            raise RuntimeProvisioningError("restored copy authentication failed")
        restored = inspect_database(temporary)
        _assert_runtime_compatible(restored)
        _publish_fresh(temporary, target_path)
        published = True
        return inspect_database(target_path)
    except BaseException:
        _remove_fresh_file_set(temporary)
        if published:
            _remove_fresh_file_set(target_path)
        raise
