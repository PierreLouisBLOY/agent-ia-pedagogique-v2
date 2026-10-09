"""Closed persistence cycle for the reviewed PR4 SQL successor."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
from contextlib import ExitStack, closing
from dataclasses import asdict
from pathlib import Path
from typing import Literal, cast

from backend.adapters.outbound.persistence.runtime_schema_inspection import (
    SQLiteRuntimeSchemaInspectionAdapter,
)
from backend.adapters.outbound.persistence.sql_successor_sql import DDL, PRECONDITIONS, READ
from backend.adapters.outbound.persistence.sql_successor_stability import (
    exclusive_copy_destination,
    pinned_windows_paths,
)
from backend.infrastructure.filesystem import (
    atomic_publish_fresh,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    hash_file_nofollow,
    private_temporary_file,
    read_file_nofollow,
)
from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeSchemaSnapshot,
    require_immutable_schema_file_set,
)
from backend.modules.local_provisioning.application.sql_successor import (
    CurrentVersionResolution,
    SQLSuccessorBinding,
    SQLSuccessorResult,
)

DDL_SHA256 = "696e0dd6329d8ef8b38cf950cd9d33d43e9deb1eab5d84653e110c3d90f8dd0e"
READ_SHA256 = "8443d3965e214a632bcb706ec04fd7b42519c0a03c912fdb19d1d26fb766f28f"
PRE_SHA256 = "d6797874abe08cf972fe2b7f9cc968c5cd678243ecc77d57e9c0deb59df0cb68"
STABILITY = "WINDOWS_OPEN_EXISTING_DENY_WRITE_DELETE_PINNED_ANCESTORS_1"


def reviewed_sql() -> None:
    for sql, expected in ((DDL, DDL_SHA256), (READ, READ_SHA256), (PRECONDITIONS, PRE_SHA256)):
        if hashlib.sha256(sql.encode("utf-8")).hexdigest() != expected:
            raise ValueError("SQL_SUCCESSOR_SQL_SUBSTITUTION")


def statements(sql: str) -> tuple[str, ...]:
    result, pending = [], ""
    for line in sql.splitlines(keepends=True):
        if line.lstrip().startswith("--") and not pending.strip():
            continue
        pending += line
        if sqlite3.complete_statement(pending):
            result.append(pending.strip())
            pending = ""
    if pending.strip() and not all(line.lstrip().startswith("--") for line in pending.splitlines()):
        raise ValueError("SQL_SUCCESSOR_INCOMPLETE_STATEMENT")
    return tuple(result)


def definitions(c: sqlite3.Connection) -> tuple[tuple[str, str, str, str | None], ...]:
    return tuple(c.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"))


def fingerprints(
    c: sqlite3.Connection,
    tables: tuple[str, ...],
) -> tuple[tuple[str, int, str], ...]:
    result = []
    for table in tables:
        name = '"' + table.replace('"', '""') + '"'
        digests = []
        for row in c.execute("SELECT * FROM " + name):
            values = [
                (
                    type(v).__name__,
                    base64.b64encode(v).decode("ascii") if isinstance(v, bytes) else v,
                )
                for v in row
            ]
            digests.append(
                hashlib.sha256(
                    json.dumps(
                        values, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                    ).encode()
                ).digest()
            )
        result.append((table, len(digests), hashlib.sha256(b"".join(sorted(digests))).hexdigest()))
    return tuple(result)


def _integrity(c: sqlite3.Connection) -> None:
    if (
        c.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
        or c.execute("PRAGMA quick_check").fetchall() != [("ok",)]
        or c.execute("PRAGMA foreign_key_check").fetchall()
    ):
        raise ValueError("SQL_SUCCESSOR_INTEGRITY")


def install_reviewed_successor(
    c: sqlite3.Connection,
    snapshot: RuntimeSchemaSnapshot,
) -> tuple[tuple[str, int, str], ...]:
    """No dynamic SQL input: fixed approved statements, one explicit transaction."""
    reviewed_sql()
    old = tuple((o.kind, o.name, o.table, o.definition) for o in snapshot.objects)
    tables = tuple(t.name for t in snapshot.tables)
    if definitions(c) != old:
        raise ValueError("SQL_SUCCESSOR_SCHEMA_SUBSTITUTION")
    if c.execute("PRAGMA foreign_keys").fetchone() != (1,) or c.execute(
        "PRAGMA recursive_triggers"
    ).fetchone() != (0,):
        raise ValueError("SQL_SUCCESSOR_CONNECTION_FLAGS")
    prior = fingerprints(c, tables)
    c.execute("BEGIN IMMEDIATE")
    try:
        if any(c.execute(sql).fetchone() != (0,) for sql in statements(PRECONDITIONS)):
            raise ValueError("SQL_SUCCESSOR_PRECONDITION_VIOLATION")
        for sql in statements(DDL):
            c.execute(sql)
        current = {row[1]: row for row in definitions(c)}
        expected = {row[1]: row for row in old}
        for sql in statements(DDL):
            match = re.match(r"CREATE (TRIGGER|TABLE|VIEW) (\w+)", sql)
            if match:
                kind, name = match.groups()
                on = re.search(r"\bON (\w+)\s", sql) if kind == "TRIGGER" else None
                table = on.group(1) if on else name
                expected[name] = (kind.lower(), name, table, sql.rstrip(";"))
        expected["sqlite_autoindex__pr4_published_version_seal_1"] = (
            "index",
            "sqlite_autoindex__pr4_published_version_seal_1",
            "_pr4_published_version_seal",
            None,
        )
        if current != expected:
            raise ValueError("SQL_SUCCESSOR_POST_SCHEMA_MISMATCH")
        if fingerprints(c, tables) != prior:
            raise ValueError("SQL_SUCCESSOR_BUSINESS_ROWS_CHANGED")
        if (
            c.execute(
                "SELECT id FROM resource_version WHERE lifecycle_status='PUBLISHED' "
                "EXCEPT SELECT resource_version_id FROM _pr4_published_version_seal"
            ).fetchall()
            or c.execute(
                "SELECT resource_version_id FROM _pr4_published_version_seal "
                "EXCEPT SELECT id FROM resource_version WHERE lifecycle_status='PUBLISHED'"
            ).fetchall()
        ):
            raise ValueError("SQL_SUCCESSOR_INITIAL_SEAL_MISMATCH")
        _integrity(c)
        c.commit()
    except BaseException:
        c.rollback()
        if definitions(c) != old or fingerprints(c, tables) != prior:
            raise ValueError("SQL_SUCCESSOR_TRANSACTION_ROLLBACK_FAILED") from None
        raise
    return prior


def _copy_exact(source: Path, destination: Path, root: Path, expected: str) -> None:
    # All source bytes are read only while the caller holds the Windows source pins.
    with source.open("rb") as reader, exclusive_copy_destination(destination, root) as writer:
        while block := reader.read(1024 * 1024):
            writer.write(block)
        writer.flush()
        import os

        os.fsync(writer.fileno())
    if hash_file_nofollow(destination, allowed_root=root) != expected:
        raise ValueError("SQL_SUCCESSOR_COPY_HASH")


class SQLiteSQLSuccessorAdapter:
    def __init__(
        self, source: Path, source_root: Path, root: Path, binding: SQLSuccessorBinding
    ) -> None:
        self.source, self.source_root, self.root, self.binding = source, source_root, root, binding
        self.final = root / "runtime-copy.sqlite"
        self.backup = root / "before-sql-successor.sqlite"
        self.receipt = root / "applied-receipt.json"

    def session(self) -> _Session:
        return _Session(self)

    def _snapshot(self, path: Path, root: Path, digest: str) -> RuntimeSchemaSnapshot:
        return SQLiteRuntimeSchemaInspectionAdapter(path, root, digest).inspect_schema()

    def _verify_existing(self) -> SQLSuccessorResult:
        if self._snapshot(self.source, self.source_root,
                          self.binding.snapshot.source_sha256) != self.binding.snapshot:
            raise ValueError("SQL_SUCCESSOR_FULL_SOURCE_BINDING_CHANGED")
        raw = read_file_nofollow(
            self.receipt, allowed_root=self.root, maximum_bytes=2 * 1024 * 1024
        )
        receipt = json.loads(raw)
        bound = asdict(self.binding)
        if receipt.get("binding") != json.loads(json.dumps(bound)):
            raise ValueError("SQL_SUCCESSOR_RECEIPT_BINDING")
        row = receipt["result"]
        if (
            hash_file_nofollow(self.backup, allowed_root=self.root)
            != self.binding.snapshot.source_sha256
        ):
            raise ValueError("SQL_SUCCESSOR_BACKUP_CHANGED")
        if hash_file_nofollow(self.final, allowed_root=self.root) != row["final_sha256"]:
            raise ValueError("SQL_SUCCESSOR_FINAL_CHANGED")
        snap = self._snapshot(self.final, self.root, row["final_sha256"])
        if snap.schema_sha256 != row["post_schema_sha256"]:
            raise ValueError("SQL_SUCCESSOR_POST_SCHEMA_MISMATCH")
        with closing(sqlite3.connect(self.final.as_uri() + "?mode=ro&immutable=1", uri=True)) as c:
            c.execute("PRAGMA foreign_keys=ON")
            _integrity(c)
            actual = fingerprints(c, tuple(t.name for t in self.binding.snapshot.tables))
        expected = tuple(tuple(v) for v in row["table_fingerprints"])
        if actual != expected:
            raise ValueError("SQL_SUCCESSOR_FINAL_ROWS_CHANGED")
        return SQLSuccessorResult(
            "ALREADY_APPLIED",
            self.binding.plan_sha256,
            self.binding.snapshot.source_sha256,
            row["final_sha256"],
            row["backup_sha256"],
            row["post_schema_sha256"],
            actual,
            tuple(row["steps"]),
            STABILITY,
        )

    def resolve_current(self, resource_ref: str) -> CurrentVersionResolution:
        reviewed_sql()
        with pinned_windows_paths(root=self.root, files=(self.final, self.backup, self.receipt)):
            self._verify_existing()
            with closing(
                sqlite3.connect(self.final.as_uri() + "?mode=ro&immutable=1", uri=True)
            ) as c:
                c.execute("PRAGMA query_only=ON")
                row = c.execute(READ, (resource_ref,)).fetchone()
        if row is None:
            raise ValueError("SQL_SUCCESSOR_CURRENT_MISSING_DIAGNOSTIC")
        return CurrentVersionResolution(
            cast(Literal["ABSENT", "EXACT", "AMBIGUOUS_CURRENT_VERSION"], row[0]), row[1], row[2]
        )


class _Session:
    def __init__(self, adapter: SQLiteSQLSuccessorAdapter) -> None:
        self.a, self.stack = adapter, ExitStack()
        self.steps: list[str] = []
        self.temporary: Path | None = None
        self.rows: tuple[tuple[str, int, str], ...] = ()
        self.final_hash = ""
        self.post_schema_hash = ""

    def __enter__(self) -> _Session:
        self.a.binding.validate()
        reviewed_sql()
        return self

    def __exit__(self, *args: object) -> None:
        try:
            if args and args[0] is not None and self.steps:
                self._evidence(
                    "FAILED",
                    {"error_type": getattr(args[0], "__name__", "ERROR"), "steps": self.steps},
                )
        finally:
            self.stack.close()

    def _evidence(self, name: str, data: object) -> None:
        path = self.a.root / (name + ".json")
        with path.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        harden_private_file(path, allowed_root=self.a.root)

    def existing(self) -> SQLSuccessorResult | None:
        a = self.a
        if not capture_secure_path(a.root, allowed_root=a.root.parent).exists:
            return None
        if not capture_secure_path(a.receipt, allowed_root=a.root).exists:
            raise ValueError("SQL_SUCCESSOR_PARTIAL_HISTORY_RETAINED")
        self.stack.enter_context(
            pinned_windows_paths(root=a.root, files=(a.final, a.backup, a.receipt))
        )
        return a._verify_existing()

    def _source_check(self) -> None:
        a = self.a
        if (
            a._snapshot(a.source, a.source_root, a.binding.snapshot.source_sha256)
            != a.binding.snapshot
        ):
            raise ValueError("SQL_SUCCESSOR_FULL_SOURCE_BINDING_CHANGED")

    def prepare(self) -> None:
        a = self.a
        files = SQLiteRuntimeSchemaInspectionAdapter(
            a.source, a.source_root, a.binding.snapshot.source_sha256
        ).inspect_files()
        require_immutable_schema_file_set(files)
        self.stack.enter_context(
            pinned_windows_paths(
                root=a.source_root,
                files=tuple(Path(str(a.source) + r.suffix) for r in files if r.exists),
            )
        )
        self._source_check()
        # Source stability is established before the first destination effect.
        if capture_secure_path(a.root, allowed_root=a.root.parent).exists:
            raise ValueError("SQL_SUCCESSOR_ROOT_COLLISION")
        ensure_private_directory(a.root, allowed_root=a.root.parent)
        self.stack.enter_context(pinned_windows_paths(root=a.root, directories=(a.root,)))
        self.temporary = private_temporary_file(
            a.root, allowed_root=a.root, prefix="initial-", suffix=".sqlite"
        )
        _copy_exact(a.source, self.temporary, a.root, a.binding.snapshot.source_sha256)
        self._source_check()
        self.steps.append("SOURCE_PINNED_INITIAL_COPY_VERIFIED")
        self._evidence(
            "01_SOURCE_STABILITY",
            {
                "mechanism": STABILITY,
                "snapshot": asdict(a.binding.snapshot),
                "source_unchanged": True,
            },
        )

    def backup_and_verify_restore(self) -> None:
        if self.steps != ["SOURCE_PINNED_INITIAL_COPY_VERIFIED"] or self.temporary is None:
            raise ValueError("SQL_SUCCESSOR_STEP_ORDER")
        a = self.a
        # Backup/control files are fresh and retained; no historical reservation erased.
        with a.backup.open("xb"):
            pass
        harden_private_file(a.backup, allowed_root=a.root)
        _copy_exact(self.temporary, a.backup, a.root, a.binding.snapshot.source_sha256)
        self.stack.enter_context(pinned_windows_paths(root=a.root, files=(a.backup,)))
        control = private_temporary_file(
            a.root, allowed_root=a.root, prefix="restore-control-", suffix=".sqlite"
        )
        _copy_exact(a.backup, control, a.root, a.binding.snapshot.source_sha256)
        copied = a._snapshot(control, a.root, a.binding.snapshot.source_sha256)
        expected = a.binding.snapshot
        if (copied.objects, copied.tables, copied.indexes) != (
            expected.objects,
            expected.tables,
            expected.indexes,
        ):
            raise ValueError("SQL_SUCCESSOR_RESTORE_SCHEMA")
        with closing(sqlite3.connect(control.as_uri() + "?mode=ro&immutable=1", uri=True)) as c:
            c.execute("PRAGMA foreign_keys=ON")
            _integrity(c)
        self.steps.append("BACKUP_RESTORE_CONTROL_VERIFIED")
        self._evidence(
            "02_BACKUP_RESTORE",
            {
                "backup_sha256": a.binding.snapshot.source_sha256,
                "control_sha256": a.binding.snapshot.source_sha256,
                "schema": copied.schema_sha256,
                "control_retained": True,
            },
        )

    def migrate_and_check(self) -> None:
        if len(self.steps) != 2 or self.temporary is None:
            raise ValueError("SQL_SUCCESSOR_STEP_ORDER")
        # This setting affects only the newly created working copy.
        c = sqlite3.connect(self.temporary, isolation_level=None)
        try:
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA recursive_triggers=OFF")
            c.execute("PRAGMA journal_mode=DELETE")
            self.rows = install_reviewed_successor(c, self.a.binding.snapshot)
        finally:
            c.close()
        self.final_hash = hash_file_nofollow(self.temporary, allowed_root=self.a.root)
        snap = self.a._snapshot(self.temporary, self.a.root, self.final_hash)
        self.post_schema_hash = snap.schema_sha256
        self.steps.append("TRANSACTION_POSTCONDITIONS_VERIFIED")
        self._evidence(
            "03_TRANSACTION",
            {
                "post_schema_sha256": self.post_schema_hash,
                "table_fingerprints": self.rows,
                "final_sha256": self.final_hash,
            },
        )

    def publish(self) -> SQLSuccessorResult:
        if len(self.steps) != 3 or self.temporary is None:
            raise ValueError("SQL_SUCCESSOR_STEP_ORDER")
        a = self.a
        self._source_check()
        if hash_file_nofollow(a.backup, allowed_root=a.root) != a.binding.snapshot.source_sha256:
            raise ValueError("SQL_SUCCESSOR_BACKUP_CHANGED")
        # Pin candidate bytes until the last checks. Fresh primitive remains unchanged.
        with pinned_windows_paths(root=a.root, files=(self.temporary,)):
            if hash_file_nofollow(self.temporary, allowed_root=a.root) != self.final_hash:
                raise ValueError("SQL_SUCCESSOR_TEMPORARY_SUBSTITUTION")
        atomic_publish_fresh(self.temporary, a.final, allowed_root=a.root)
        self.stack.enter_context(pinned_windows_paths(root=a.root, files=(a.final,)))
        if hash_file_nofollow(a.final, allowed_root=a.root) != self.final_hash:
            raise ValueError("SQL_SUCCESSOR_PUBLICATION_SUBSTITUTION")
        self.steps.append("FRESH_FINAL_PUBLISHED_ONCE")
        result = SQLSuccessorResult(
            "APPLIED",
            a.binding.plan_sha256,
            a.binding.snapshot.source_sha256,
            self.final_hash,
            a.binding.snapshot.source_sha256,
            self.post_schema_hash,
            self.rows,
            tuple(self.steps),
            STABILITY,
        )
        self._evidence(
            "applied-receipt",
            {
                "binding": asdict(a.binding),
                "result": asdict(result),
                "operational_rollback": "STOP_PENDING_SAFE_REPLACEMENT_REVIEW",
            },
        )
        return result
