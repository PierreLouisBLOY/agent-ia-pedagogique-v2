"""Positive HARDEN projection. The full parent stays on the Application side."""

from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    HARDEN,
    AssessmentRevisionRequest,
)


def harden_projection(request: AssessmentRevisionRequest) -> dict[str, object]:
    if request.operation != HARDEN or request.base is None:
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")
    base = request.base
    ConfirmedConversationContext(request.context)
    if (
        fingerprint(request.subject) != base.data["subject_sha256"]
        or fingerprint(request.context) != base.data["context_sha256"]
        or encoded(request.references) != encoded(base.data["references"])
    ):
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")
    questions = items(base.data["questions"], 30)
    answers = items(object_data(base.data["correction"])["answers"])
    protected = {str(q["question_id"]) for q in questions if q["dossier_id"] != "DOSSIER_3"}
    d3 = {str(q["question_id"]) for q in questions if q["dossier_id"] == "DOSSIER_3"}
    dossiers = items(object_data(base.data["marking"])["dossiers"], 3)
    selected = [d for d in dossiers if d["dossier_id"] == "DOSSIER_3"]
    if len(selected) != 1:
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")
    cases = object_data(base.data["case_data"])
    result = {
        "subject": {"sections": as_plain(object_data(request.subject)["sections"])},
        "case_data": {
            k: as_plain(cases[k])
            for k in ("base_case", "currency", "source_scale", "source_unit_locator")
        },
        "questions_d3": [q for q in questions if q["question_id"] in d3],
        "answers_d3": [a for a in answers if a["question_id"] in d3],
        "marking_d3": selected[0],
        "protected_facts": {
            "questions": [
                {k: q[k] for k in ("question_id", "calculation_refs")}
                for q in questions
                if q["question_id"] in protected
            ],
            "calculations": [
                {k: c[k] for k in ("case_id", "metric", "value", "expression")}
                for a in answers
                if a["question_id"] in protected
                for c in items(a["calculations"])
            ],
            "reserved_question_ids": sorted(protected),
            "reserved_case_ids": [str(object_data(cases["base_case"])["case_id"])],
        },
        "limits": {
            "total_duration_minutes": 60,
            "total_points": "20.00",
            "d3_duration_minutes": 20,
            "d3_points": "8.00",
            "min_d3_questions": max(2, len(d3) + 1),
            "min_scenarios": 1,
        },
    }
    if len(encoded(result)) > 128 * 1024:
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")
    return object_data(as_plain(result))
