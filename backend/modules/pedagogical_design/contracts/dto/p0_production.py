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
    if not isinstance(value, str) or re.fullmatch(r"Q[A-Z0-9_-]{1,63}", value) is None:
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
        if not isinstance(section_id, str) or re.fullmatch(r"S[A-Z0-9_-]{1,63}", section_id) is None:
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


def _validated_references(value: object) -> tuple[dict[str, object], ...]:
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
        if reference["provenance_label"] != P0_PROVENANCE_LABEL:
            raise ValueError("P0_REFERENCE_PROVENANCE")
    if len(ids) != len(set(ids)):
        raise ValueError("P0_REFERENCES")
    return references


@dataclass(frozen=True, slots=True)
class P0Production:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
            COURSE_PRODUCTION_CONTRACT,
            CourseChapter,
        )

        is_chapter = self.data.get("contract_id") == COURSE_PRODUCTION_CONTRACT
        data = object_data(self.data, _FIELDS | {"course_chapter"} if is_chapter else _FIELDS)
        if data["contract_id"] not in {P0_PRODUCTION_CONTRACT, COURSE_PRODUCTION_CONTRACT}:
            raise ValueError("P0_PRODUCTION_CONTRACT")
        identifier(data["production_ref"], "prod")
        identifier(data["version_ref"], "ver")
        nonempty(data["title"], 300)
        context = P0Context(object_data(data["context"]))
        if data["context_sha256"] != context.sha256:
            raise ValueError("P0_CONTEXT_HASH")
        _validated_sections(data["sections"])
        questions = _validated_questions(data["questions"])
        corrections = _validated_corrections(data["corrections"])
        marking = _validated_marking(data["marking"])
        _validated_references(data["references"])
        self._validate_content(context, questions, corrections, marking)
        if is_chapter:
            chapter = CourseChapter(object_data(data["course_chapter"]))
            chapter.bind_production(str(data["production_ref"]))
            chapter.bind_context(context)
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
        return result
