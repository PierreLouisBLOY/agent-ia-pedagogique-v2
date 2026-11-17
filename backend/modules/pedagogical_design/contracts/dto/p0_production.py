"""Closed R6 P0 production contract and its student/teacher projections."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    identifier,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.case_study import (
    CASE_CONTEXT,
    CASE_PRODUCTION,
)
from backend.modules.pedagogical_design.contracts.dto.chapter_assembly import (
    ASSEMBLY_PRODUCTION_CONTRACT,
    ASSEMBLY_PROVENANCE,
)
from backend.modules.pedagogical_design.contracts.dto.production_media import (
    MEDIA_PRODUCTION_CONTRACT,
    ProductionMediaPlan,
)
from backend.modules.pedagogical_design.contracts.dto.section_identity import (
    valid_question_id,
    valid_section_id,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

P0_PRODUCTION_CONTRACT = "R6-P0-PRODUCTION-1.0"
P0_PROVENANCE_LABEL = (
    "REFERENCE_LOCALE_R6_EXACT_V1 — aucune autorité officielle ou validation "
    "pédagogique attestée"
)
P0_RETENTION = "DURABLE_R6"

_FIELDS = {
    "contract_id",
    "production_ref",
    "version_ref",
    "title",
    "context",
    "context_sha256",
    "sections",
    "questions",
    "corrections",
    "marking",
    "references",
    "lineage",
    "limitations",
}
_LINEAGE_FIELDS = {
    "source_run_id",
    "source_step_id",
    "evidence_set_ref",
    "source_request_id",
    "conversation_id",
    "context_sha256",
    "parent_version_ref",
}
_REFERENCE_FIELDS = {
    "evidence_id",
    "source_ref",
    "locator",
    "checksum_or_version",
    "excerpt_sha256",
    "provenance_label",
}


def _question_id(value: object) -> str:
    if not valid_question_id(value):
        raise ValueError("P0_QUESTION_ID")
    return value


def _points(value: object) -> Decimal:
    if not isinstance(value, str) or re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.[0-9]{2}", value) is None:
        raise ValueError("P0_MARKING_POINTS")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError("P0_MARKING_POINTS") from None
    if result <= 0:
        raise ValueError("P0_MARKING_POINTS")
    return result


def _validated_sections(value: object) -> tuple[dict[str, object], ...]:
    sections = items(value, 16)
    if not sections:
        raise ValueError("P0_SECTIONS")
    ids: list[str] = []
    for section in sections:
        object_data(section, {"section_id", "heading", "text"})
        section_id = section["section_id"]
        if not valid_section_id(section_id):
            raise ValueError("P0_SECTION_ID")
        nonempty(section["heading"], 200)
        nonempty(section["text"], 16_000)
        ids.append(section_id)
    if len(ids) != len(set(ids)):
        raise ValueError("P0_SECTIONS")
    return sections


def _validated_questions(value: object) -> tuple[dict[str, object], ...]:
    questions = items(value, 60)
    ids: list[str] = []
    for question in questions:
        object_data(question, {"question_id", "prompt", "options"})
        ids.append(_question_id(question["question_id"]))
        nonempty(question["prompt"], 4_000)
        options = question["options"]
        if not isinstance(options, (tuple, list)) or len(options) > 6:
            raise ValueError("P0_OPTIONS")
        option_values = tuple(nonempty(option, 1_000) for option in options)
        if len(option_values) != len(set(option_values)):
            raise ValueError("P0_OPTIONS")
    if len(ids) != len(set(ids)):
        raise ValueError("P0_QUESTIONS")
    return questions


def _validated_corrections(value: object) -> tuple[dict[str, object], ...]:
    corrections = items(value, 60)
    ids: list[str] = []
    for correction in corrections:
        object_data(correction, {"question_id", "expected_answer", "rationale"})
        ids.append(_question_id(correction["question_id"]))
        nonempty(correction["expected_answer"], 4_000)
        nonempty(correction["rationale"], 4_000)
    if len(ids) != len(set(ids)):
        raise ValueError("P0_CORRECTIONS")
    return corrections


def _validated_marking(value: object) -> tuple[dict[str, object], ...]:
    marking = items(value, 60)
    ids: list[str] = []
    for entry in marking:
        object_data(entry, {"question_id", "points", "criteria"})
        ids.append(_question_id(entry["question_id"]))
        _points(entry["points"])
        criteria = entry["criteria"]
        if not isinstance(criteria, (tuple, list)) or not 1 <= len(criteria) <= 8:
            raise ValueError("P0_MARKING_CRITERIA")
        tuple(nonempty(criterion, 1_000) for criterion in criteria)
    if len(ids) != len(set(ids)):
        raise ValueError("P0_MARKING")
    return marking


def _validated_references(value: object, *, local_assembly: bool = False) -> tuple[dict[str, object], ...]:
    references = items(value, 8)
    if not references:
        raise ValueError("P0_REFERENCES")
    ids: list[str] = []
    for reference in references:
        object_data(reference, _REFERENCE_FIELDS)
        evidence_id = reference["evidence_id"]
        if not isinstance(evidence_id, str) or re.fullmatch(
            r"evidence:[0-9a-f]{32}", evidence_id
        ) is None:
            raise ValueError("P0_EVIDENCE_ID")
        ids.append(evidence_id)
        nonempty(reference["source_ref"], 500)
        nonempty(reference["locator"], 1_000)
        checksum = reference["checksum_or_version"]
        if not isinstance(checksum, str) or not checksum.strip() or len(checksum) > 500:
            raise ValueError("P0_REFERENCE_VERSION")
        excerpt_sha = reference["excerpt_sha256"]
        if not isinstance(excerpt_sha, str) or re.fullmatch(r"[0-9a-f]{64}", excerpt_sha) is None:
            raise ValueError("P0_REFERENCE_HASH")
        if reference["provenance_label"] != (ASSEMBLY_PROVENANCE if local_assembly else P0_PROVENANCE_LABEL):
            raise ValueError("P0_REFERENCE_PROVENANCE")
    if len(ids) != len(set(ids)):
        raise ValueError("P0_REFERENCES")
    return references


@dataclass(frozen=True, slots=True)
class P0Production:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
            COURSE_NOTION_LINEAGE_CONTRACT,
            COURSE_NOTION_PRODUCTION_CONTRACT,
            COURSE_PRODUCTION_CONTRACT,
            CourseChapter,
        )

        is_chapter = self.data.get("contract_id") in {COURSE_PRODUCTION_CONTRACT, COURSE_NOTION_PRODUCTION_CONTRACT, ASSEMBLY_PRODUCTION_CONTRACT}
        is_media = self.data.get("contract_id") == MEDIA_PRODUCTION_CONTRACT
        from backend.modules.pedagogical_context.contracts.dto.exercise_context import (
            EXERCISE_CONTEXTS,
        )
        from backend.modules.pedagogical_design.contracts.dto.exercise_profile import (
            EXERCISE_PRODUCTION,
            StructuredExercise,
        )

        is_exercise = self.data.get("contract_id") in {EXERCISE_PRODUCTION, CASE_PRODUCTION}
        fields = _FIELDS | ({"exercise"} if is_exercise else {"course_chapter"} if is_chapter else {"media_plan"} if is_media else set())
        data = object_data(self.data, fields)
        if data["contract_id"] not in {P0_PRODUCTION_CONTRACT, COURSE_PRODUCTION_CONTRACT, COURSE_NOTION_PRODUCTION_CONTRACT, MEDIA_PRODUCTION_CONTRACT, ASSEMBLY_PRODUCTION_CONTRACT, EXERCISE_PRODUCTION, CASE_PRODUCTION}:
            raise ValueError("P0_PRODUCTION_CONTRACT")
        identifier(data["production_ref"], "prod")
        identifier(data["version_ref"], "ver")
        nonempty(data["title"], 300)
        context = P0Context(object_data(data["context"]))
        if is_exercise != (context.data["contract_id"] in EXERCISE_CONTEXTS):
            raise ValueError("EXERCISE_PRODUCTION_CONTEXT_BINDING")
        if (data["contract_id"] == COURSE_NOTION_PRODUCTION_CONTRACT) != (context.data["contract_id"] == "P0-CONTEXT-COURSE-4.0"):
            raise ValueError("P0_NOTION_COURSE_PRODUCTION_BINDING")
        if data["context_sha256"] != context.sha256:
            raise ValueError("P0_CONTEXT_HASH")
        _validated_sections(data["sections"])
        questions = _validated_questions(data["questions"])
        corrections = _validated_corrections(data["corrections"])
        marking = _validated_marking(data["marking"])
        _validated_references(data["references"], local_assembly=data["contract_id"] == ASSEMBLY_PRODUCTION_CONTRACT)
        self._validate_content(context, questions, corrections, marking)
        if (data["contract_id"] == CASE_PRODUCTION) != (context.data["contract_id"] == CASE_CONTEXT):
            raise ValueError("P0_CASE_CONTEXT_BINDING")
        if is_exercise:
            exercise = StructuredExercise(object_data(data["exercise"]), case_study=data["contract_id"] == CASE_PRODUCTION)
            exercise.bind(context.data, data["references"])
            if (as_plain(data["sections"]) != exercise.sections()
                    or as_plain(data["questions"]) != exercise.simple_questions()
                    or as_plain(data["corrections"]) != exercise.simple_answers()):
                raise ValueError("EXERCISE_SIMPLE_PROJECTION_BINDING")
        if is_media:
            ProductionMediaPlan(object_data(data["media_plan"])).bind(data)
        if is_chapter:
            chapter = CourseChapter(object_data(data["course_chapter"]))
            from backend.modules.pedagogical_context.contracts.dto.real_course_thread import (
                REAL_CHAPTER,
                thread_from_context,
                validate_real_course,
            )

            if (data["contract_id"] == COURSE_NOTION_PRODUCTION_CONTRACT) != (chapter.data["contract_id"] in {COURSE_NOTION_LINEAGE_CONTRACT, REAL_CHAPTER}):
                raise ValueError("P0_NOTION_COURSE_PRODUCTION_BINDING")
            from backend.modules.pedagogical_design.contracts.dto.chapter_assembly import (
                ASSEMBLY_CHAPTER_CONTRACT,
            )
            if (data["contract_id"] == ASSEMBLY_PRODUCTION_CONTRACT) != (chapter.data["contract_id"] == ASSEMBLY_CHAPTER_CONTRACT):
                raise ValueError("ASSEMBLY_PRODUCTION_BINDING")
            chapter.bind_production(str(data["production_ref"]))
            chapter.bind_context(context)
            if chapter.data["contract_id"] == REAL_CHAPTER:
                thread = thread_from_context(context.data)
                if thread is None:
                    raise ValueError("COURSE_REAL_CONTEXT_BINDING")
                validate_real_course(thread, chapter.data, data["references"])
            if as_plain(data["sections"]) != chapter.sections() or data["title"] != chapter.data["title"]:
                raise ValueError("COURSE_STUDENT_PROJECTION_BINDING")
        lineage = object_data(data["lineage"], _LINEAGE_FIELDS)
        identifier(lineage["source_run_id"], "run")
        identifier(lineage["source_step_id"], "step")
        identifier(lineage["evidence_set_ref"], "evidence")
        identifier(lineage["source_request_id"], "req")
        identifier(lineage["conversation_id"], "conv")
        if lineage["context_sha256"] != context.sha256:
            raise ValueError("P0_LINEAGE_CONTEXT")
        parent = lineage["parent_version_ref"]
        if parent is not None:
            identifier(parent, "ver")
            if parent == data["version_ref"]:
                raise ValueError("P0_LINEAGE_PARENT")
        limitations = data["limitations"]
        if not isinstance(limitations, (tuple, list)) or not 1 <= len(limitations) <= 16:
            raise ValueError("P0_LIMITATIONS")
        tuple(nonempty(limit, 500) for limit in limitations)
        if len(encoded(data)) > 256 * 1024:
            raise ValueError("P0_PRODUCTION_SIZE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @staticmethod
    def _validate_content(
        context: P0Context,
        questions: tuple[dict[str, object], ...],
        corrections: tuple[dict[str, object], ...],
        marking: tuple[dict[str, object], ...],
    ) -> None:
        question_ids = tuple(str(item["question_id"]) for item in questions)
        correction_ids = tuple(str(item["question_id"]) for item in corrections)
        marking_ids = tuple(str(item["question_id"]) for item in marking)
        if context.resource_type == "COURSE":
            if questions or corrections or marking:
                raise ValueError("P0_COURSE_SHAPE")
            return
        if not questions or correction_ids != question_ids:
            raise ValueError("P0_QUESTION_CORRECTION_LINKS")
        mode = context.question_mode
        for question, correction in zip(questions, corrections, strict=True):
            options = tuple(cast(list[str] | tuple[str, ...], question["options"]))
            if mode in {"QCM", "QUIZ"}:
                if not 2 <= len(options) <= 6 or correction["expected_answer"] not in options:
                    raise ValueError("P0_CHOICE_SHAPE")
            elif options:
                raise ValueError("P0_OPEN_QUESTION_OPTIONS")
        if context.resource_type == "ASSESSMENT":
            if marking_ids != question_ids:
                raise ValueError("P0_MARKING_LINKS")
            expected = Decimal(str(context.data["total_points"]))
            if sum((_points(entry["points"]) for entry in marking), Decimal("0")) != expected:
                raise ValueError("P0_MARKING_TOTAL")
        elif marking:
            raise ValueError("P0_MARKING_ASSESSMENT_ONLY")

    @property
    def production_ref(self) -> str:
        return str(self.data["production_ref"])

    @property
    def version_ref(self) -> str:
        return str(self.data["version_ref"])

    @property
    def context(self) -> P0Context:
        return P0Context(object_data(self.data["context"]))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def mutable_copy(self) -> dict[str, object]:
        return object_data(as_plain(self.data))

    def student_projection(self) -> dict[str, object]:
        result = {
            "contract_id": "R6-P0-STUDENT-PROJECTION-1.0",
            "production_ref": self.production_ref,
            "version_ref": self.version_ref,
            "title": self.data["title"],
            "context": as_plain(self.data["context"]),
            "sections": as_plain(self.data["sections"]),
            "questions": as_plain(self.data["questions"]),
            "references": as_plain(self.data["references"]),
        }
        if "course_chapter" in self.data:
            from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
                CourseChapter,
            )

            result["course_chapter"] = CourseChapter(object_data(self.data["course_chapter"])).projection()
        if "media_plan" in self.data:
            result["media_assets"] = ProductionMediaPlan(object_data(self.data["media_plan"])).projection("student")
        if "exercise" in self.data:
            from backend.modules.pedagogical_design.contracts.dto.exercise_profile import (
                StructuredExercise,
            )

            result["exercise"] = StructuredExercise(object_data(self.data["exercise"]), case_study=self.data["contract_id"] == CASE_PRODUCTION).projection()
        return result

    def teacher_projection(self) -> dict[str, object]:
        result = {
            **self.student_projection(),
            "contract_id": "R6-P0-TEACHER-PROJECTION-1.0",
            "corrections": as_plain(self.data["corrections"]),
            "marking": as_plain(self.data["marking"]),
            "limitations": as_plain(self.data["limitations"]),
        }
        if "course_chapter" in self.data:
            from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
                CourseChapter,
            )

            result["course_chapter"] = CourseChapter(object_data(self.data["course_chapter"])).projection(teacher=True)
        if "media_plan" in self.data:
            result["media_assets"] = ProductionMediaPlan(object_data(self.data["media_plan"])).projection("correction")
        if "exercise" in self.data:
            from backend.modules.pedagogical_design.contracts.dto.exercise_profile import (
                StructuredExercise,
            )

            result["exercise"] = StructuredExercise(object_data(self.data["exercise"]), case_study=self.data["contract_id"] == CASE_PRODUCTION).projection(teacher=True)
        return result

    def media_review_context(self) -> list[dict[str, object]]:
        """Bounded textual commitments; hashes never attest pixel inspection."""
        if "course_chapter" in self.data:
            from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
                CourseChapter,
            )

            return CourseChapter(object_data(self.data["course_chapter"])).media_review_context()
        if "media_plan" not in self.data:
            return []
        from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief

        result = []
        plan = ProductionMediaPlan(object_data(self.data["media_plan"]))
        plan.bind(self.data)
        for entry in items(plan.data["entries"], 8):
            asset = entry["asset"]
            brief = VisualBrief(object_data(entry["brief"]))
            commitment = brief.review_context(str(object_data(asset)["png_sha256"]) if asset is not None else "UNAVAILABLE")
            commitment.update(version_ref=self.version_ref, dependencies=as_plain(entry["dependencies"]),
                              required=entry["required"], omission_reason=entry["omission_reason"],
                              availability="PRESENT" if asset is not None else "MISSING")
            result.append(commitment)
        return result
