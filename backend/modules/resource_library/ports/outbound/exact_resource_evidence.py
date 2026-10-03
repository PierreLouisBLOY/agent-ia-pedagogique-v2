from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.shared_kernel._strings import require_non_empty


class ExactResourceLookupStatus(StrEnum):
    FOUND = "FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VERSION_NOT_FOUND = "VERSION_NOT_FOUND"
    VERSION_MISMATCH = "VERSION_MISMATCH"


@dataclass(frozen=True, slots=True)
class ExactResourceQuestionRecord:
    question_id: str
    position: int
    points: float
    prompt: str
    correction_id: str
    correction: str

    def __post_init__(self) -> None:
        for name in ("question_id", "prompt", "correction_id", "correction"):
            require_non_empty(getattr(self, name), name)
        if type(self.position) is not int or self.position < 1:
            raise ValueError("R6_RESOURCE_SHAPE_INVALID")
        if isinstance(self.points, bool) or not isinstance(self.points, (int, float)):
            raise TypeError("points must be numeric")
        if self.points < 0:
            raise ValueError("R6_RESOURCE_SHAPE_INVALID")


@dataclass(frozen=True, slots=True)
class ExactResourceEvidenceRecord:
    resource_ref: ResourceRef
    resource_version_ref: str
    resource_type: str
    canonical_title: str
    identity_status: str
    resource_lifecycle_status: str
    resource_validation_status: str
    body: str
    questions: tuple[ExactResourceQuestionRecord, ...]

    def __post_init__(self) -> None:
        if type(self.resource_ref) is not ResourceRef:
            raise TypeError("resource_ref must be a ResourceRef")
        for name in (
            "resource_version_ref",
            "resource_type",
            "canonical_title",
            "identity_status",
            "resource_lifecycle_status",
            "resource_validation_status",
            "body",
        ):
            require_non_empty(getattr(self, name), name)
        if not isinstance(self.questions, tuple):
            raise TypeError("questions must be a tuple")


@dataclass(frozen=True, slots=True)
class ExactResourceLookup:
    status: ExactResourceLookupStatus
    record: ExactResourceEvidenceRecord | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExactResourceLookupStatus):
            raise TypeError("status must be an ExactResourceLookupStatus")
        if (self.status is ExactResourceLookupStatus.FOUND) != (self.record is not None):
            raise ValueError("R6_RESOURCE_LOOKUP_SHAPE_INVALID")


@runtime_checkable
class ExactResourceEvidencePort(Protocol):
    def load_exact_resource(
        self,
        resource_ref: ResourceRef,
        resource_version_ref: str,
    ) -> ExactResourceLookup:
        ...
