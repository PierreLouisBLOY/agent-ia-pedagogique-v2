from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.ports.outbound.exact_resource_evidence import (
    ExactResourceEvidenceRecord,
    ExactResourceQuestionRecord,
)
from backend.shared_kernel._strings import require_non_empty

EXACT_RESOURCE_EVIDENCE_CONTRACT = "R6-U1-EXACT-RESOURCE-EVIDENCE-1.0"
EXACT_RESOURCE_PROVENANCE_LABEL = (
    "REFERENCE_LOCALE_R6_EXACT_V1 — aucune autorité officielle ou validation "
    "pédagogique attestée"
)
MAX_EXACT_RESOURCE_BYTES = 65_536
MAX_EXACT_RESOURCE_QUESTIONS = 20
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ExactResourceQuestionView:
    question_id: str
    position: int
    points: float
    prompt: str
    prompt_sha256: str
    correction_id: str
    correction: str
    correction_sha256: str

    def __post_init__(self) -> None:
        for name in ("question_id", "prompt", "correction_id", "correction"):
            require_non_empty(getattr(self, name), name)
        if type(self.position) is not int or self.position < 1:
            raise ValueError("R6_RESOURCE_SHAPE_INVALID")
        if isinstance(self.points, bool) or not isinstance(self.points, (int, float)):
            raise TypeError("points must be numeric")
        if self.points < 0:
            raise ValueError("R6_RESOURCE_SHAPE_INVALID")
        if self.prompt_sha256 != _digest(self.prompt):
            raise ValueError("R6_QUESTION_HASH_MISMATCH")
        if self.correction_sha256 != _digest(self.correction):
            raise ValueError("R6_CORRECTION_HASH_MISMATCH")

    @classmethod
    def from_record(cls, record: ExactResourceQuestionRecord) -> ExactResourceQuestionView:
        return cls(
            question_id=record.question_id,
            position=record.position,
            points=float(record.points),
            prompt=record.prompt,
            prompt_sha256=_digest(record.prompt),
            correction_id=record.correction_id,
            correction=record.correction,
            correction_sha256=_digest(record.correction),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "question_id": self.question_id,
            "position": self.position,
            "points": self.points,
            "prompt": self.prompt,
            "prompt_sha256": self.prompt_sha256,
            "correction_id": self.correction_id,
            "correction": self.correction,
            "correction_sha256": self.correction_sha256,
        }


@dataclass(frozen=True, slots=True)
class ExactResourceEvidenceView:
    resource_ref: ResourceRef
    resource_version_ref: str
    resource_type: str
    canonical_title: str
    identity_status: str
    resource_lifecycle_status: str
    resource_validation_status: str
    body: str
    body_sha256: str
    questions: tuple[ExactResourceQuestionView, ...]
    provenance_label: str = EXACT_RESOURCE_PROVENANCE_LABEL

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
        if self.body_sha256 != _digest(self.body):
            raise ValueError("R6_RESOURCE_BODY_HASH_MISMATCH")
        if self.provenance_label != EXACT_RESOURCE_PROVENANCE_LABEL:
            raise ValueError("R6_RESOURCE_PROVENANCE_LABEL")
        if not isinstance(self.questions, tuple):
            raise TypeError("questions must be a tuple")
        if len(self.questions) > MAX_EXACT_RESOURCE_QUESTIONS:
            raise ValueError("R6_RESOURCE_PROJECTION_TOO_LARGE")
        order = tuple((item.position, item.question_id) for item in self.questions)
        if order != tuple(sorted(order)) or len({item.question_id for item in self.questions}) != len(self.questions):
            raise ValueError("R6_RESOURCE_SHAPE_INVALID")
        encoded = json.dumps(
            self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) > MAX_EXACT_RESOURCE_BYTES:
            raise ValueError("R6_RESOURCE_PROJECTION_TOO_LARGE")

    @classmethod
    def from_record(cls, record: ExactResourceEvidenceRecord) -> ExactResourceEvidenceView:
        return cls(
            resource_ref=record.resource_ref,
            resource_version_ref=record.resource_version_ref,
            resource_type=record.resource_type,
            canonical_title=record.canonical_title,
            identity_status=record.identity_status,
            resource_lifecycle_status=record.resource_lifecycle_status,
            resource_validation_status=record.resource_validation_status,
            body=record.body,
            body_sha256=_digest(record.body),
            questions=tuple(
                ExactResourceQuestionView.from_record(question)
                for question in record.questions
            ),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "contract_id": EXACT_RESOURCE_EVIDENCE_CONTRACT,
            "resource_ref": self.resource_ref.value,
            "resource_version_ref": self.resource_version_ref,
            "resource_type": self.resource_type,
            "canonical_title": self.canonical_title,
            "identity_status": self.identity_status,
            "resource_lifecycle_status": self.resource_lifecycle_status,
            "resource_validation_status": self.resource_validation_status,
            "body": self.body,
            "body_sha256": self.body_sha256,
            "questions": [question.as_dict() for question in self.questions],
            "provenance_label": self.provenance_label,
        }

    def evidence_text(self) -> str:
        parts = [self.body]
        for question in self.questions:
            parts.extend((question.prompt, question.correction))
        return "\n".join(parts)
