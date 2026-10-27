"""Editorial-only changes; original records and all source authority stay intact."""
from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.materialization_export.application.services.exercise_projection import (
    project_exercise,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from tests.exercise_quality_fixture import blueprint
from tests.test_exercise_quality_323b import prepare


def xml(document):
    with ZipFile(BytesIO(CourseOOXMLWordWriter().write(document))) as z:
        return z.read("word/document.xml").decode()


def test_internal_references_and_status_stay_in_teacher_and_record_only():
    d, c = blueprint()
    d["references"][0].update(source_ref="notion:attitude", locator="search-chunk:323d-synthetic-reference")
    record = prepare(d, c)
    bundle = record.p0_bundle
    identity = bundle.sha256
    student = project_exercise(bundle, "student")
    teacher = project_exercise(bundle, "correction")
    shown = xml(student)
    assert not any(s in shown for s in ("notion:", "search-chunk:", "Sources et statut", "CONTENT_GAP", "Réponse attendue", "Remédiation"))
    assert student.exercise_content["source_notes"] == ()
    assert "notion:attitude" in xml(teacher) and "search-chunk:323d-synthetic-reference" in xml(teacher)
    assert bundle.sha256 == identity and bundle.data["references"][0]["source_ref"] == "notion:attitude"


def test_role_is_separate_from_the_unchanged_pedagogical_title():
    record = prepare()
    student = project_exercise(record.p0_bundle, "student")
    teacher = project_exercise(record.p0_bundle, "correction")
    assert student.title == teacher.title == record.p0_bundle.data["title"]
    assert teacher.exercise_content["notice"] == "Corrigé professeur — propositions à relire."
    assert student.exercise_content["notice"] == "Exercice"
    assert "Démonstration locale" not in xml(student)


def test_singular_and_plural_human_document_references():
    record = prepare()
    shown = xml(project_exercise(record.p0_bundle, "student"))
    assert "(Document 1)" in shown and "(Documents 1, 2)" in shown
    assert "Documents D1" not in shown


@pytest.mark.parametrize("text", ["search-chunk:private", "notion:attitude", "a" * 64, "PARSING_REJECTED", "SYNTHETIC_FIXTURE", "CANDIDATE", "NOT_PERFORMED", "APPLICATION_SAVED", "evidence:" + "b" * 32, "context:" + "c" * 24])
def test_technical_pedagogical_text_is_refused_never_silently_removed(text):
    d, c = blueprint()
    c["exercise"]["questions"][0]["prompt"] += " " + text
    record = prepare(d, c)
    before = record.p0_bundle.sha256
    with pytest.raises(ValueError, match="EXERCISE_STUDENT_TECHNICAL_METADATA"):
        project_exercise(record.p0_bundle, "student")
    assert record.p0_bundle.sha256 == before
    assert text in xml(project_exercise(record.p0_bundle, "correction"))


def test_forged_source_notes_or_title_cannot_bypass_student_projection():
    document = project_exercise(prepare().p0_bundle, "student")
    raw = document.as_dict()["exercise_content"]
    raw["source_notes"] = ["search-chunk:private"]
    with pytest.raises(ValueError, match="EXERCISE_STUDENT_TECHNICAL_METADATA"):
        WordDocument("student", document.title, document.blocks, exercise_profile=document.exercise_profile, exercise_content=raw)
    with pytest.raises(ValueError, match="EXERCISE_STUDENT_TECHNICAL_METADATA"):
        xml(replace(document, title="notion:private"))


def test_actual_export_command_with_local_reservations_retains_role_and_disclaimer():
    record = prepare()
    exporter = ExportSavedCommand(R6ReadableWordWriter(profile="product-v7"), product_projection=True)
    student = exporter.preview(record, "student")
    teacher = exporter.preview(record, "correction")
    assert "sans génération fournisseur" in student.exercise_content["notice"]
    assert teacher.exercise_content["notice"].startswith("Corrigé professeur")
    assert "qualification locale" in teacher.exercise_content["notice"]
    assert all("source_ref" not in block.text and "search-chunk:" not in block.text for block in student.blocks)
    assert "Traçabilité interne du professeur" not in xml(student)
    assert "Corrigé professeur" in xml(teacher)
