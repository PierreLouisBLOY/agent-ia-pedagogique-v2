"""Typed case, exact quotes, links, canonical schema and both existing writers."""

from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter
from backend.adapters.outbound.generation.openai.p0_content import bind_p0_content
from backend.adapters.outbound.generation.openai.p0_exercise_schema import exercise_content_schema
from backend.modules.materialization_export.application.services.exercise_projection import (
    project_exercise,
)
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.case_study import (
    CASE_CONTEXT,
    CASE_PRODUCTION,
    CaseStudyDossier,
)
from tests.focus_323d_fixture import focus_dispatch


def case_blueprint():
    dispatch, content = focus_dispatch()
    dispatch["context"]["contract_id"] = CASE_CONTEXT
    context = P0Context(dispatch["context"])
    dispatch["context_sha256"] = dispatch["lineage"]["context_sha256"] = context.sha256
    exercise = content["exercise"]
    exercise["case_study"] = {
        "contract_id": "CASE-STUDY-DOSSIER-1.0",
        "organizations": [{"organization_id": "O1", "label": "Atelier Delta"}],
        "data": [
            {
                "data_id": "A1",
                "organization_id": "O1",
                "kind": "FICTION",
                "text": "L'organisation prépare une commande.",
                "document_id": "D1",
                "quote": None,
            }
        ],
        "missions": [
            {
                "mission_id": "M1",
                "title": "Analyser puis clarifier l'échange",
                "document_ids": [row["document_id"] for row in exercise["documents"]],
                "question_ids": [row["question_id"] for row in exercise["questions"]],
                "data_ids": ["A1"],
            }
        ],
    }
    return dispatch, content


def test_case_is_a_new_explicit_contract_through_existing_exercise_projections():
    dispatch, content = case_blueprint()
    bundle = bind_p0_content(dispatch, content)
    assert bundle.data["contract_id"] == CASE_PRODUCTION
    assert bundle.context.resource_type == "EXERCISE"
    assert "case_study" in bundle.teacher_projection()["exercise"]
    assert "teacher_answers" not in bundle.student_projection()["exercise"]
    assert "Donnée fictive" in bundle.data["sections"][2]["text"]
    for kind in ("student", "correction"):
        document = project_exercise(bundle, kind)
        with ZipFile(BytesIO(CourseOOXMLWordWriter().write(document))) as archive:
            xml = archive.read("word/document.xml").decode()
        assert "Mission :" in xml and "Donnée fictive" in xml
        assert ("Réponse attendue" in xml) == (kind == "correction")


@pytest.mark.parametrize(
    "change",
    (
        "missing",
        "orphan_question",
        "unused_data",
        "unsupported_fact",
        "invented_source",
        "extra_field",
    ),
)
def test_invalid_cases_are_refused_without_relaxing_exercise(change):
    dispatch, content = case_blueprint()
    case = content["exercise"]["case_study"]
    if change == "missing":
        del content["exercise"]["case_study"]
    elif change == "orphan_question":
        case["missions"][0]["question_ids"].pop()
    elif change == "unused_data":
        case["missions"][0]["data_ids"] = ["inexistent"]
    elif change == "unsupported_fact":
        case["data"][0].update(kind="DOCUMENTED_FACT", quote="Absent du document")
    elif change == "invented_source":
        case["data"][0]["quote"] = "Fausse citation réelle"
    else:
        case["data"][0]["hidden"] = "metadata"
    with pytest.raises(ValueError):
        bind_p0_content(dispatch, content)


def test_fact_quote_is_lexical_not_global_truth_and_inference_stays_distinct():
    dispatch, content = case_blueprint()
    exercise = content["exercise"]
    dossier = deepcopy(exercise["case_study"])
    exercise["documents"][0].update(
        text="Atelier Delta annonce un objectif de dix commandes.", provenance="SUPPLIED_REFERENCE"
    )
    dossier["data"][0].update(
        kind="DOCUMENTED_FACT",
        text=exercise["documents"][0]["text"],
        quote=exercise["documents"][0]["text"],
    )
    CaseStudyDossier(dossier).bind(exercise)
    dossier["data"][0]["text"] = "Atelier Delta a réalisé dix commandes."
    with pytest.raises(ValueError, match="P0_CASE_FACT_REQUIRES_EXACT_QUOTE"):
        CaseStudyDossier(dossier).bind(exercise)
    dossier["data"][0]["kind"] = "INFERENCE"
    assert "Interprétation à discuter" in CaseStudyDossier(dossier).public_text()


def test_schema_and_local_parser_select_same_closed_case_profile():
    schema = exercise_content_schema(case_study=True)
    base = exercise_content_schema()
    assert "case_study" in schema["properties"]["exercise"]["properties"]
    assert "case_study" not in base["properties"]["exercise"]["properties"]
    dispatch, content = case_blueprint()
    dispatch["context"]["contract_id"] = "P0-CONTEXT-EXERCISE-1.1"
    context = P0Context(dispatch["context"])
    dispatch["context_sha256"] = dispatch["lineage"]["context_sha256"] = context.sha256
    with pytest.raises(ValueError):
        bind_p0_content(dispatch, content)
