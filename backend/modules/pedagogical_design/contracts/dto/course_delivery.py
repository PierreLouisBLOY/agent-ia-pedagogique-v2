"""Delivery invariants for explicit normal rich COURSE; legacy chapters unchanged."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

from backend.modules.pedagogical_context.contracts.dto.p0_context import (
    P0_COURSE_CONTEXT_CONTRACT,
    P0_NOTION_COURSE_CONTEXT_CONTRACT,
    P0Context,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
    COURSE_LINEAGE_CONTRACT,
    COURSE_NOTION_LINEAGE_CONTRACT,
    CourseChapter,
)
from backend.modules.pedagogical_design.contracts.dto.program_authority import (
    require_supported_claims,
)


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def validate_course_delivery(context: P0Context, chapter_data: object, references: object) -> None:
    """Check requested format and observable copies, not semantic acceptance.

    A substantive exact teacher block has at least eight words or 80 characters.
    Short numerical/factual answers and an expected answer equal to an explicitly
    taught concept definition/explanation are allowed. These bounded exceptions
    do not certify absence of indirect answers; pedagogical review remains.
    """
    if context.data["contract_id"] not in {P0_COURSE_CONTEXT_CONTRACT, P0_NOTION_COURSE_CONTEXT_CONTRACT}:
        return
    if context.course_format == "EXPLAINED":
        if chapter_data is not None:
            raise ValueError("P0_UNREQUESTED_RICH_COURSE")
        return
    context.require_institutional_dispatch()
    if not isinstance(chapter_data, Mapping):
        raise ValueError("P0_RICH_COURSE_REQUIRED")
    chapter = CourseChapter(object_data(chapter_data))
    expected = (COURSE_NOTION_LINEAGE_CONTRACT if context.data["contract_id"] == P0_NOTION_COURSE_CONTEXT_CONTRACT
                else COURSE_LINEAGE_CONTRACT)
    if chapter.data["contract_id"] != expected:
        raise ValueError("P0_RICH_COURSE_CONTRACT")
    chapter.bind_context(context)
    evidence_ids = {str(row["evidence_id"]) for row in items(references, 8)}
    for doc in items(chapter.data["documents"]):
        provenance = object_data(doc["provenance"])
        if (
            provenance["kind"] == "SUPPLIED_REFERENCE"
            and provenance["source_ref"] not in evidence_ids
        ) or (
            provenance["kind"] == "LOCAL_FICTION"
            and provenance["source_ref"] != "LOCAL_APPLICATION_CONSTRUCTION"
        ):
            raise ValueError("P0_RICH_COURSE_DOCUMENT_REFERENCE")
    used = {
        str(ref)
        for part in items(chapter.data["parts"])
        for ref in cast(tuple[str, ...], part["document_ids"])
    }
    if not any(
        doc["function"] == "METHOD" and doc["id"] in used
        for doc in items(chapter.data["documents"])
    ):
        raise ValueError("P0_RICH_COURSE_METHOD_REQUIRED")
    require_supported_claims(
        chapter.visible_text(teacher=True), context.data["institutional_resolution"]
    )
    student = _normalized(chapter.visible_text())
    definitions = {
        _normalized(str(concept[field]))
        for concept in items(chapter.data["concepts"])
        for field in ("definition", "explanation")
    }
    for answer in items(chapter.data["teacher_answers"]):
        for field in ("expected_answer", "rationale", "vigilance", "remediation"):
            text = _normalized(str(answer[field]))
            substantive = len(text) >= 80 or len(re.findall(r"\S+", text)) >= 8
            taught = field == "expected_answer" and text in definitions
            if substantive and not taught and text in student:
                raise ValueError("P0_RICH_COURSE_TEACHER_BLOCK_IN_STUDENT")
