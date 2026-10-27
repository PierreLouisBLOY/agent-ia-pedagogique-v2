"""Only synthetic question objects; no real catalog or authority is imported."""

from copy import deepcopy

from backend.modules.pedagogical_context.contracts.dto.exercise_context import (
    FOCUSED_EXERCISE_CONTEXT,
    LOCAL_FOCUS_AUTHORITY,
)
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from tests.exercise_quality_fixture import blueprint

LOCAL_LABEL = "Comment un individu devient-il acteur dans une organisation ?"
SOURCE_LABEL = "Comment définir les différents types d'organisation ? " + LOCAL_LABEL


def focus_dispatch():
    d, content = blueprint()
    context = d["context"]
    question = context["institutional_resolution"]["question"]
    question.update(
        official_label=SOURCE_LABEL,
        official_text="SYNTHETIC_SOURCE_TEXT_NOT_AN_ADMISSION",
        element_type="QUESTION",
        framework_version_id=context["institutional"]["program_version"],
        document_reference_id="docref:SYNTHETIC",
        parent_element_id="theme:SYNTHETIC",
        position=1,
    )
    context["contract_id"] = FOCUSED_EXERCISE_CONTEXT
    context["exercise_focus_selection"] = {
        "source_question_ref": question["id"],
        "source_question_sha256": fingerprint(question),
        "local_question_label": LOCAL_LABEL,
        "authority": LOCAL_FOCUS_AUTHORITY,
    }
    context["exercise_focus_justification"] = (
        "Sélection pédagogique locale pour analyser les comportements individuels ; aucune relation officielle plus étroite."
    )
    context["institutional_resolution"]["source_fidelity_test"] = (
        "SYNTHETIC_UNPROJECTED_RESOLUTION_METADATA"
    )
    d["context_sha256"] = P0Context(context).sha256
    d["lineage"]["context_sha256"] = d["context_sha256"]
    return deepcopy(d), deepcopy(content)
