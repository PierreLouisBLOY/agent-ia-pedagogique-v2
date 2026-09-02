from __future__ import annotations

import os
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.persistence.migrations import (
    CANONICAL_SEED_SHA256,
    CANONICAL_SEED_SIZE,
    MigrationArtifact,
    MigrationChecksumMismatch,
    apply_migration,
    inspect_database,
    provision_runtime,
)
from backend.adapters.outbound.persistence.sqlite import ConcurrencyConflict, connect_sqlite
from backend.adapters.outbound.read_models.sqlite import ReadModelAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.adapters.outbound.transaction.sqlite import SQLiteUnitOfWork, operation_committed
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.modules.audit_traceability.application.dto.persistence_vocabulary import (
    AuditActorRef,
    AuditEventType,
    AuditPayload,
    AuditPersistenceValues,
)
from backend.modules.documents_provenance.domain.value_objects.persistence_vocabulary import (
    DocumentLanguageCode,
    DocumentPersistenceValues,
    DocumentStatus,
    DocumentType,
)
from backend.modules.knowledge_reference.domain.value_objects.persistence_vocabulary import (
    KnowledgeLanguageCode,
    NotionIdentityStatus,
    NotionPersistenceValues,
)
from backend.modules.lifecycle_promotion.domain.value_objects.persistence_vocabulary import (
    PromotionJustification,
    PromotionPersistenceValues,
    PromotionStatus,
)
from backend.modules.pedagogical_context.application.dto.context_origin import (
    ContextOrigin,
    ContextOriginCode,
)
from backend.modules.quality_evaluation.domain.value_objects.persistence_vocabulary import (
    QualityEvaluationStatus,
    QualityPersistenceValues,
    QualityScore,
)
from backend.modules.resource_library.domain.value_objects.persistence_vocabulary import (
    ResourceIdentityStatus,
    ResourcePersistenceValues,
    ResourceType,
)
from backend.modules.transformation_assembly.domain.value_objects.persistence_vocabulary import (
    ProductionLifecycleStatus,
    ProductionPersistenceValues,
    ProductionTitle,
    ProductionType,
)
from backend.modules.validation_control.application.dto.persistence_vocabulary import (
    ValidationPersistenceValues,
    ValidationResult,
    ValidationType,
    ValidatorRef,
)
from backend.modules.work_orchestration.application.dto.task_persistence import (
    TaskObjectiveRef,
    TaskPersistenceValues,
    TaskStatus,
    TaskType,
)
from backend.modules.work_orchestration.domain.value_objects.session_lifecycle import (
    SessionLifecycleStatus,
)

SEED_VALUE = os.environ.get(SEED_PATH_ENV)
pytestmark = pytest.mark.skipif(SEED_VALUE is None, reason=f"{SEED_PATH_ENV} is not configured")
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
NOTION_VALUES = NotionPersistenceValues(
    KnowledgeLanguageCode.FR, NotionIdentityStatus.CANONICAL
)
DOCUMENT_VALUES = DocumentPersistenceValues(
    DocumentType.OTHER, DocumentLanguageCode.FR, DocumentStatus.ACTIVE
)
RESOURCE_VALUES = ResourcePersistenceValues(
    ResourceType.OTHER, ResourceIdentityStatus.CANONICAL
)
CONTEXT_ORIGIN = ContextOrigin(ContextOriginCode.RUNTIME)
TASK_VALUES = TaskPersistenceValues(
    TaskType.RUNTIME_CONTRACT, TaskObjectiveRef("contract"), TaskStatus.COMPLETED
)
PRODUCTION_VALUES = ProductionPersistenceValues(
    ProductionType.OTHER,
    ProductionTitle("runtime production"),
    ProductionLifecycleStatus.VALIDATED,
)
VALIDATION_VALUES = ValidationPersistenceValues(
    ValidationType.RUNTIME_CONTRACT, ValidationResult.PASS, ValidatorRef("sqlite adapter")
)
QUALITY_VALUES = QualityPersistenceValues(
    QualityEvaluationStatus.COMPLETED, QualityScore(1.0)
)
PROMOTION_VALUES = PromotionPersistenceValues(
    PromotionStatus.PROMOTED, PromotionJustification("runtime contract")
)
AUDIT_VALUES = AuditPersistenceValues(
    AuditEventType.RUNTIME_PORT_CONTRACT,
    AuditActorRef("sqlite adapter"),
    AuditPayload.from_mapping({}),
)


@pytest.fixture(scope="module")
def seed_path() -> Path:
    assert SEED_VALUE is not None
    return Path(SEED_VALUE)


@pytest.fixture(scope="module", autouse=True)
def seed_remains_immutable(seed_path: Path) -> Iterator[None]:
    before = inspect_database(seed_path, authenticate_seed=True)
    yield
    after = inspect_database(seed_path, authenticate_seed=True)
    assert after == before


@pytest.fixture(scope="module")
def runtime_template(seed_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("sqlite-runtime") / "runtime.sqlite"
    provision_runtime(seed_path, path, MIGRATION)
    return path


@pytest.fixture
def runtime_copy(runtime_template: Path, tmp_path: Path) -> Path:
    path = tmp_path / "mutation.sqlite"
    shutil.copy2(runtime_template, path)
    return path


def test_seed_gate_is_exact_and_read_only(seed_path: Path) -> None:
    before = inspect_database(seed_path, authenticate_seed=True)
    with connect_sqlite(seed_path, readonly=True) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE forbidden_seed_write(id INTEGER)")
    after = inspect_database(seed_path, authenticate_seed=True)

    assert before == after
    assert before.size_bytes == CANONICAL_SEED_SIZE
    assert before.sha256 == CANONICAL_SEED_SHA256


def test_runtime_provisioning_applies_exact_migration(
    seed_path: Path, tmp_path: Path
) -> None:
    runtime = tmp_path / "application.sqlite"
    report = provision_runtime(seed_path, runtime, MIGRATION)

    assert report.migration_applied is True
    assert report.documents_before == report.documents_after == 15
    assert (report.domain_tables, report.explicit_indexes, report.triggers, report.views) == (
        98,
        20,
        7,
        2,
    )
    assert report.runtime_sha256 != CANONICAL_SEED_SHA256


def test_migration_replay_is_idempotent_and_checksum_mismatch_stops(
    runtime_copy: Path, tmp_path: Path
) -> None:
    artifact = MigrationArtifact.load(MIGRATION)
    with connect_sqlite(runtime_copy) as connection:
        assert apply_migration(connection, artifact) is False
        altered = tmp_path / "altered.sql"
        altered.write_text(artifact.sql + "\n-- altered\n", encoding="utf-8")
        with pytest.raises(MigrationChecksumMismatch):
            apply_migration(connection, MigrationArtifact.load(altered))


def test_op01_knowledge_store_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        notion = unit.knowledge.add_notion("C0 notion", NOTION_VALUES)
        assert unit.knowledge.load_notion(notion) is not None


def test_op02_document_store_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        document = unit.documents.add_document("C0 document", DOCUMENT_VALUES, "a" * 64)
        assert unit.documents.load_document(document) is not None


def test_op03_resource_store_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        resource = unit.resources.add_resource("C0 resource", RESOURCE_VALUES)
        assert unit.resources.load_resource(resource) is not None


def test_op04_context_store_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        context = unit.contexts.add_context("c0-context", CONTEXT_ORIGIN)
        assert unit.contexts.load_context(context) is not None


def test_op05_work_store_contract_and_expected_version(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        session = unit.work.add_session("C0 session", SessionLifecycleStatus.ACTIVE)
        loaded = unit.work.load_session(session)
        assert loaded is not None
        version = str(loaded["updated_at"])
        unit.work.change_status(
            session, SessionLifecycleStatus.PAUSED, expected_updated_at=version
        )
        with pytest.raises(ConcurrencyConflict):
            unit.work.change_status(
                session, SessionLifecycleStatus.ACTIVE, expected_updated_at=version
            )


def test_op06_validation_append_read_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        notion = unit.knowledge.add_notion("events", NOTION_VALUES)
        validation = unit.validations.append(notion, VALIDATION_VALUES)
        assert unit.validations.read(validation) is not None


def test_op07_quality_append_read_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        notion = unit.knowledge.add_notion("quality", NOTION_VALUES)
        quality = unit.quality.append(notion, QUALITY_VALUES)
        assert unit.quality.read(quality) is not None


def test_op09_audit_append_read_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        notion = unit.knowledge.add_notion("audit", NOTION_VALUES)
        audit = unit.audit.append_event(notion, AUDIT_VALUES)
        assert unit.audit.read_event(audit) is not None


def test_op08_lifecycle_contract(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy) as unit:
        session = unit.work.add_session("promotion", SessionLifecycleStatus.ACTIVE)
        task = unit.work.add_task(session, TASK_VALUES)
        production = unit.work.add_production(task, PRODUCTION_VALUES)
        resource = unit.resources.add_resource("promoted", RESOURCE_VALUES)
        promotion = unit.lifecycle.append_promotion(
            production, resource, PROMOTION_VALUES
        )
        assert unit.lifecycle.read_promotion(promotion) is not None


def test_op10_commit_rollback_operation_ref_and_reconciliation(runtime_copy: Path) -> None:
    with SQLiteUnitOfWork(runtime_copy, operation_ref="operation:c0") as unit:
        committed = unit.knowledge.add_notion("committed", NOTION_VALUES)
        unit.commit()
    assert operation_committed(runtime_copy, "operation:c0") is True
    with pytest.raises(sqlite3.IntegrityError):
        with SQLiteUnitOfWork(runtime_copy, operation_ref="operation:c0") as unit:
            unit.knowledge.add_notion("duplicate operation", NOTION_VALUES)
            unit.commit()
    with SQLiteUnitOfWork(runtime_copy) as unit:
        rolled_back = unit.knowledge.add_notion("rolled back", NOTION_VALUES)
    with connect_sqlite(runtime_copy, readonly=True) as connection:
        assert connection.execute("SELECT count(*) FROM notion WHERE id = ?", (committed,)).fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM notion WHERE id = ?", (rolled_back,)).fetchone()[0] == 0


def test_op11_real_fts_read_is_stable_and_non_authoritative(runtime_template: Path) -> None:
    with connect_sqlite(runtime_template, readonly=True) as connection:
        hits = BusinessSearchAdapter(connection).search("absence", limit=3)
    assert hits
    assert hits[0].entity_ref == "notion:absence"
    assert hits[0].entity_kind == "NOTION_LABEL"
    assert hits[0].passage_ref.startswith("search-chunk:")


def test_op12_projection_is_real_and_non_owner(runtime_template: Path) -> None:
    with connect_sqlite(runtime_template, readonly=True) as connection:
        views = ReadModelAdapter(connection).resource_catalog(limit=3)
    assert len(views) == 3
    assert all(view.projection_freshness == "seed-derived" for view in views)


def test_op13_real_read_exposes_only_logical_fragments(runtime_template: Path) -> None:
    with connect_sqlite(runtime_template, readonly=True) as connection:
        document_ref = str(connection.execute("SELECT id FROM document ORDER BY id LIMIT 1").fetchone()[0])
        adapter = DocumentContentAccessAdapter(connection)
        fragments = adapter.read_document(document_ref)
        hit = BusinessSearchAdapter(connection).search("absence", limit=1)[0]
        passage = adapter.read_passage(hit.passage_ref)
    assert fragments
    assert fragments[0].document_ref == document_ref
    assert passage is not None
    assert passage.source_ref == hit.entity_ref
    assert passage.text == hit.snippet
    assert not hasattr(fragments[0], "storage_uri")
    assert not hasattr(fragments[0], "url")


def test_composition_root_binds_migrated_runtime(seed_path: Path, tmp_path: Path) -> None:
    paths = SQLiteDatabasePaths(seed_path, tmp_path / "composed.sqlite")
    composition = build_sqlite_runtime(paths, MIGRATION)
    adapter = composition.business_search()
    try:
        assert adapter.search("absence", limit=1)
    finally:
        adapter.close()
