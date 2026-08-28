"""Owner-specific SQLite stores and Data Mapper primitives from Phase 7."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from pathlib import Path

PersistenceRecord = dict[str, object]


class ConcurrencyConflict(RuntimeError):
    """The persisted version no longer matches the caller's expected version."""


def new_ref(prefix: str) -> str:
    return f"{prefix}:runtime:{uuid.uuid4().hex}"


def connect_sqlite(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    """Open either an immutable seed/read connection or a mutable runtime one."""
    if readonly:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if not readonly:
        connection.execute("PRAGMA busy_timeout = 3000")
        connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _record(row: sqlite3.Row | None) -> PersistenceRecord | None:
    if row is None:
        return None
    return {str(key): row[key] for key in row.keys()}


def _records(rows: Sequence[sqlite3.Row]) -> tuple[PersistenceRecord, ...]:
    return tuple({str(key): row[key] for key in row.keys()} for row in rows)


class _OwnerStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def _one(self, sql: str, parameters: tuple[object, ...]) -> PersistenceRecord | None:
        return _record(self._connection.execute(sql, parameters).fetchone())


class KnowledgeStore(_OwnerStore):
    def load_notion(self, notion_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM notion WHERE id = ?", (notion_ref,))

    def add_notion(self, label: str) -> str:
        notion_ref = new_ref("notion")
        self._connection.execute(
            """INSERT INTO notion(
                   id, canonical_label, language_code, identity_status, created_at
               ) VALUES (?, ?, ?, ?, datetime('now'))""",
            (notion_ref, label, "fr", "CANONICAL"),
        )
        register_object(self._connection, notion_ref, "NOTION")
        return notion_ref


class DocumentStore(_OwnerStore):
    def load_document(self, document_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM document WHERE id = ?", (document_ref,))

    def add_document(self, title: str, sha256: str | None = None) -> str:
        document_ref = new_ref("document")
        self._connection.execute(
            """INSERT INTO document(
                   id, document_type, title, sha256, language_code,
                   document_status, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (document_ref, "OTHER", title, sha256, "fr", "ACTIVE"),
        )
        return document_ref


class ResourceStore(_OwnerStore):
    def load_resource(self, resource_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM resource WHERE id = ?", (resource_ref,))

    def add_resource(self, title: str) -> str:
        resource_ref = new_ref("resource")
        self._connection.execute(
            """INSERT INTO resource(
                   id, resource_type, canonical_title, identity_status, created_at
               ) VALUES (?, ?, ?, ?, datetime('now'))""",
            (resource_ref, "OTHER", title, "CANONICAL"),
        )
        register_object(self._connection, resource_ref, "RESOURCE")
        return resource_ref


class ContextStore(_OwnerStore):
    def load_context(self, context_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM pedagogical_context WHERE id = ?", (context_ref,))

    def add_context(self, context_key: str) -> str:
        context_ref = new_ref("context")
        self._connection.execute(
            "INSERT INTO pedagogical_context(id, context_key, notes) VALUES (?, ?, ?)",
            (context_ref, context_key, "runtime"),
        )
        return context_ref


class WorkStore(_OwnerStore):
    def load_session(self, session_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM session WHERE id = ?", (session_ref,))

    def add_session(self, title: str) -> str:
        session_ref = new_ref("session")
        self._connection.execute(
            """INSERT INTO session(
                   id, title, lifecycle_status, created_at, updated_at
               ) VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
            (session_ref, title, "ACTIVE"),
        )
        return session_ref

    def change_status(
        self, session_ref: str, status: str, *, expected_updated_at: str
    ) -> str:
        next_version = f"{expected_updated_at}.next"
        cursor = self._connection.execute(
            """UPDATE session SET lifecycle_status = ?, updated_at = ?
               WHERE id = ? AND updated_at = ?""",
            (status, next_version, session_ref, expected_updated_at),
        )
        if cursor.rowcount != 1:
            raise ConcurrencyConflict(session_ref)
        return next_version

    def add_task(self, session_ref: str) -> str:
        task_ref = new_ref("task")
        self._connection.execute(
            """INSERT INTO task(
                   id, session_id, task_type, objective, status, created_at
               ) VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (task_ref, session_ref, "RUNTIME_CONTRACT", "contract", "COMPLETED"),
        )
        return task_ref

    def add_production(self, task_ref: str) -> str:
        production_ref = new_ref("production")
        self._connection.execute(
            """INSERT INTO production(
                   id, task_id, production_type, title, lifecycle_status, created_at
               ) VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (production_ref, task_ref, "OTHER", "runtime production", "VALIDATED"),
        )
        register_object(self._connection, production_ref, "PRODUCTION")
        return production_ref


class ValidationStore(_OwnerStore):
    def append(self, object_ref: str) -> str:
        event_ref = new_ref("validation")
        self._connection.execute(
            """INSERT INTO validation_event(
                   id, object_id, validation_type, result, comment, created_at
               ) VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (event_ref, object_ref, "RUNTIME_CONTRACT", "PASS", "sqlite adapter"),
        )
        return event_ref

    def read(self, event_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM validation_event WHERE id = ?", (event_ref,))


class QualityStore(_OwnerStore):
    def append(self, object_ref: str) -> str:
        framework = self._connection.execute(
            "SELECT id FROM quality_framework_version ORDER BY id LIMIT 1"
        ).fetchone()
        if framework is None:
            raise LookupError("quality framework version unavailable")
        evaluation_ref = new_ref("quality")
        self._connection.execute(
            """INSERT INTO quality_evaluation(
                   id, object_id, quality_framework_version_id,
                   status, evaluated_at, global_score
               ) VALUES (?, ?, ?, ?, datetime('now'), ?)""",
            (evaluation_ref, object_ref, framework[0], "COMPLETED", 1.0),
        )
        return evaluation_ref

    def read(self, evaluation_ref: str) -> PersistenceRecord | None:
        return self._one(
            "SELECT * FROM quality_evaluation WHERE id = ?", (evaluation_ref,)
        )


class LifecycleDecisionStore(_OwnerStore):
    def append_promotion(self, production_ref: str, resource_ref: str) -> str:
        promotion_ref = new_ref("promotion")
        self._connection.execute(
            """INSERT INTO production_resource_promotion(
                   id, production_id, resource_id, promotion_status,
                   promoted_at, justification
               ) VALUES (?, ?, ?, ?, datetime('now'), ?)""",
            (promotion_ref, production_ref, resource_ref, "PROMOTED", "runtime contract"),
        )
        return promotion_ref

    def read_promotion(self, promotion_ref: str) -> PersistenceRecord | None:
        return self._one(
            "SELECT * FROM production_resource_promotion WHERE id = ?", (promotion_ref,)
        )


class AuditTraceabilityStore(_OwnerStore):
    def append_event(self, object_ref: str | None) -> str:
        event_ref = new_ref("audit")
        self._connection.execute(
            """INSERT INTO audit_event(
                   id, object_id, event_type, occurred_at, reason, payload_json
               ) VALUES (?, ?, ?, datetime('now'), ?, ?)""",
            (event_ref, object_ref, "RUNTIME_PORT_CONTRACT", "sqlite adapter", "{}"),
        )
        return event_ref

    def read_event(self, event_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM audit_event WHERE id = ?", (event_ref,))


def register_object(connection: sqlite3.Connection, object_ref: str, object_type: str) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO object_registry(object_id, object_type) VALUES (?, ?)",
        (object_ref, object_type),
    )
