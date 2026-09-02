from collections.abc import Callable
from typing import cast

import pytest

from backend.adapters.outbound.persistence.vocabulary import (
    MAPPED_VOCABULARY_FAMILIES,
    SQLiteVocabularyMappingError,
    decode_audit,
    decode_context_origin,
    decode_document,
    decode_notion,
    decode_production,
    decode_promotion,
    decode_quality,
    decode_resource,
    decode_session,
    decode_task,
    decode_validation,
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
    MAX_AUDIT_PAYLOAD_BYTES,
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


def test_exactly_ten_owner_mapping_families_are_registered() -> None:
    assert MAPPED_VOCABULARY_FAMILIES == (
        "notion",
        "document",
        "resource",
        "context",
        "session",
        "task",
        "production",
        "validation",
        "quality_promotion",
        "audit",
    )


def test_notion_vocabulary_round_trips() -> None:
    values = NotionPersistenceValues(
        KnowledgeLanguageCode.FR, NotionIdentityStatus.CANONICAL
    )
    assert encode_notion(values) == ("fr", "CANONICAL")
    assert decode_notion(*encode_notion(values)) == values


def test_document_vocabulary_round_trips() -> None:
    values = DocumentPersistenceValues(
        DocumentType.OTHER, DocumentLanguageCode.FR, DocumentStatus.ACTIVE
    )
    assert encode_document(values) == ("OTHER", "fr", "ACTIVE")
    assert decode_document(*encode_document(values)) == values


def test_resource_observed_states_remain_distinct_and_round_trip() -> None:
    active = ResourcePersistenceValues(ResourceType.EXERCISE_SET, ResourceIdentityStatus.ACTIVE)
    canonical = ResourcePersistenceValues(ResourceType.OTHER, ResourceIdentityStatus.CANONICAL)

    assert decode_resource(*encode_resource(active)) == active
    assert decode_resource(*encode_resource(canonical)) == canonical
    assert active.identity_status is not canonical.identity_status


def test_context_origin_is_validated_but_never_encoded_as_pedagogical_notes() -> None:
    origin = ContextOrigin(ContextOriginCode.RUNTIME)

    assert encode_context_origin(origin) is None
    assert decode_context_origin("runtime") == origin


def test_all_session_lifecycle_values_round_trip_exhaustively() -> None:
    assert {
        decode_session(encode_session(status)) for status in SessionLifecycleStatus
    } == set(SessionLifecycleStatus)
    with pytest.raises(TypeError, match="SessionLifecycleStatus"):
        encode_session(cast(SessionLifecycleStatus, "ACTIVE"))


def test_task_vocabulary_round_trips() -> None:
    values = TaskPersistenceValues(
        TaskType.RUNTIME_CONTRACT, TaskObjectiveRef("contract"), TaskStatus.COMPLETED
    )
    assert decode_task(*encode_task(values)) == values


def test_production_vocabulary_round_trips() -> None:
    values = ProductionPersistenceValues(
        ProductionType.OTHER,
        ProductionTitle("runtime production"),
        ProductionLifecycleStatus.VALIDATED,
    )
    assert decode_production(*encode_production(values)) == values


def test_validation_vocabulary_round_trips() -> None:
    values = ValidationPersistenceValues(
        ValidationType.RUNTIME_CONTRACT,
        ValidationResult.PASS,
        ValidatorRef("sqlite adapter"),
    )
    assert decode_validation(*encode_validation(values)) == values


def test_quality_and_promotion_keep_separate_owner_mappings() -> None:
    quality = QualityPersistenceValues(
        QualityEvaluationStatus.COMPLETED, QualityScore(1.0)
    )
    promotion = PromotionPersistenceValues(
        PromotionStatus.PROMOTED, PromotionJustification("runtime contract")
    )

    assert decode_quality(*encode_quality(quality)) == quality
    assert decode_promotion(*encode_promotion(promotion)) == promotion


def test_audit_payload_is_canonical_bounded_and_round_trips() -> None:
    values = AuditPersistenceValues(
        AuditEventType.RUNTIME_PORT_CONTRACT,
        AuditActorRef("sqlite adapter"),
        AuditPayload.from_mapping({"b": 2, "a": 1}),
    )

    assert values.payload.serialized_json == '{"a":1,"b":2}'
    assert decode_audit(*encode_audit(values)) == values
    with pytest.raises(ValueError, match="payload limit"):
        AuditPayload('{"value":"' + ("x" * MAX_AUDIT_PAYLOAD_BYTES) + '"}')


UNKNOWN_DECODERS: tuple[Callable[[], object], ...] = (
    lambda: decode_notion("xx", "CANONICAL"),
    lambda: decode_document("UNKNOWN", "fr", "ACTIVE"),
    lambda: decode_resource("UNKNOWN", "ACTIVE"),
    lambda: decode_context_origin("unknown"),
    lambda: decode_session("UNKNOWN"),
    lambda: decode_task("UNKNOWN", "contract", "COMPLETED"),
    lambda: decode_production("UNKNOWN", "title", "VALIDATED"),
    lambda: decode_validation("UNKNOWN", "PASS", "validator"),
    lambda: decode_quality("UNKNOWN", 1.0),
    lambda: decode_audit("UNKNOWN", "actor", "{}"),
)


@pytest.mark.parametrize("decoder", UNKNOWN_DECODERS)
def test_each_mapping_family_rejects_unknown_values(decoder: Callable[[], object]) -> None:
    with pytest.raises(SQLiteVocabularyMappingError, match="unknown"):
        decoder()
