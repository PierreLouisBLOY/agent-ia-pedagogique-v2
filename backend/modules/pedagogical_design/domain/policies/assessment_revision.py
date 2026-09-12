"""Assemble only the authorized delta; never let generated data overwrite V1."""
from collections.abc import Callable, Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    BUNDLE_CONTRACT,
    AssessmentBundle,
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    HARDEN,
    AssessmentRevisionRequest,
    EditorialCorrectionPlan,
)


def assemble_revision(request: AssessmentRevisionRequest, proposed: Mapping[str, object],
                      *, version_ref: str, lineage: Mapping[str, object],
                      observe: Callable[[str], None] | None = None) -> AssessmentBundle:
    def mark(stage: str) -> None:
        # Diagnostic-only scalar notification; a sink cannot change a domain decision.
        if observe is not None:
            try:
                observe(stage)
            except Exception:
                pass

    mark("BUNDLE_ASSEMBLY")
    if request.operation == HARDEN:
        delta = object_data(proposed, {"dossier_3", "questions_d3", "answers_d3",
                                      "marking_d3", "scenarios_d3", "limitations"})
        if request.base is None:
            raise ValueError("ASSESSMENT_BUNDLE_MISSING")
        data = request.base.mutable_copy()
        subject = object_data(data["subject"])
        sections = list(items(subject["sections"], 5))
        section = object_data(delta["dossier_3"], {"section_id", "text"})
        if section["section_id"] != "DOSSIER_3" or section == sections[-1]:
            raise ValueError("TARGETED_DELTA_REQUIRED")
        questions = items(delta["questions_d3"], 30)
        old_d3 = [q for q in items(data["questions"]) if q["dossier_id"] == "DOSSIER_3"]
        if (len(questions) <= len(old_d3)
                or any(q.get("dossier_id") != "DOSSIER_3" for q in questions)
                or not items(delta["scenarios_d3"], 10)):
            raise ValueError("COMPLEXIFICATION_REQUIRED")
        sections[-1] = section
        subject["sections"] = sections
        subject["content"] = "\n\n".join(str(s["text"]) for s in sections)
        data["subject"] = subject
        data["questions"] = [q for q in items(data["questions"]) if q["dossier_id"] != "DOSSIER_3"] + list(questions)
        old_ids = {q["question_id"] for q in old_d3}
        correction = object_data(data["correction"])
        correction["answers"] = [a for a in items(correction["answers"]) if a["question_id"] not in old_ids] + list(items(delta["answers_d3"]))
        data["correction"] = correction
        marking = object_data(data["marking"])
        dossiers = list(items(marking["dossiers"], 3))
        revised = object_data(delta["marking_d3"])
        if (revised.get("dossier_id") != "DOSSIER_3"
                or revised.get("duration_minutes") != dossiers[-1].get("duration_minutes")):
            raise ValueError("DEPENDENCY_CHANGE_REQUIRES_APPROVAL")
        old_points = tuple(q["points"] for q in items(dossiers[-1]["questions"]))
        from decimal import Decimal
        if sum(Decimal(str(q["points"])) for q in items(revised["questions"])) != sum(Decimal(str(p)) for p in old_points):
            raise ValueError("DEPENDENCY_CHANGE_REQUIRES_APPROVAL")
        dossiers[-1] = revised
        marking["dossiers"] = dossiers
        data["marking"] = marking
        case_data = object_data(data["case_data"])
        case_data["scenarios"] = list(items(delta["scenarios_d3"], 10))
        data["case_data"] = case_data
        data["limitations"] = as_plain(delta["limitations"])
    else:
        mark("PARSED_OUTPUT_MAPPING")
        delta = object_data(proposed, {"questions", "correction", "marking", "case_data", "limitations"})
        for field in ("correction", "marking"):
            mark("SUPPLEMENTS_DOMAIN_CONSTRUCTION")
            supplied = object_data(delta[field])
            mark("VERSION_BINDING")
            if (supplied.get("production_ref"), supplied.get("version_ref")) != (
                    request.production_ref, request.base_version_ref):
                raise ValueError("ASSESSMENT_REFERENCE")
        mark("BUNDLE_ASSEMBLY")
        data = dict(delta)
        data.update(contract_id=BUNDLE_CONTRACT, production_ref=request.production_ref,
                    subject=as_plain(request.subject), pedagogical_context=as_plain(request.context),
                    context_sha256=fingerprint(request.context), references=as_plain(request.references))
    mark("BUNDLE_ASSEMBLY")
    data["version_ref"] = version_ref
    data["subject_sha256"] = fingerprint(data["subject"])
    for field in ("correction", "marking"):
        part = object_data(data[field])
        part.update(production_ref=request.production_ref, version_ref=version_ref)
        data[field] = part
    data["lineage"] = dict(lineage)
    mark("BUNDLE_ASSEMBLY")
    return AssessmentBundle(data)


def assemble_editorial_corrections(
    plan: EditorialCorrectionPlan, parent: AssessmentBundle, *, version_ref: str,
    lineage: Mapping[str, object],
    calculate_locators: Callable[[str, str, tuple[str, ...]], tuple[dict[str, object], ...]],
) -> AssessmentBundle:
    """Local approved text only. No provider, store, approval or parent mutation."""
    plan.validate_parent(parent)
    if version_ref == parent.version_ref:
        raise ValueError("ASSESSMENT_REFERENCE")
    data = parent.mutable_copy()
    correction = object_data(data["correction"])
    answers = items(correction["answers"])
    for i, edit in enumerate(items(plan.data["edits"], 2)):
        answer = answers[i]
        calculations = items(answer["calculations"])
        text = str(edit["proposed_expected_answer"])
        locators = calculate_locators(str(answer["question_id"]), text,
                                      tuple(str(c["value"]) for c in calculations))
        if len(locators) != 1:
            raise ValueError("ASSESSMENT_LOCATOR")
        locator = object_data(locators[0], {"section_id", "start", "end", "exact_text"})
        if (locator["section_id"] != answer["question_id"]
                or locator["exact_text"] != calculations[0]["value"]):
            raise ValueError("ASSESSMENT_LOCATOR")
        answer["expected_answer"] = text
        calculations[0]["locator"] = locator
        answer["calculations"] = list(calculations)
    correction["answers"] = list(answers)
    data["correction"] = correction
    data["version_ref"] = version_ref
    for name in ("correction", "marking"):
        part = object_data(data[name])
        part["version_ref"] = version_ref
        data[name] = part
    data["lineage"] = dict(lineage)
    return AssessmentBundle(data)
