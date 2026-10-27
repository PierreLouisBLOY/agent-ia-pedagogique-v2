"""One unvalidated question/answer edit of the explicit local assembly variant."""
from backend.modules.pedagogical_design.application.commands.assemble_chapter import AssembleChapter
from backend.modules.pedagogical_design.application.commands.edit_saved_course import (
    apply_course_edits,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.pedagogical_design.contracts.dto.chapter_assembly import (
    ASSEMBLY_CHAPTER_CONTRACT,
    ASSEMBLY_PRODUCTION_CONTRACT,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


class ReviseLocalChapter:
    def execute(self, parent: P0Production, *, version_ref: str, question_id: str,
                prompt: str, expected_answer: str, rationale: str) -> P0Production:
        original = parent.mutable_copy()
        chapter = object_data(original.get("course_chapter"))
        if (original["contract_id"] != ASSEMBLY_PRODUCTION_CONTRACT
                or chapter["contract_id"] != ASSEMBLY_CHAPTER_CONTRACT):
            raise ValueError("R4_LOCAL_EDIT_UNAVAILABLE")
        patch = {"course_edits": {
            "questions": [{"id": question_id, "prompt": prompt}],
            "teacher_answers": [{"id": question_id, "expected_answer": expected_answer,
                                 "rationale": rationale}],
        }}
        edited = apply_course_edits(original, patch, allow_assembly_question_edits=True)
        if edited["course_chapter"] == original["course_chapter"]:
            raise ValueError("R4_LOCAL_EDIT_NO_CHANGE")
        lineage = {**object_data(original["lineage"]), "parent_version_ref": parent.version_ref}
        raw_limitations = original["limitations"]
        if not isinstance(raw_limitations, (list, tuple)):
            raise ValueError("R4_LOCAL_EDIT_REJECTED")
        limitations = list(raw_limitations)
        warning = "CANDIDATE — édition locale non validée ; l'acceptation du parent n'est pas héritée."
        if warning not in limitations:
            limitations.append(warning)
        # Same local assembly command/contract, not provider creation or admission.
        return AssembleChapter().execute({
            "schema": "LOCAL-CHAPTER-BLUEPRINT-1.0",
            "identity": {"production_ref": parent.production_ref,
                         "version_ref": version_ref, "lineage": lineage},
            "context": original["context"], "chapter": edited["course_chapter"],
            "references": original["references"], "limitations": limitations,
        })
