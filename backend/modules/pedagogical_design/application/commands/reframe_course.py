"""Explicit local context correction creates a child; it never consumes a grant."""
from collections.abc import Mapping
from secrets import token_hex

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    ReviseP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_P0_CONTRACT,
    SavedProduction,
)


class ReframeCourseCommand:
    def execute(self, parent: SavedProduction, context: P0Context, *, title: str, sections: object,
                evidence: Mapping[str, str], course_chapter: Mapping[str, object] | None = None,
                reference_override: Mapping[str, object] | None = None) -> SavedProduction:
        original = parent.p0_bundle
        if (original is None or original.context.resource_type != "COURSE" or context.resource_type != "COURSE" or
                context.institutional is None or context.data["institutional_resolution"] is None or
                parent.data["origin"] != "LOCAL_APPLICATION"):
            raise ValueError("P0_LOCAL_COURSE_REFRAME_REQUIRED")
        data = original.mutable_copy()
        if reference_override is not None:
            data["references"] = [dict(reference_override)]
        if course_chapter is not None:
            from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
                COURSE_NOTION_LINEAGE_CONTRACT,
                COURSE_NOTION_PRODUCTION_CONTRACT,
                COURSE_PRODUCTION_CONTRACT,
                CourseChapter,
            )

            chapter = CourseChapter(course_chapter)
            chapter.bind_context(context)
            production_contract = (COURSE_NOTION_PRODUCTION_CONTRACT if chapter.data["contract_id"] == COURSE_NOTION_LINEAGE_CONTRACT
                                   else COURSE_PRODUCTION_CONTRACT)
            data.update({"contract_id": production_contract, "course_chapter": as_plain(chapter.data)})
            sections = chapter.sections()
        data.update({"version_ref": "ver:" + token_hex(16), "title": title, "sections": sections,
                     "context": context.as_dict(), "context_sha256": context.sha256})
        data["lineage"] = {**object_data(data["lineage"]), "parent_version_ref": original.version_ref,
            "context_sha256": context.sha256, "source_request_id": "req:" + token_hex(16),
            "source_run_id": "run:" + token_hex(16), "source_step_id": "step:" + token_hex(16)}
        data["limitations"] = ["CANDIDATE — création locale, sans nouvelle génération fournisseur.",
            "Rattachement pédagogique proposé ; recette enseignante non effectuée.",
            "Les lacunes institutionnelles restent visibles dans le contexte exact."]
        child = ReviseP0Candidate().execute(original, data, evidence=evidence)
        validation = ValidateP0Command().execute(child, parent=original)
        return SavedProduction({"contract_id": SAVED_P0_CONTRACT, "view": as_plain(P0ProductionReadView.from_bundle(child).data),
            "bundle": child.mutable_copy(), "reviews": [], "validations": [validation], "origin": "LOCAL_APPLICATION",
            "provenance": {"LOCAL_EDIT_PARENT_BUNDLE_SHA256": original.sha256, "LOCAL_EDIT_PARENT_RECORD_SHA256": parent.sha256,
                "INSTITUTIONAL_RESOLUTION_SHA256": fingerprint(context.data["institutional_resolution"]),
                "LOCAL_REFERENCE_SUCCESSOR_SHA256": fingerprint(reference_override),
                "LOCAL_EDIT_OPERATION_SHA256": fingerprint({"mode": "EXPLICIT_LOCAL_CONTEXT_SUCCESSOR", "parent": parent.sha256,
                    "context": context.sha256, "title": title, "sections": sections,
                    "course_chapter": as_plain(course_chapter)})},
            "reservations": ["Recette enseignante en attente ; aucune review héritée."]})
