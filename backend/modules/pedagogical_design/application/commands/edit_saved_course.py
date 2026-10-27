"""Closed local edits preserve the structured COURSE contract and dependencies."""
from collections.abc import Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.course_chapter import CourseChapter


def apply_course_edits(parent: Mapping[str, object], edits: Mapping[str, object], *,
                       allow_assembly_question_edits: bool = False) -> dict[str, object]:
    if "course_chapter" not in parent:
        raise ValueError("P0_COURSE_EDITS_REQUIRED")
    if set(edits) - {"title", "course_edits"}:
        raise ValueError("P0_COURSE_PROJECTION_READ_ONLY")
    data = object_data(parent)
    chapter = object_data(as_plain(data["course_chapter"]))
    patch = object_data(edits.get("course_edits", {}))
    allowed = {"context", "documents", "questions", "concepts", "parts", "synthesis", "teacher_answers"}
    if set(patch) - allowed:
        raise ValueError("P0_COURSE_EDITS_REJECTED")
    if "context" in patch:
        context = object_data(patch["context"])
        if set(context) - {"title", "text"}:
            raise ValueError("P0_COURSE_EDITS_REJECTED")
        chapter["context"] = {**object_data(chapter["context"]), **context}
    for field, keys in (
        ("documents", {"title", "text"}),
        ("questions", {"prompt"}),
        ("concepts", {"definition", "explanation", "example"}),
        ("parts", {"title"}),
        ("teacher_answers", {"expected_answer", "rationale", "vigilance", "remediation"}),
    ):
        if field not in patch:
            continue
        rows = items(chapter[field], 60)
        by_id = {str(row["id"]): row for row in rows}
        seen = set()
        for change in items(patch[field], 60):
            if set(change) - (keys | {"id"}) or "id" not in change:
                raise ValueError("P0_COURSE_EDITS_REJECTED")
            key = str(change["id"])
            if key not in by_id or key in seen:
                raise ValueError("P0_COURSE_EDIT_ID")
            seen.add(key)
            original = by_id[key]
            changed = any(original[k] != v for k, v in change.items() if k != "id")
            if field == "documents" and changed and object_data(original["provenance"])["kind"] == "SUPPLIED_REFERENCE":
                raise ValueError("P0_COURSE_SUPPLIED_REFERENCE_EDIT_REQUIRES_ADMISSION")
            original.update(change)
        chapter[field] = list(rows)
    if "synthesis" in patch:
        chapter["synthesis"] = patch["synthesis"]
    before = object_data(as_plain(data["course_chapter"]))
    if "media_assets" in before and {k: v for k, v in chapter.items() if k != "title"} != {
        k: v for k, v in before.items() if k != "title"
    }:
        independent_question_patch = (
            allow_assembly_question_edits
            and chapter["contract_id"] == "COURSE-CHAPTER-ASSEMBLY-5.0"
            and set(edits) == {"course_edits"}
            and set(patch) == {"questions", "teacher_answers"}
            and all(chapter[k] == before[k] for k in before
                    if k not in {"questions", "teacher_answers"})
        )
        if not independent_question_patch:
            raise ValueError("P0_COURSE_MEDIA_DEPENDENCY_CHANGED")
    if "title" in edits:
        chapter["title"] = edits["title"]
    validated = CourseChapter(chapter)
    data.update(title=validated.data["title"], course_chapter=chapter, sections=validated.sections())
    return data
