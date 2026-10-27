"""Exact-version student-safe R6 P0 read view."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import (
    P0_RETENTION,
    P0Production,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

P0_VIEW_CONTRACT = "R6-P0-PRODUCTION-VIEW-1.0"
COURSE_VIEW_CONTRACT = "R6-P0-PRODUCTION-VIEW-COURSE-2.0"
MEDIA_VIEW_CONTRACT = "R6-P0-PRODUCTION-VIEW-MEDIA-3.0"
_FIELDS = {
    "contract_id",
    "production_ref",
    "version_ref",
    "production_kind",
    "question_mode",
    "title",
    "sections",
    "questions",
    "pedagogical_context",
    "context_sha256",
    "lineage",
    "references",
    "validation_state",
    "limitations",
    "retention",
    "bundle_sha256",
}


@dataclass(frozen=True, slots=True)
class P0ProductionReadView:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        chapter = self.data.get("contract_id") == COURSE_VIEW_CONTRACT
        media = self.data.get("contract_id") == MEDIA_VIEW_CONTRACT
        data = object_data(self.data, _FIELDS | ({"course_chapter"} if chapter else {"media_assets"} if media else set()))
        if data["contract_id"] not in {P0_VIEW_CONTRACT, COURSE_VIEW_CONTRACT, MEDIA_VIEW_CONTRACT}:
            raise ValueError("P0_VIEW_CONTRACT")
        if chapter and "teacher_answers" in object_data(data["course_chapter"]):
            raise ValueError("COURSE_STUDENT_ANSWER_FORBIDDEN")
        if data["production_kind"] not in {"COURSE", "EXERCISE", "QUESTION_SET", "ASSESSMENT"}:
            raise ValueError("P0_VIEW_KIND")
        if data["validation_state"] != "CANDIDATE" or data["retention"] != P0_RETENTION:
            raise ValueError("P0_VIEW_STATE")
        bundle_data = {
            "contract_id": "R6-P0-PRODUCTION-1.0",
            "production_ref": data["production_ref"],
            "version_ref": data["version_ref"],
            "title": data["title"],
            "context": data["pedagogical_context"],
            "context_sha256": data["context_sha256"],
            "sections": data["sections"],
            "questions": data["questions"],
            "corrections": (),
            "marking": (),
            "references": data["references"],
            "lineage": data["lineage"],
            "limitations": data["limitations"],
        }
        # A full bundle cannot be reconstructed from a student-safe view. Validate the
        # neutral identity and structural fields directly; SavedProduction binds the view
        # to the full bundle and its hash.
        if not isinstance(data["bundle_sha256"], str) or len(data["bundle_sha256"]) != 64:
            raise ValueError("P0_VIEW_BUNDLE_HASH")
        if not all(character in "0123456789abcdef" for character in data["bundle_sha256"]):
            raise ValueError("P0_VIEW_BUNDLE_HASH")
        object_data(bundle_data)
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @classmethod
    def from_bundle(cls, bundle: P0Production) -> P0ProductionReadView:
        context = bundle.context
        data = {
                "contract_id": COURSE_VIEW_CONTRACT if "course_chapter" in bundle.data else MEDIA_VIEW_CONTRACT if "media_plan" in bundle.data else P0_VIEW_CONTRACT,
                "production_ref": bundle.production_ref,
                "version_ref": bundle.version_ref,
                "production_kind": context.resource_type,
                "question_mode": context.question_mode,
                "title": bundle.data["title"],
                "sections": as_plain(bundle.data["sections"]),
                "questions": as_plain(bundle.data["questions"]),
                "pedagogical_context": context.as_dict(),
                "context_sha256": context.sha256,
                "lineage": as_plain(bundle.data["lineage"]),
                "references": as_plain(bundle.data["references"]),
                "validation_state": "CANDIDATE",
                "limitations": as_plain(bundle.data["limitations"]),
                "retention": P0_RETENTION,
                "bundle_sha256": bundle.sha256,
            }
        if "course_chapter" in bundle.data:
            data["course_chapter"] = bundle.student_projection()["course_chapter"]
        if "media_plan" in bundle.data:
            data["media_assets"] = bundle.student_projection()["media_assets"]
        return cls(data)

    @property
    def production_ref(self) -> str:
        return str(self.data["production_ref"])

    @property
    def version_ref(self) -> str:
        return str(self.data["version_ref"])

    @property
    def conversation_id(self) -> str:
        return str(object_data(self.data["lineage"])["conversation_id"])
