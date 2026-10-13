"""An explained lesson is distinct from a revision sheet or an assessment."""
COURSE_SECTIONS = ("OBJECTIVES", "EXPLAINED_NOTIONS", "METHOD", "GUIDED_APPLICATION", "SYNTHESIS")
COURSE_POLICY: dict[str, object] = {
    "contract_id": "COURSE-EXPLAINED-1.0",
    "sections": list(COURSE_SECTIONS),
    "depth": "CONFIRMED_CONTEXT", "page_limit": None,
    "examples": "INVENTED_DATA_MARKED_FICTIVES", "teacher_acceptance": "REQUIRED",
}

# The successor is selected explicitly; existing bundles and dispatches retain 1.0.
COURSE_BENCHMARK_POLICY: dict[str, object] = {
    "contract_id": "COURSE-CHAPTER-1.0",
    "flow": ["DOCUMENT", "OBSERVATION", "ANALYSIS", "CONCEPTUALIZATION", "REINVESTMENT", "KNOWLEDGE_CHECK", "TRANSFER"],
    "student_and_teacher": "SEPARATE_PROJECTIONS",
    "template_activation": "EXPLICIT_CHAPTER_ONLY_PENDING_M01_OWNER_ACCEPTANCE",
    "structural_validation_is_pedagogical_acceptance": False,
}


def validate_course_structure(sections: object) -> None:
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items

    present = {str(row["section_id"]) for row in items(sections, 16)}
    if not {"S_" + role for role in COURSE_SECTIONS} <= present:
        raise ValueError("P0_COURSE_EXPLANATION_REQUIRED")


def course_policy_for(context: object) -> dict[str, object]:
    from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context

    if not isinstance(context, P0Context):
        raise ValueError("P0_COURSE_CONTEXT_REQUIRED")
    if context.course_format != "CHAPTER":
        return COURSE_POLICY
    return {"contract_id": "COURSE-CHAPTER-LINEAGE-3.0",
            "provider_content_contract": "P0-COURSE-RICH-CONTENT-1.0",
            "depth": "CONFIRMED_CONTEXT", "page_limit": None,
            "student_and_teacher": "SEPARATE_PROJECTIONS",
            "content_completion": "PROVIDER_REQUIRED_NO_LOCAL_REPAIR",
            "teacher_acceptance": "REQUIRED"}
