"""Composition root factory for the migrated SQLite runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import (
    EvidenceClockPort,
    SQLiteEvidenceDocumentContentAdapter,
    SQLiteEvidenceSearchAdapter,
)
from backend.adapters.outbound.persistence.migrations import (
    DatabaseEvidence,
    MigrationRegistry,
    RuntimeBackupReport,
    RuntimeProvisioningReport,
    create_runtime_backup,
    migration_registry,
    provision_runtime,
    restore_runtime_backup,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.read_models.sqlite import ReadModelAdapter
from backend.adapters.outbound.resource_library.sqlite import SQLiteResourceStoreAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.adapters.outbound.semantic import SemanticPassage, SemanticSearchBackend
from backend.adapters.outbound.transaction.sqlite import SQLiteUnitOfWork
from backend.infrastructure.composition.bootstrap.observability import (
    LocalObservabilitySession,
)
from backend.infrastructure.config.loaders.sqlite import load_sqlite_paths
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths


@dataclass(frozen=True, slots=True)
class SQLiteRuntimeComposition:
    paths: SQLiteDatabasePaths
    migration_path: Path | MigrationRegistry
    readiness: RuntimeProvisioningReport
    observability: LocalObservabilitySession | None = field(
        default=None,
        repr=False,
    )

    def unit_of_work(self, *, operation_ref: str | None = None) -> SQLiteUnitOfWork:
        return SQLiteUnitOfWork(self.paths.runtime_database_path, operation_ref=operation_ref)

    def business_search(self) -> BusinessSearchAdapter:
        return BusinessSearchAdapter(
            connect_sqlite(
                self.paths.runtime_database_path,
                readonly=True,
                allowed_root=self.paths.data_directory,
            )
        )

    def read_models(self) -> ReadModelAdapter:
        return ReadModelAdapter(
            connect_sqlite(
                self.paths.runtime_database_path,
                readonly=True,
                allowed_root=self.paths.data_directory,
            )
        )

    def document_content(self) -> DocumentContentAccessAdapter:
        return DocumentContentAccessAdapter(
            connect_sqlite(
                self.paths.runtime_database_path,
                readonly=True,
                allowed_root=self.paths.data_directory,
            )
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
            connect_sqlite(
                self.paths.runtime_database_path,
                readonly=True,
                allowed_root=self.paths.data_directory,
            )
        )

    def create_backup(self, backup_path: Path) -> RuntimeBackupReport:
        try:
            report = create_runtime_backup(
                self.paths.runtime_database_path,
                backup_path,
                data_root=self.paths.data_directory,
                canonical_seed_path=self.paths.canonical_seed_path,
            )
        except Exception as error:
            if self.observability is not None:
                self.observability.sqlite_artifact_operation(
                    recovery=False,
                    succeeded=False,
                    closed_error_code=type(error).__name__,
                )
            raise
        if self.observability is not None:
            self.observability.sqlite_artifact_operation(
                recovery=False,
                succeeded=True,
                artifact_digest=report.backup_sha256,
            )
        return report

    def restore_backup(self, backup_path: Path, target_path: Path) -> DatabaseEvidence:
        try:
            evidence = restore_runtime_backup(
                backup_path,
                target_path,
                canonical_seed_path=self.paths.canonical_seed_path,
                data_root=self.paths.data_directory,
            )
        except Exception as error:
            if self.observability is not None:
                self.observability.sqlite_artifact_operation(
                    recovery=True,
                    succeeded=False,
                    closed_error_code=type(error).__name__,
                )
            raise
        if self.observability is not None:
            self.observability.sqlite_artifact_operation(
                recovery=True,
                succeeded=True,
                artifact_digest=evidence.sha256,
            )
        return evidence


def build_sqlite_runtime(
    paths: SQLiteDatabasePaths,
    migration_path: Path | MigrationRegistry,
    *,
    observability: LocalObservabilitySession | None = None,
) -> SQLiteRuntimeComposition:
    registry = (
        migration_path
        if isinstance(migration_path, MigrationRegistry)
        else migration_registry(migration_path)
    )
    latest = registry.specs[-1]
    if observability is not None:
        observability.sqlite_bootstrap_started(schema_version=latest.version)
        observability.sqlite_migration(
            started=True,
            succeeded=False,
            from_version="000",
            to_version=latest.version,
            migration_id=latest.name,
            migration_checksum=latest.checksum,
        )
    try:
        readiness = provision_runtime(
            paths.canonical_seed_path,
            paths.runtime_database_path,
            registry,
            data_root=paths.data_directory,
        )
    except Exception as error:
        if observability is not None:
            closed_error_code = type(error).__name__
            observability.sqlite_migration(
                started=False,
                succeeded=False,
                from_version="000",
                to_version=latest.version,
                migration_id=latest.name,
                migration_checksum=latest.checksum,
                closed_error_code=closed_error_code,
            )
            observability.sqlite_bootstrap_failed(
                schema_version=latest.version,
                closed_error_code=closed_error_code,
            )
        raise
    if observability is not None:
        observability.sqlite_migration(
            started=False,
            succeeded=True,
            from_version="000",
            to_version=latest.version,
            migration_id=latest.name,
            migration_checksum=latest.checksum,
        )
        observability.sqlite_bootstrap_completed(
            schema_version=readiness.migration_version,
            seed_identity_digest=readiness.seed.sha256,
            runtime_identity_digest=readiness.runtime_sha256,
        )
    return SQLiteRuntimeComposition(paths, registry, readiness, observability)


def build_configured_sqlite_runtime(
    environment: Mapping[str, str],
    migration_path: Path | MigrationRegistry,
    *,
    platform_name: str | None = None,
    observability: LocalObservabilitySession | None = None,
) -> SQLiteRuntimeComposition:
    """Compose the existing runtime from the portable injected configuration."""

    paths = load_sqlite_paths(environment, platform_name=platform_name)
    if observability is None:
        return build_sqlite_runtime(paths, migration_path)
    return build_sqlite_runtime(paths, migration_path, observability=observability)
