"""Composition root factory for the migrated SQLite runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.persistence.migrations import (
    RuntimeProvisioningReport,
    provision_runtime,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.read_models.sqlite import ReadModelAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.adapters.outbound.transaction.sqlite import SQLiteUnitOfWork
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths


@dataclass(frozen=True, slots=True)
class SQLiteRuntimeComposition:
    paths: SQLiteDatabasePaths
    migration_path: Path
    readiness: RuntimeProvisioningReport

    def unit_of_work(self, *, operation_ref: str | None = None) -> SQLiteUnitOfWork:
        return SQLiteUnitOfWork(self.paths.runtime_database_path, operation_ref=operation_ref)

    def business_search(self) -> BusinessSearchAdapter:
        return BusinessSearchAdapter(connect_sqlite(self.paths.runtime_database_path, readonly=True))

    def read_models(self) -> ReadModelAdapter:
        return ReadModelAdapter(connect_sqlite(self.paths.runtime_database_path, readonly=True))

    def document_content(self) -> DocumentContentAccessAdapter:
        return DocumentContentAccessAdapter(
            connect_sqlite(self.paths.runtime_database_path, readonly=True)
        )


def build_sqlite_runtime(
    paths: SQLiteDatabasePaths, migration_path: Path
) -> SQLiteRuntimeComposition:
    readiness = provision_runtime(
        paths.canonical_seed_path, paths.runtime_database_path, migration_path
    )
    return SQLiteRuntimeComposition(paths, migration_path, readiness)
