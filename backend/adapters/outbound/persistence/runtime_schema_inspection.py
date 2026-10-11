"""Authenticated fixed-schema reader. No caller-supplied SQL or write operation."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.infrastructure.filesystem import PathSnapshot, capture_secure_path, hash_file_nofollow
from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeFileMetadata,
    RuntimeIndexMetadata,
    RuntimeSchemaObject,
    RuntimeSchemaSnapshot,
    RuntimeTableMetadata,
    SchemaScalar,
    require_immutable_schema_file_set,
)

SIDECARS = ("-wal", "-shm", "-journal")


def _rows(cursor: sqlite3.Cursor, maximum: int) -> tuple[tuple[SchemaScalar, ...], ...]:
    values = cursor.fetchmany(maximum + 1)
    if len(values) > maximum:
        raise ValueError("RUNTIME_SCHEMA_BOUNDS")
    result = tuple(tuple(row) for row in values)
    if any(any(value is not None and type(value) not in (str, int)
               for value in row) for row in result):
        raise ValueError("RUNTIME_SCHEMA_METADATA_TYPE")
    return result


class SQLiteRuntimeSchemaInspectionAdapter:
    def __init__(self, path: Path, allowed_root: Path, expected_sha256: str) -> None:
        self._path, self._root, self._expected = path, allowed_root, expected_sha256

    def _capture(self) -> PathSnapshot:
        require_immutable_schema_file_set(self.inspect_files())
        return capture_secure_path(self._path, allowed_root=self._root)

    def inspect_schema(self) -> RuntimeSchemaSnapshot:
        files_before = self.inspect_files()
        before = self._capture()
        # Refuse nonempty WAL, all journals and inconsistent SHM before reading
        # pinned main bytes. Preserve passive sidecars and capture them afterwards.
        # Runtime WAL readers keep their existing, non-immutable behavior.
        connection = connect_sqlite(self._path, readonly=True, immutable=True,
                                    allowed_root=self._root)
        try:
            connection.execute("BEGIN")
            definitions = _rows(connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
            ), 2048)
            objects = tuple(RuntimeSchemaObject(str(r[0]), str(r[1]), str(r[2]),
                                                None if r[3] is None else str(r[3]))
                            for r in definitions)
            tables = tuple(RuntimeTableMetadata(
                obj.name,
                _rows(connection.execute("SELECT * FROM pragma_table_xinfo(?)", (obj.name,)), 256),
                _rows(connection.execute("SELECT * FROM pragma_foreign_key_list(?)", (obj.name,)), 256),
                _rows(connection.execute("SELECT * FROM pragma_index_list(?)", (obj.name,)), 256),
            ) for obj in objects if obj.kind == "table")
            indexes = tuple(RuntimeIndexMetadata(obj.name, _rows(connection.execute(
                "SELECT * FROM pragma_index_xinfo(?)", (obj.name,)
            ), 256)) for obj in objects if obj.kind == "index")
            flags = tuple((name, connection.execute("PRAGMA " + name).fetchone()[0])
                          for name in ("query_only", "foreign_keys", "recursive_triggers",
                                       "journal_mode", "schema_version", "user_version"))
            integrity = tuple(str(row[0]) for row in _rows(
                connection.execute("PRAGMA integrity_check"), 256))
            quick = tuple(str(row[0]) for row in _rows(
                connection.execute("PRAGMA quick_check"), 256))
            violations = len(_rows(connection.execute("PRAGMA foreign_key_check"), 10000))
            connection.rollback()
        finally:
            connection.close()
        after = self._capture()
        files_after = self.inspect_files()
        if files_before != files_after or not before.same_state(after):
            raise ValueError("RUNTIME_SCHEMA_SOURCE_CHANGED")
        encoded = json.dumps(definitions, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return RuntimeSchemaSnapshot(
            self._expected, before.size_bytes, int(before.device or 0),
            int(before.inode or 0), int(before.modified_ns or 0),
            hashlib.sha256(encoded).hexdigest(), objects, tables, indexes,
            flags, integrity, quick, violations,
            tuple(row.suffix for row in files_before[1:] if not row.exists), files_before,
        )

    def inspect_files(self) -> tuple[RuntimeFileMetadata, ...]:
        result = []
        for suffix in ("", *SIDECARS):
            path = Path(str(self._path) + suffix)
            before = capture_secure_path(path, allowed_root=self._root)
            if before.exists and not before.is_file:
                raise ValueError("RUNTIME_SCHEMA_REGULAR_FILE_REQUIRED")
            digest = hash_file_nofollow(path, allowed_root=self._root) if before.exists else None
            after = capture_secure_path(path, allowed_root=self._root)
            if not before.same_state(after):
                raise ValueError("RUNTIME_SCHEMA_SOURCE_CHANGED")
            result.append(RuntimeFileMetadata(suffix, before.exists, before.size_bytes,
                before.device, before.inode, before.modified_ns, digest))
        if result[0].sha256 != self._expected:
            raise ValueError("RUNTIME_SCHEMA_SOURCE_MISMATCH")
        return tuple(result)
