"""Synthetic fixtures exercise the COURSE contract, boundaries and exact-version exports."""

import copy
import hashlib
import json
from io import BytesIO
from secrets import token_hex
from zipfile import ZipFile

import pytest

from backend.adapters.inbound.application.reframe_course import ReframeCourseInbound
from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
    COURSE_PRODUCTION_CONTRACT,
    CourseChapter,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.unit.test_stmg_institutional_alignment import (
    Catalog,
    ExplainedCourseDouble,
    app,
    context,
    prepare,
)


def chapter_data(confirmed):
    selected = confirmed["institutional"]
    return {
        "contract_id": "COURSE-CHAPTER-1.0",
        "chapter_number": 1,
        "title": "Chapitre synthétique",
        "program_header": {
            **{
                k: selected[k]
                for k in ("frame", "program_ref", "program_version", "theme_ref", "question_ref")
            },
            "theme_label": "Thème de test",
            "question_label": confirmed["institutional_resolution"]["question"]["official_label"],
            "level_label": "Première STMG",
            "subject_label": confirmed["discipline"],
        },
        "capabilities": [
            {
                "id": "C1",
                "label": "Identifier les faits du document",
                "source_ref": "unit:source",
                "locator": "unit:page1",
                "authority_status": "LOCAL_PROPOSED",
            }
        ],
        "notions": confirmed["topics"],
        "context": {
            "title": "Contexte synthétique",
            "text": "Une équipe prépare une activité commune.",
        },
        "documents": [
            {
                "id": "D1",
                "title": "Situation d’apprentissage",
                "function": "Observer les contributions",
                "text": "Deux participants se répartissent les tâches.",
                "table": {
                    "columns": ["Acteur", "Rôle"],
                    "rows": [["A", "Prépare"], ["B", "Vérifie"]],
                },
                "provenance": {"kind": "LOCAL_FICTION", "source_ref": "unit:fiction"},
            }
        ],
        "parts": [
            {
                "id": "I",
                "title": "I Observer et expliquer",
                "document_ids": ["D1"],
                "observation": ["Q1"],
                "analysis": ["Q2"],
                "concept_ids": ["N1"],
                "reinvestment": ["Q3"],
            }
        ],
        "questions": [
            {
                "id": "Q" + str(i),
                "number": i,
                "prompt": f"Identifier le fait {i} dans la situation.",
                "document_ids": ["D1"],
                "capability_ids": ["C1"],
                "response": {"kind": "LINES", "lines": 2, "table": None},
            }
            for i in range(1, 6)
        ],
        "concepts": [
            {
                "id": "N1",
                "notion": confirmed["topics"][0],
                "definition": "Une notion relie les faits.",
                "explanation": "Elle aide à justifier la réponse.",
                "example": "Les tâches sont réparties.",
            }
        ],
        "knowledge_check": ["Q4"],
        "transfer": {
            "title": "Transférer le raisonnement",
            "document_ids": ["D1"],
            "question_ids": ["Q5"],
        },
        "synthesis": "Relier un fait à une notion pour justifier la conclusion.",
        "teacher_answers": [
            {
                "id": "Q" + str(i),
                "expected_answer": f"ORACLE_PROF_{i}",
                "rationale": "Fait explicite du document",
                "vigilance": "Ne pas recopier sans expliquer",
                "remediation": "Relever le fait utile",
            }
            for i in range(1, 6)
        ],
    }


def child_fixture():
    catalog = Catalog()
    service = app(catalog, ExplainedCourseDouble())
    prepared = prepare(service, context())
    view = service.execute(
        "generate",
        {
            "command_id": token_hex(16),
            "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"],
        },
    )["view"]
    parent = service.saved_source(view["production_ref"], view["version_ref"])
    content = chapter_data(parent.p0_bundle.context.as_dict())
    child = ReframeCourseInbound(ReadSTMGAlignment(catalog).resolve).execute(
        parent,
        context(),
        title=content["title"],
        sections=[],
        course_chapter=content,
        reference_selection={"notion_id": "notion:shared"},
        evidence=service.evidence[parent.version_ref],
    )
    return parent, child


def test_chapter_checks_do_not_claim_visual_or_pedagogical_acceptance():
    parent, child = child_fixture()
    assert parent.p0_bundle.data["contract_id"] == "R6-P0-PRODUCTION-1.0"
    assert child.p0_bundle.data["contract_id"] == COURSE_PRODUCTION_CONTRACT
    report = child.data["validations"][0]
    assert report["status"] == "PASS" and all(report["course_checks"].values())
    assert report["visual_review"] == "REQUIRED_NOT_ATTESTED"
    assert report["pedagogical_acceptance"] == "NOT_PERFORMED"
    assert child.data["reviews"] == ()


@pytest.mark.parametrize(
    "field",
    [
        "capabilities",
        "notions",
        "documents",
        "parts",
        "questions",
        "concepts",
        "knowledge_check",
        "teacher_answers",
    ],
)
def test_missing_course_content_cannot_pass(field):
    _, child = child_fixture()
    data = as_plain(child.p0_bundle.data["course_chapter"])
    data[field] = []
    with pytest.raises(ValueError):
        CourseChapter(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "question_number",
        "document_link",
        "capability_link",
        "part_link",
        "concept_link",
        "answer_link",
        "response",
        "table",
        "metadata",
        "unknown_field",
        "claimed_admission",
    ],
)
def test_structure_and_link_mutations_are_rejected(mutation):
    _, child = child_fixture()
    data = as_plain(child.p0_bundle.data["course_chapter"])
    if mutation == "question_number":
        data["questions"][0]["number"] = 2
    elif mutation == "document_link":
        data["questions"][0]["document_ids"] = ["MISSING"]
    elif mutation == "capability_link":
        data["questions"][0]["capability_ids"] = ["MISSING"]
    elif mutation == "part_link":
        data["parts"][0]["analysis"] = ["Q99"]
    elif mutation == "concept_link":
        data["parts"][0]["concept_ids"] = ["MISSING"]
    elif mutation == "answer_link":
        data["teacher_answers"][0]["id"] = "Q99"
    elif mutation == "response":
        data["questions"][0]["response"]["lines"] = True
    elif mutation == "table":
        data["documents"][0]["table"]["rows"][0] = ["ragged"]
    elif mutation == "metadata":
        data["documents"][0]["text"] = "SQLite et CONTENT_GAP"
    elif mutation == "unknown_field":
        data["extra"] = "uncontrolled"
    else:
        data["capabilities"][0]["authority_status"] = "ADMITTED"
    with pytest.raises(ValueError):
        CourseChapter(data)


@pytest.mark.parametrize(
    "field",
    [
        "frame",
        "program_ref",
        "program_version",
        "theme_ref",
        "question_ref",
        "question_label",
        "subject_label",
        "level_label",
    ],
)
def test_other_programme_or_question_never_enters_m01(field):
    _, child = child_fixture()
    data = child.p0_bundle.mutable_copy()
    data["course_chapter"]["program_header"][field] = "different"
    with pytest.raises(ValueError, match="COURSE_PROGRAM_BINDING"):
        P0Production(data)


def test_student_projection_and_exports_exclude_answers_and_internal_provenance():
    _, child = child_fixture()
    bundle = child.p0_bundle
    student = json.dumps(bundle.student_projection(), ensure_ascii=False)
    assert (
        "ORACLE_PROF" not in student
        and "LOCAL_FICTION" not in student
        and "unit:fiction" not in student
    )
    assert "ORACLE_PROF_1" in json.dumps(bundle.teacher_projection())
    assert "ORACLE_PROF" not in json.dumps(as_plain(child.view.data))
    exporter = ExportSavedCommand(R6ReadableWordWriter(profile="diffusion-v6"))
    for kind in ("student", "correction"):
        raw = exporter.execute(child, kind)
        assert raw == exporter.execute(child, kind)
        with ZipFile(BytesIO(raw)) as z:
            assert z.testzip() is None
            text = z.read("word/document.xml").decode()
            assert ("ORACLE_PROF_1" in text) == (kind == "correction")
            assert "LOCAL_FICTION" not in text and "unit:fiction" not in text
            assert "Document 1" in text and "Tester ses connaissances" in text
            assert "pageBreakBefore" in text and "tblHeader" in text
            assert "Management" in z.read("word/header1.xml").decode().title()
            assert "PAGE" in z.read("word/footer1.xml").decode()
            assert not any(name.endswith(".bin") for name in z.namelist())
            assert b'TargetMode="External"' not in z.read("word/_rels/document.xml.rels")
    forged = WordDocument("student", "Synthetic", (), course_chapter=bundle.teacher_projection()["course_chapter"])
    with pytest.raises(ValueError, match="COURSE_WORD_PROJECTION"):
        CourseOOXMLWordWriter().write(forged)


def test_readable_projection_cannot_be_substituted_with_answer_text():
    _, child = child_fixture()
    data = child.p0_bundle.mutable_copy()
    data["sections"][0]["text"] = "ORACLE_PROF_1"
    with pytest.raises(ValueError, match="COURSE_STUDENT_PROJECTION_BINDING"):
        P0Production(data)
    record = child.mutable_copy()
    record["view"]["course_chapter"]["teacher_answers"] = copy.deepcopy(
        record["bundle"]["course_chapter"]["teacher_answers"]
    )
    with pytest.raises(ValueError, match="COURSE_STUDENT_ANSWER_FORBIDDEN"):
        SavedProduction(record)


def test_application_save_reopen_and_both_exports_preserve_parent(tmp_path):
    parent, child = child_fixture()
    before = parent.mutable_copy()
    records = {(r.production_ref, r.version_ref): r for r in (parent, child)}
    saved = build_saved_application(
        tmp_path / "store", create=True, source=lambda p, v: records[(p, v)]
    )
    saved.execute(
        "save",
        body={"production_ref": child.production_ref, "version_ref": child.version_ref},
        correlation="course.save",
    )
    again = build_saved_application(tmp_path / "store")
    result = again.execute(
        "open", child.production_ref, child.version_ref, correlation="course.reopen"
    )
    assert result["record_sha256"] == child.sha256 and result["active_authority"] == "NONE_RESTORED"
    for kind in ("student", "correction"):
        raw = again.execute(
            "word", child.production_ref, child.version_ref, kind=kind, correlation="course.export"
        )
        assert (
            hashlib.sha256(raw).hexdigest()
            == hashlib.sha256(
                ExportSavedCommand(R6ReadableWordWriter()).execute(child, kind)
            ).hexdigest()
        )
    assert parent.mutable_copy() == before
