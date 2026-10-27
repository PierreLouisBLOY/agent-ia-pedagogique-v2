"""Application-owned binding of explicit exercise content; no generation authority."""
from collections.abc import Mapping

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.modules.pedagogical_design.contracts.dto.case_study import (
    CASE_CONTEXT,
    CASE_PRODUCTION,
)
from backend.modules.pedagogical_design.contracts.dto.exercise_profile import (
    EXERCISE_FIELDS,
    EXERCISE_PRODUCTION,
    StructuredExercise,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production

_BINDINGS = ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage")


def bind_exercise_content(request: Mapping[str, object], content: Mapping[str, object]) -> P0Production:
    context = P0Context(object_data(request["context"]))
    if context.sha256 != request["context_sha256"]:
        raise ValueError("P0_CONTEXT_HASH")
    proposed = object_data(as_plain(content), EXERCISE_FIELDS)
    exercise = StructuredExercise(object_data(proposed["exercise"]), case_study=context.data["contract_id"] == CASE_CONTEXT)
    exercise.bind(context.data, request["references"])
    limits = proposed["limitations"]
    if not isinstance(limits, (list, tuple)):
        raise ValueError("P0_LIMITATIONS")
    marker = "CANDIDATE — ressource non validée, à relire par l'enseignant avant usage."
    limitations = list(limits) if marker in limits else [*limits, marker]
    return P0Production({"contract_id": CASE_PRODUCTION if context.data["contract_id"] == CASE_CONTEXT else EXERCISE_PRODUCTION, **{key: request[key] for key in _BINDINGS},
                         "title": proposed["title"], "exercise": as_plain(exercise.data),
                         "sections": exercise.sections(), "questions": exercise.simple_questions(),
                         "corrections": exercise.simple_answers(), "marking": [], "limitations": limitations})
