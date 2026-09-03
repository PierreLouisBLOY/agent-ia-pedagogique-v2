"""Composition root factory for the migrated SQLite runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import (
    EvidenceClockPort,
    SQLiteEvidenceDocumentContentAdapter,
    SQLiteEvidenceSearchAdapter,
)
from backend.adapters.outbound.persistence.migrations import (
    RuntimeProvisioningReport,
    provision_runtime,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.read_models.sqlite import ReadModelAdapter
from backend.adapters.outbound.resource_library.sqlite import SQLiteResourceStoreAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.adapters.outbound.semantic import SemanticPassage, SemanticSearchBackend
from backend.adapters.outbound.transaction.sqlite import SQLiteUnitOfWork
from backend.infrastructure.config.loaders.sqlite import load_sqlite_paths
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

    def evidence_search(
        self,
        semantic_backend: SemanticSearchBackend | None = None,
    ) -> SQLiteEvidenceSearchAdapter:
        return SQLiteEvidenceSearchAdapter(
            self.business_search(),
            semantic_backend=semantic_backend,
        )

    def semantic_passages(self) -> tuple[SemanticPassage, ...]:
        search = self.business_search()
        try:
            return tuple(
                SemanticPassage(
                    canonical_object_ref=item.canonical_object_ref,
                    passage_ref=item.passage_ref,
                    version_or_checksum=item.version_or_checksum,
                    object_type=item.object_type,
                    chunk_type=item.chunk_type,
                    text=item.text,
                    semantic_aliases=item.semantic_aliases,
                    semantic_context=item.semantic_context,
                    semantic_rollup_refs=item.semantic_rollup_refs,
                )
                for item in search.canonical_search_passages()
            )
        finally:
            search.close()

    def evidence_document_content(
        self, clock: EvidenceClockPort
    ) -> SQLiteEvidenceDocumentContentAdapter:
        return SQLiteEvidenceDocumentContentAdapter(self.document_content(), clock)

    def resource_store(self) -> SQLiteResourceStoreAdapter:
        return SQLiteResourceStoreAdapter(
            connect_sqlite(self.paths.runtime_database_path, readonly=True)
        )


def build_sqlite_runtime(
    paths: SQLiteDatabasePaths, migration_path: Path
) -> SQLiteRuntimeComposition:
    readiness = provision_runtime(
        paths.canonical_seed_path, paths.runtime_database_path, migration_path
    )
    return SQLiteRuntimeComposition(paths, migration_path, readiness)


def build_configured_sqlite_runtime(
    environment: Mapping[str, str],
    migration_path: Path,
    *,
    platform_name: str | None = None,
) -> SQLiteRuntimeComposition:
    """Compose the existing runtime from the portable injected configuration."""

    return build_sqlite_runtime(
        load_sqlite_paths(environment, platform_name=platform_name), migration_path
    )
