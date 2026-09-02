from __future__ import annotations

from enum import StrEnum
from typing import cast

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

MAPPED_VOCABULARY_FAMILIES = (
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


class SQLiteVocabularyMappingError(ValueError):
    """A persisted vocabulary value cannot be decoded by its owning context."""


def _decode_enum[EnumValue: StrEnum](
    raw: object, enum_type: type[EnumValue], family: str
) -> EnumValue:
    if type(raw) is not str:
        raise SQLiteVocabularyMappingError(f"{family} vocabulary value must be text")
    try:
        return enum_type(raw)
    except ValueError as error:
        raise SQLiteVocabularyMappingError(f"unknown {family} vocabulary value") from error


def _decode_text(raw: object, family: str) -> str:
    if type(raw) is not str or not raw.strip():
        raise SQLiteVocabularyMappingError(f"{family} vocabulary value must be non-empty text")
    return raw


def encode_notion(values: NotionPersistenceValues) -> tuple[str, str]:
    if not isinstance(values, NotionPersistenceValues):
        raise TypeError("values must be NotionPersistenceValues")
    return values.language_code.value, values.identity_status.value


def decode_notion(language: object, status: object) -> NotionPersistenceValues:
    return NotionPersistenceValues(
        _decode_enum(language, KnowledgeLanguageCode, "notion language"),
        _decode_enum(status, NotionIdentityStatus, "notion identity"),
    )


def encode_document(values: DocumentPersistenceValues) -> tuple[str, str, str]:
    if not isinstance(values, DocumentPersistenceValues):
        raise TypeError("values must be DocumentPersistenceValues")
    return values.document_type.value, values.language_code.value, values.status.value


def decode_document(
    document_type: object, language: object, status: object
) -> DocumentPersistenceValues:
    return DocumentPersistenceValues(
        _decode_enum(document_type, DocumentType, "document type"),
        _decode_enum(language, DocumentLanguageCode, "document language"),
        _decode_enum(status, DocumentStatus, "document status"),
    )


def encode_resource(values: ResourcePersistenceValues) -> tuple[str, str]:
    if not isinstance(values, ResourcePersistenceValues):
        raise TypeError("values must be ResourcePersistenceValues")
    return values.resource_type.value, values.identity_status.value


def decode_resource(resource_type: object, status: object) -> ResourcePersistenceValues:
    return ResourcePersistenceValues(
        _decode_enum(resource_type, ResourceType, "resource type"),
        _decode_enum(status, ResourceIdentityStatus, "resource identity"),
    )


def encode_context_origin(origin: ContextOrigin) -> None:
    """Validate origin while keeping it out of pedagogical notes.

    There is no approved physical column for this technical metadata. Returning
    ``None`` is deliberate and does not resolve the open schema question.
    """

    if not isinstance(origin, ContextOrigin):
        raise TypeError("origin must be a ContextOrigin")
    return None


def decode_context_origin(raw: object) -> ContextOrigin:
    return ContextOrigin(_decode_enum(raw, ContextOriginCode, "context origin"))


def encode_session(status: SessionLifecycleStatus) -> str:
    if not isinstance(status, SessionLifecycleStatus):
        raise TypeError("status must be a SessionLifecycleStatus")
    return status.value


def decode_session(raw: object) -> SessionLifecycleStatus:
    return _decode_enum(raw, SessionLifecycleStatus, "session lifecycle")


def encode_task(values: TaskPersistenceValues) -> tuple[str, str, str]:
    if not isinstance(values, TaskPersistenceValues):
        raise TypeError("values must be TaskPersistenceValues")
    return values.task_type.value, values.objective_ref.value, values.status.value


def decode_task(task_type: object, objective: object, status: object) -> TaskPersistenceValues:
    try:
        return TaskPersistenceValues(
            _decode_enum(task_type, TaskType, "task type"),
            TaskObjectiveRef(_decode_text(objective, "task objective")),
            _decode_enum(status, TaskStatus, "task status"),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, SQLiteVocabularyMappingError):
            raise
        raise SQLiteVocabularyMappingError("invalid task vocabulary value") from error


def encode_production(values: ProductionPersistenceValues) -> tuple[str, str, str]:
    if not isinstance(values, ProductionPersistenceValues):
        raise TypeError("values must be ProductionPersistenceValues")
    return values.production_type.value, values.title.value, values.lifecycle_status.value


def decode_production(
    production_type: object, title: object, status: object
) -> ProductionPersistenceValues:
    try:
        return ProductionPersistenceValues(
            _decode_enum(production_type, ProductionType, "production type"),
            ProductionTitle(_decode_text(title, "production title")),
            _decode_enum(status, ProductionLifecycleStatus, "production lifecycle"),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, SQLiteVocabularyMappingError):
            raise
        raise SQLiteVocabularyMappingError("invalid production vocabulary value") from error


def encode_validation(values: ValidationPersistenceValues) -> tuple[str, str, str]:
    if not isinstance(values, ValidationPersistenceValues):
        raise TypeError("values must be ValidationPersistenceValues")
    return values.validation_type.value, values.result.value, values.validator_ref.value


def decode_validation(
    validation_type: object, result: object, validator: object
) -> ValidationPersistenceValues:
    try:
        return ValidationPersistenceValues(
            _decode_enum(validation_type, ValidationType, "validation type"),
            _decode_enum(result, ValidationResult, "validation result"),
            ValidatorRef(_decode_text(validator, "validation actor")),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, SQLiteVocabularyMappingError):
            raise
        raise SQLiteVocabularyMappingError("invalid validation vocabulary value") from error


def encode_quality(values: QualityPersistenceValues) -> tuple[str, float]:
    if not isinstance(values, QualityPersistenceValues):
        raise TypeError("values must be QualityPersistenceValues")
    return values.status.value, values.score.value


def decode_quality(status: object, score: object) -> QualityPersistenceValues:
    if type(score) not in (float, int):
        raise SQLiteVocabularyMappingError("quality score must be numeric")
    try:
        return QualityPersistenceValues(
            _decode_enum(status, QualityEvaluationStatus, "quality status"),
            QualityScore(float(cast(float | int, score))),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, SQLiteVocabularyMappingError):
            raise
        raise SQLiteVocabularyMappingError("invalid quality vocabulary value") from error


def encode_promotion(values: PromotionPersistenceValues) -> tuple[str, str]:
    if not isinstance(values, PromotionPersistenceValues):
        raise TypeError("values must be PromotionPersistenceValues")
    return values.status.value, values.justification.value


def decode_promotion(status: object, justification: object) -> PromotionPersistenceValues:
    try:
        return PromotionPersistenceValues(
            _decode_enum(status, PromotionStatus, "promotion status"),
            PromotionJustification(_decode_text(justification, "promotion justification")),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, SQLiteVocabularyMappingError):
            raise
        raise SQLiteVocabularyMappingError("invalid promotion vocabulary value") from error


def encode_audit(values: AuditPersistenceValues) -> tuple[str, str, str]:
    if not isinstance(values, AuditPersistenceValues):
        raise TypeError("values must be AuditPersistenceValues")
    return values.event_type.value, values.actor_ref.value, values.payload.serialized_json


def decode_audit(event_type: object, actor: object, payload: object) -> AuditPersistenceValues:
    try:
        return AuditPersistenceValues(
            _decode_enum(event_type, AuditEventType, "audit event"),
            AuditActorRef(_decode_text(actor, "audit actor")),
            AuditPayload(_decode_text(payload, "audit payload")),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, SQLiteVocabularyMappingError):
            raise
        raise SQLiteVocabularyMappingError("invalid audit vocabulary value") from error
