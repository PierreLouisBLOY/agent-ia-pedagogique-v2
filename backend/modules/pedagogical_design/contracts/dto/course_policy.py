"""An explained lesson is distinct from a revision sheet or an assessment."""
COURSE_SECTIONS = ("OBJECTIVES", "EXPLAINED_NOTIONS", "METHOD", "GUIDED_APPLICATION", "SYNTHESIS")
COURSE_POLICY: dict[str, object] = {
    "contract_id": "COURSE-EXPLAINED-1.0",
    "sections": list(COURSE_SECTIONS),
    "depth": "CONFIRMED_CONTEXT", "page_limit": None,
    "examples": "INVENTED_DATA_MARKED_FICTIVES", "teacher_acceptance": "REQUIRED",
}


def validate_course_structure(sections: object) -> None:
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items

    present = {str(row["section_id"]) for row in items(sections, 16)}
    if not {"S_" + role for role in COURSE_SECTIONS} <= present:
        raise ValueError("P0_COURSE_EXPLANATION_REQUIRED")
