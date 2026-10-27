"""Pure local assembly; no supplier, validation, authority or storage effects."""

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.modules.pedagogical_design.contracts.dto.chapter_assembly import (
    ASSEMBLY_CHAPTER_CONTRACT,
    ASSEMBLY_PRODUCTION_CONTRACT,
)
from backend.modules.pedagogical_design.contracts.dto.course_chapter import CourseChapter
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


class AssembleChapter:
    def execute(self, blueprint: object) -> P0Production:
        b = object_data(
            blueprint, {"schema", "identity", "context", "chapter", "references", "limitations"}
        )
        if b["schema"] != "LOCAL-CHAPTER-BLUEPRINT-1.0":
            raise ValueError("ASSEMBLY_BLUEPRINT_SCHEMA")
        identity = object_data(b["identity"], {"production_ref", "version_ref", "lineage"})
        context = P0Context(object_data(b["context"]))
        chapter = CourseChapter(object_data(b["chapter"]))
        if chapter.data["contract_id"] != ASSEMBLY_CHAPTER_CONTRACT:
            raise ValueError("ASSEMBLY_EXPLICIT_VARIANT_REQUIRED")
        chapter.bind_context(context)
        chapter.bind_production(str(identity["production_ref"]))
        return P0Production(
            {
                "contract_id": ASSEMBLY_PRODUCTION_CONTRACT,
                "production_ref": identity["production_ref"],
                "version_ref": identity["version_ref"],
                "title": chapter.data["title"],
                "context": context.as_dict(),
                "context_sha256": context.sha256,
                "sections": chapter.sections(),
                "questions": [],
                "corrections": [],
                "marking": [],
                "references": b["references"],
                "lineage": identity["lineage"],
                "limitations": b["limitations"],
                "course_chapter": as_plain(chapter.data),
            }
        )
