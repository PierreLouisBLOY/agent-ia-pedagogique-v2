"""Root-owned Phase 7 SQLite Unit of Work."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Literal

from backend.adapters.outbound.persistence.sqlite import (
    AuditTraceabilityStore,
    ContextStore,
    DocumentStore,
    KnowledgeStore,
    LifecycleDecisionStore,
    QualityStore,
    ResourceStore,
    ValidationStore,
    WorkStore,
    connect_sqlite,
)

MARKER_TABLE = "_runtime_operation_commit"


class SQLiteUnitOfWork:
    def __init__(self, path: Path, *, operation_ref: str | None = None) -> None:
        self._path = path
        self._operation_ref = operation_ref
        self._connection: sqlite3.Connection | None = None
        self._committed = False

    def __enter__(self) -> SQLiteUnitOfWork:
        connection = connect_sqlite(self._path)
        connection.execute(
            f"""CREATE TABLE IF NOT EXISTS {MARKER_TABLE} (
                   operation_ref TEXT PRIMARY KEY,
                   committed_at TEXT NOT NULL
               )"""
        )
        connection.execute("BEGIN IMMEDIATE")
        self._connection = connection
        self.knowledge = KnowledgeStore(connection)
        self.documents = DocumentStore(connection)
        self.resources = ResourceStore(connection)
        self.contexts = ContextStore(connection)
        self.work = WorkStore(connection)
        self.validations = ValidationStore(connection)
        self.quality = QualityStore(connection)
        self.lifecycle = LifecycleDecisionStore(connection)
        self.audit = AuditTraceabilityStore(connection)
        return self

    def commit(self) -> None:
        if self._connection is None:
            raise RuntimeError("unit of work is not active")
        if self._operation_ref is not None:
            self._connection.execute(
                f"INSERT INTO {MARKER_TABLE}(operation_ref, committed_at) VALUES (?, datetime('now'))",
                (self._operation_ref,),
            )
        self._connection.commit()
        self._committed = True

    def rollback(self) -> None:
        if self._connection is not None and self._connection.in_transaction:
            self._connection.rollback()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._connection is not None:
            if exc_type is not None or not self._committed:
                self.rollback()
            self._connection.close()
        return False


def operation_committed(path: Path, operation_ref: str) -> bool:
    with connect_sqlite(path, readonly=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (MARKER_TABLE,),
        ).fetchone()
        if exists is None:
            return False
        return (
            connection.execute(
                f"SELECT 1 FROM {MARKER_TABLE} WHERE operation_ref = ?", (operation_ref,)
            ).fetchone()
            is not None
        )
