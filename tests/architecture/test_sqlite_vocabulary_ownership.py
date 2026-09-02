from pathlib import Path

from backend.adapters.outbound.persistence.vocabulary import MAPPED_VOCABULARY_FAMILIES
from backend.modules.audit_traceability.application.dto.persistence_vocabulary import (
    AuditEventType,
)
from backend.modules.documents_provenance.domain.value_objects.persistence_vocabulary import (
    DocumentType,
)
from backend.modules.knowledge_reference.domain.value_objects.persistence_vocabulary import (
    KnowledgeLanguageCode,
)
from backend.modules.lifecycle_promotion.domain.value_objects.persistence_vocabulary import (
    PromotionStatus,
)
from backend.modules.pedagogical_context.application.dto.context_origin import ContextOrigin
from backend.modules.quality_evaluation.domain.value_objects.persistence_vocabulary import (
    QualityEvaluationStatus,
)
from backend.modules.resource_library.domain.value_objects.persistence_vocabulary import (
    ResourceType,
)
from backend.modules.transformation_assembly.domain.value_objects.persistence_vocabulary import (
    ProductionType,
)
from backend.modules.validation_control.application.dto.persistence_vocabulary import ValidationType
from backend.modules.work_orchestration.application.dto.task_persistence import TaskType
from backend.modules.work_orchestration.domain.value_objects.session_lifecycle import (
    SessionLifecycleStatus,
)

ROOT = Path(__file__).parents[2]


def test_ten_vocabularies_are_owned_by_their_bounded_contexts() -> None:
    owner_families = (
        (KnowledgeLanguageCode,),
        (DocumentType,),
        (ResourceType,),
        (ContextOrigin,),
        (SessionLifecycleStatus,),
        (TaskType,),
        (ProductionType,),
        (ValidationType,),
        (QualityEvaluationStatus, PromotionStatus),
        (AuditEventType,),
    )
    owner_types = tuple(owner_type for family in owner_families for owner_type in family)

    assert len(MAPPED_VOCABULARY_FAMILIES) == 10
    assert len(owner_families) == 10
    assert all(value.__module__.startswith("backend.modules.") for value in owner_types)
    assert all("shared_kernel" not in value.__module__ for value in owner_types)


def test_owner_modules_do_not_depend_on_sqlite_or_outbound_adapters() -> None:
    offenders: list[str] = []
    for path in (ROOT / "backend" / "modules").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "sqlite3" in source or "backend.adapters" in source:
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_sqlite_store_contains_no_untyped_owner_vocabulary_literals() -> None:
    source = (
        ROOT / "backend" / "adapters" / "outbound" / "persistence" / "sqlite.py"
    ).read_text(encoding="utf-8")
    forbidden_literals = (
        '"fr"',
        '"CANONICAL"',
        '"ACTIVE"',
        '"COMPLETED"',
        '"VALIDATED"',
        '"PROMOTED"',
        '"PASS"',
        '"RUNTIME_CONTRACT"',
        '"RUNTIME_PORT_CONTRACT"',
        '"runtime production"',
        '"runtime contract"',
        '"sqlite adapter"',
        '"{}"',
    )

    assert [literal for literal in forbidden_literals if literal in source] == []


def test_context_origin_is_not_persisted_in_pedagogical_notes() -> None:
    source = (
        ROOT / "backend" / "adapters" / "outbound" / "persistence" / "sqlite.py"
    ).read_text(encoding="utf-8")

    assert "encode_context_origin(origin)" in source
    assert '(context_ref, context_key, "runtime")' not in source
