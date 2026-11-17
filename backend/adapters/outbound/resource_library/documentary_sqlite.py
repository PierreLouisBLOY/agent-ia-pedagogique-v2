"""Separate, append-only documentary database. Never opens another V2 store for writes."""
import json
from pathlib import Path
from typing import cast

from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.infrastructure.filesystem import (
    capture_secure_path,
    ensure_private_directory,
    hash_file_nofollow,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint, items
from backend.modules.resource_library.contracts.dto.documentary_library import (
    DocumentaryAttachment,
    DocumentarySnapshot,
)

APP_ID = 0x5632444C
TABLES = {"documentary_package", "documentary_organization", "documentary_document", "documentary_source",
          "documentary_link", "documentary_file"}
DDL = (
    "CREATE TABLE documentary_package(id TEXT PRIMARY KEY, snapshot_sha256 TEXT NOT NULL, payload TEXT NOT NULL)",
    "CREATE TABLE documentary_organization(package TEXT NOT NULL REFERENCES documentary_package(id), id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(package,id))",
    "CREATE TABLE documentary_document(package TEXT NOT NULL, id TEXT NOT NULL, organization TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(package,id), FOREIGN KEY(package,organization) REFERENCES documentary_organization(package,id))",
    "CREATE TABLE documentary_source(package TEXT NOT NULL REFERENCES documentary_package(id), id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(package,id))",
    "CREATE TABLE documentary_link(package TEXT NOT NULL, document TEXT NOT NULL, source TEXT NOT NULL, ordinal INTEGER NOT NULL, PRIMARY KEY(package,document,source), FOREIGN KEY(package,document) REFERENCES documentary_document(package,id), FOREIGN KEY(package,source) REFERENCES documentary_source(package,id))",
    "CREATE TABLE documentary_file(package TEXT NOT NULL REFERENCES documentary_package(id), name TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, content BLOB NOT NULL, PRIMARY KEY(package,name))",
)


def _json(value: object) -> str:
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
    return json.dumps(as_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class DocumentarySQLite:
    def __init__(self, path: Path, *, allowed_root: Path, create: bool = False) -> None:
        self.path, self.root = path, allowed_root
        if not path.exists():
            if not create:
                raise ValueError("DOCUMENTARY_DATABASE_NOT_FOUND")
            ensure_private_directory(path.parent, allowed_root=allowed_root)
            capture_secure_path(path.parent, allowed_root=allowed_root)
            with path.open("xb"):
                pass
            connection = connect_sqlite(path, allowed_root=allowed_root)
            try:
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in DDL:
                        connection.execute(statement)
                    connection.execute(f"PRAGMA application_id={APP_ID}")
                    connection.execute("PRAGMA user_version=1")
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            finally:
                connection.close()
        # Read-only check before any writable connect, including idempotent imports.
        connection = connect_sqlite(path, readonly=True, allowed_root=allowed_root)
        try:
            actual = {str(r[0]) for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if (connection.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                    or connection.execute("PRAGMA user_version").fetchone()[0] != 1 or actual != TABLES):
                raise ValueError("DOCUMENTARY_FOREIGN_DATABASE_REFUSED")
        finally:
            connection.close()
        self.identity = capture_secure_path(path, allowed_root=allowed_root)

    def _identity(self) -> None:
        if not self.identity.same_identity(capture_secure_path(self.path, allowed_root=self.root)):
            raise ValueError("DOCUMENTARY_DATABASE_IDENTITY_CHANGED")

    def descriptor(self) -> dict[str, object]:
        self._identity()
        return {"schema": "V2-DOCUMENTARY-SQLITE-1.0",
                "sha256": hash_file_nofollow(self.path, allowed_root=self.root),
                "bytes": self.path.stat().st_size, "independent_library": True}

    def append(self, snapshot: DocumentarySnapshot, files: tuple[DocumentaryAttachment, ...]) -> bool:
        self._identity()
        expected = {str(f["name"]): f for f in items(snapshot.data["files"], 100)}
        if len(files) != len(expected) or {f.name for f in files} != set(expected):
            raise ValueError("DOCUMENTARY_ATTACHMENTS_REQUIRED")
        for file in files:
            if file.sha256 != expected[file.name]["sha256"] or len(file.content) != expected[file.name]["bytes"]:
                raise ValueError("DOCUMENTARY_ATTACHMENT_CHANGED")
        key = str(snapshot.data["archive_sha256"])
        reader = connect_sqlite(self.path, readonly=True, allowed_root=self.root)
        try:
            prior = reader.execute("SELECT snapshot_sha256 FROM documentary_package WHERE id=?", (key,)).fetchone()
            if prior is not None:
                if prior[0] != snapshot.sha256:
                    raise ValueError("DOCUMENTARY_IMMUTABLE_CONFLICT")
                return False  # No writable connection for a repeated import.
        finally:
            reader.close()
        connection = connect_sqlite(self.path, allowed_root=self.root)
        try:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute("SELECT snapshot_sha256 FROM documentary_package WHERE id=?", (key,)).fetchone()
            if prior is not None:
                if prior[0] != snapshot.sha256:
                    raise ValueError("DOCUMENTARY_IMMUTABLE_CONFLICT")
                connection.rollback()
                return False
            connection.execute("INSERT INTO documentary_package VALUES (?,?,?)", (key, snapshot.sha256, _json(snapshot.data)))
            for row in items(snapshot.data["organizations"], 100):
                connection.execute("INSERT INTO documentary_organization VALUES (?,?,?)", (key, row["id"], _json(row)))
            for row in items(snapshot.data["sources"], 1000):
                connection.execute("INSERT INTO documentary_source VALUES (?,?,?)", (key, row["id"], _json(row)))
            for row in items(snapshot.data["documents"], 1000):
                connection.execute("INSERT INTO documentary_document VALUES (?,?,?,?)", (key, row["id"], row["organization_id"], _json(row)))
                for ordinal, source in enumerate(cast(tuple[str, ...], row["source_ids"])):
                    connection.execute("INSERT INTO documentary_link VALUES (?,?,?,?)", (key, row["id"], source, ordinal))
            for file in files:
                connection.execute("INSERT INTO documentary_file VALUES (?,?,?,?,?)", (key, file.name, file.sha256, len(file.content), file.content))
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def snapshots(self) -> tuple[DocumentarySnapshot, ...]:
        self._identity()
        connection = connect_sqlite(self.path, readonly=True, allowed_root=self.root)
        try:
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("DOCUMENTARY_STORED_LINK_CHANGED")
            result = []
            for row in connection.execute("SELECT id,snapshot_sha256,payload FROM documentary_package ORDER BY id LIMIT 101"):
                value = DocumentarySnapshot(json.loads(row["payload"]))
                if value.sha256 != row["snapshot_sha256"] or value.data["archive_sha256"] != row["id"]:
                    raise ValueError("DOCUMENTARY_STORED_SNAPSHOT_CHANGED")
                key = row["id"]
                for table, field, maximum in (("documentary_organization", "organizations", 100),
                        ("documentary_document", "documents", 1000), ("documentary_source", "sources", 1000)):
                    actual = [json.loads(r[0]) for r in connection.execute(f"SELECT payload FROM {table} WHERE package=? ORDER BY id", (key,))]
                    expected = sorted(items(value.data[field], maximum), key=lambda r: str(r["id"]))
                    if fingerprint(actual) != fingerprint(expected):
                        raise ValueError("DOCUMENTARY_STORED_INDEX_CHANGED")
                links = [(d["id"], s, i) for d in items(value.data["documents"], 1000) for i, s in enumerate(cast(tuple[str, ...], d["source_ids"]))]
                actual_links = [tuple(r) for r in connection.execute("SELECT document,source,ordinal FROM documentary_link WHERE package=?", (key,))]
                if set(links) != set(actual_links):
                    raise ValueError("DOCUMENTARY_STORED_LINK_CHANGED")
                actual_files = [dict(r) for r in connection.execute("SELECT name,sha256,size AS bytes FROM documentary_file WHERE package=? ORDER BY name", (key,))]
                expected_files = sorted(items(value.data["files"], 100), key=lambda f: str(f["name"]))
                if fingerprint(actual_files) != fingerprint(expected_files):
                    raise ValueError("DOCUMENTARY_STORED_FILE_INDEX_CHANGED")
                result.append(value)
            if len(result) > 100:
                raise ValueError("DOCUMENTARY_PACKAGE_BOUND")
            return tuple(result)
        finally:
            connection.close()

    def attachment(self, archive_sha256: str, name: str) -> DocumentaryAttachment:
        self._identity()
        connection = connect_sqlite(self.path, readonly=True, allowed_root=self.root)
        try:
            row = connection.execute("SELECT content,sha256,size FROM documentary_file WHERE package=? AND name=?", (archive_sha256, name)).fetchone()
            if row is None:
                raise ValueError("DOCUMENTARY_FILE_NOT_FOUND")
            result = DocumentaryAttachment(name, bytes(row["content"]))
            if result.sha256 != row["sha256"] or len(result.content) != row["size"]:
                raise ValueError("DOCUMENTARY_ATTACHMENT_CHANGED")
            return result
        finally:
            connection.close()
