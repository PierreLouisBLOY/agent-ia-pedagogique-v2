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
                evidence: Mapping[str, str]) -> SavedProduction:
        original = parent.p0_bundle
        if (original is None or original.context.resource_type != "COURSE" or context.resource_type != "COURSE" or
                context.institutional is None or context.data["institutional_resolution"] is None or
                parent.data["origin"] != "LOCAL_APPLICATION"):
            raise ValueError("P0_LOCAL_COURSE_REFRAME_REQUIRED")
        data = original.mutable_copy()
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
                "LOCAL_EDIT_OPERATION_SHA256": fingerprint({"mode": "EXPLICIT_LOCAL_CONTEXT_SUCCESSOR", "parent": parent.sha256,
                    "context": context.sha256, "title": title, "sections": sections})},
            "reservations": ["Recette enseignante en attente ; aucune review héritée."]})
