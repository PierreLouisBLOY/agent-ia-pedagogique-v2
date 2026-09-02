"""Owner-specific SQLite stores and Data Mapper primitives from Phase 7."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from pathlib import Path

from backend.adapters.outbound.persistence.vocabulary import (
    encode_audit,
    encode_context_origin,
    encode_document,
    encode_notion,
    encode_production,
    encode_promotion,
    encode_quality,
    encode_resource,
    encode_session,
    encode_task,
    encode_validation,
)
from backend.modules.audit_traceability.application.dto.persistence_vocabulary import (
    AuditPersistenceValues,
)
from backend.modules.documents_provenance.domain.value_objects.persistence_vocabulary import (
    DocumentPersistenceValues,
)
from backend.modules.knowledge_reference.domain.value_objects.persistence_vocabulary import (
    NotionPersistenceValues,
)
from backend.modules.lifecycle_promotion.domain.value_objects.persistence_vocabulary import (
    PromotionPersistenceValues,
)
from backend.modules.pedagogical_context.application.dto.context_origin import ContextOrigin
from backend.modules.quality_evaluation.domain.value_objects.persistence_vocabulary import (
    QualityPersistenceValues,
)
from backend.modules.resource_library.domain.value_objects.persistence_vocabulary import (
    ResourcePersistenceValues,
)
from backend.modules.transformation_assembly.domain.value_objects.persistence_vocabulary import (
    ProductionPersistenceValues,
)
from backend.modules.validation_control.application.dto.persistence_vocabulary import (
    ValidationPersistenceValues,
)
from backend.modules.work_orchestration.application.dto.task_persistence import (
    TaskPersistenceValues,
)
from backend.modules.work_orchestration.domain.value_objects.session_lifecycle import (
    SessionLifecycleStatus,
)

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

    def add_notion(self, label: str, values: NotionPersistenceValues) -> str:
        notion_ref = new_ref("notion")
        language_code, identity_status = encode_notion(values)
        self._connection.execute(
            """INSERT INTO notion(
                   id, canonical_label, language_code, identity_status, created_at
               ) VALUES (?, ?, ?, ?, datetime('now'))""",
            (notion_ref, label, language_code, identity_status),
        )
        register_object(self._connection, notion_ref, "NOTION")
        return notion_ref


class DocumentStore(_OwnerStore):
    def load_document(self, document_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM document WHERE id = ?", (document_ref,))

    def add_document(
        self,
        title: str,
        values: DocumentPersistenceValues,
        sha256: str | None = None,
    ) -> str:
        document_ref = new_ref("document")
        document_type, language_code, status = encode_document(values)
        self._connection.execute(
            """INSERT INTO document(
                   id, document_type, title, sha256, language_code,
                   document_status, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (document_ref, document_type, title, sha256, language_code, status),
        )
        return document_ref


class ResourceStore(_OwnerStore):
    def load_resource(self, resource_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM resource WHERE id = ?", (resource_ref,))

    def add_resource(self, title: str, values: ResourcePersistenceValues) -> str:
        resource_ref = new_ref("resource")
        resource_type, identity_status = encode_resource(values)
        self._connection.execute(
            """INSERT INTO resource(
                   id, resource_type, canonical_title, identity_status, created_at
               ) VALUES (?, ?, ?, ?, datetime('now'))""",
            (resource_ref, resource_type, title, identity_status),
        )
        register_object(self._connection, resource_ref, "RESOURCE")
        return resource_ref


class ContextStore(_OwnerStore):
    def load_context(self, context_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM pedagogical_context WHERE id = ?", (context_ref,))

    def add_context(self, context_key: str, origin: ContextOrigin) -> str:
        context_ref = new_ref("context")
        encode_context_origin(origin)
        self._connection.execute(
            "INSERT INTO pedagogical_context(id, context_key, notes) VALUES (?, ?, ?)",
            (context_ref, context_key, None),
        )
        return context_ref


class WorkStore(_OwnerStore):
    def load_session(self, session_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM session WHERE id = ?", (session_ref,))

    def add_session(self, title: str, status: SessionLifecycleStatus) -> str:
        session_ref = new_ref("session")
        self._connection.execute(
            """INSERT INTO session(
                   id, title, lifecycle_status, created_at, updated_at
               ) VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
            (session_ref, title, encode_session(status)),
        )
        return session_ref

    def change_status(
        self,
        session_ref: str,
        status: SessionLifecycleStatus,
        *,
        expected_updated_at: str,
    ) -> str:
        next_version = f"{expected_updated_at}.next"
        cursor = self._connection.execute(
            """UPDATE session SET lifecycle_status = ?, updated_at = ?
               WHERE id = ? AND updated_at = ?""",
            (encode_session(status), next_version, session_ref, expected_updated_at),
        )
        if cursor.rowcount != 1:
            raise ConcurrencyConflict(session_ref)
        return next_version

    def add_task(self, session_ref: str, values: TaskPersistenceValues) -> str:
        task_ref = new_ref("task")
        task_type, objective_ref, status = encode_task(values)
        self._connection.execute(
            """INSERT INTO task(
                   id, session_id, task_type, objective, status, created_at
               ) VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (task_ref, session_ref, task_type, objective_ref, status),
        )
        return task_ref

    def add_production(self, task_ref: str, values: ProductionPersistenceValues) -> str:
        production_ref = new_ref("production")
        production_type, title, lifecycle_status = encode_production(values)
        self._connection.execute(
            """INSERT INTO production(
                   id, task_id, production_type, title, lifecycle_status, created_at
               ) VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (production_ref, task_ref, production_type, title, lifecycle_status),
        )
        register_object(self._connection, production_ref, "PRODUCTION")
        return production_ref


class ValidationStore(_OwnerStore):
    def append(self, object_ref: str, values: ValidationPersistenceValues) -> str:
        event_ref = new_ref("validation")
        validation_type, result, validator_ref = encode_validation(values)
        self._connection.execute(
            """INSERT INTO validation_event(
                   id, object_id, validation_type, result, comment, created_at
               ) VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (event_ref, object_ref, validation_type, result, validator_ref),
        )
        return event_ref

    def read(self, event_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM validation_event WHERE id = ?", (event_ref,))


class QualityStore(_OwnerStore):
    def append(self, object_ref: str, values: QualityPersistenceValues) -> str:
        framework = self._connection.execute(
            "SELECT id FROM quality_framework_version ORDER BY id LIMIT 1"
        ).fetchone()
        if framework is None:
            raise LookupError("quality framework version unavailable")
        evaluation_ref = new_ref("quality")
        status, score = encode_quality(values)
        self._connection.execute(
            """INSERT INTO quality_evaluation(
                   id, object_id, quality_framework_version_id,
                   status, evaluated_at, global_score
               ) VALUES (?, ?, ?, ?, datetime('now'), ?)""",
            (evaluation_ref, object_ref, framework[0], status, score),
        )
        return evaluation_ref

    def read(self, evaluation_ref: str) -> PersistenceRecord | None:
        return self._one(
            "SELECT * FROM quality_evaluation WHERE id = ?", (evaluation_ref,)
        )


class LifecycleDecisionStore(_OwnerStore):
    def append_promotion(
        self,
        production_ref: str,
        resource_ref: str,
        values: PromotionPersistenceValues,
    ) -> str:
        promotion_ref = new_ref("promotion")
        status, justification = encode_promotion(values)
        self._connection.execute(
            """INSERT INTO production_resource_promotion(
                   id, production_id, resource_id, promotion_status,
                   promoted_at, justification
               ) VALUES (?, ?, ?, ?, datetime('now'), ?)""",
            (promotion_ref, production_ref, resource_ref, status, justification),
        )
        return promotion_ref

    def read_promotion(self, promotion_ref: str) -> PersistenceRecord | None:
        return self._one(
            "SELECT * FROM production_resource_promotion WHERE id = ?", (promotion_ref,)
        )


class AuditTraceabilityStore(_OwnerStore):
    def append_event(self, object_ref: str | None, values: AuditPersistenceValues) -> str:
        event_ref = new_ref("audit")
        event_type, actor_ref, payload = encode_audit(values)
        self._connection.execute(
            """INSERT INTO audit_event(
                   id, object_id, event_type, occurred_at, reason, payload_json
               ) VALUES (?, ?, ?, datetime('now'), ?, ?)""",
            (event_ref, object_ref, event_type, actor_ref, payload),
        )
        return event_ref

    def read_event(self, event_ref: str) -> PersistenceRecord | None:
        return self._one("SELECT * FROM audit_event WHERE id = ?", (event_ref,))


def register_object(connection: sqlite3.Connection, object_ref: str, object_type: str) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO object_registry(object_id, object_type) VALUES (?, ?)",
        (object_ref, object_type),
    )
