"""Prepare a local original through the same typed production and validation commands."""
from collections.abc import Mapping

from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
)
from backend.modules.pedagogical_design.application.mappers.exercise_provider_content import (
    bind_exercise_content,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class PrepareStructuredExercise:
    def execute(self, dispatch: Mapping[str, object], content: Mapping[str, object]) -> SavedProduction:
        bound = bind_exercise_content(dispatch, content)
        raw_evidence = object_data(dispatch["evidence"])
        if any(not isinstance(text, str) for text in raw_evidence.values()):
            raise ValueError("P0_EVIDENCE_INSUFFICIENT")
        evidence = {key: str(value) for key, value in raw_evidence.items()}
        bundle = CreateP0Candidate().execute(bound.data, evidence=evidence)
        ValidateP0Command().execute(bundle)
        return SavedProduction({"contract_id": "SAVED-PRODUCTION-P0-1.0",
                                "view": object_data(P0ProductionReadView.from_bundle(bundle).data),
                                "bundle": bundle.mutable_copy(), "reviews": [], "validations": [],
                                "origin": "LOCAL_APPLICATION", "provenance": {"LOCAL_EXERCISE_CONTENT": fingerprint(content)},
                                "reservations": ["LOCAL_ORIGINAL_NO_PROVIDER_CALL", "TEACHER_ACCEPTANCE_NOT_PERFORMED"]})
