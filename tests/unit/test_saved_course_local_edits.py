"""Structured local COURSE edits never relabel sources or invalidate existing media."""
from secrets import token_hex

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_design.application.commands.edit_saved_course import (
    apply_course_edits,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from tests.unit.test_course_chapter import child_fixture
from tests.unit.test_course_media import media_chapter
from tests.unit.test_course_media_persistence import record_version
from tests.unit.test_integrated_saved_p0_resume import resume_with
from tests.unit.test_p0_agentic_routing import identity


def test_structured_course_local_edit_preserves_programme_and_teacher_boundary_after_restart(tmp_path):
    ancestor, parent = child_fixture()
    records = {ancestor.version_ref: ancestor, parent.version_ref: parent}
    service = resume_with(records)
    view = service.read(parent.production_ref, parent.version_ref)
    changed = service.execute("revise", {"command_id": token_hex(16), **identity(view), "edits": {
        "title": "Cours modifié localement", "course_edits": {
            "context": {"text": "Les participants analysent une répartition locale des tâches."},
            "questions": [{"id": "Q1", "prompt": "Identifiez les rôles de chacun."}],
            "teacher_answers": [{"id": "Q1", "expected_answer": "ORACLE_PROF_NOUVEAU"}]}}})
    child = service.saved_source(parent.production_ref, changed["view"]["version_ref"])
    assert child.p0_bundle.data["course_chapter"]["program_header"] == parent.p0_bundle.data["course_chapter"]["program_header"]
    assert child.p0_bundle.data["references"] == parent.p0_bundle.data["references"]
    assert child.p0_bundle.data["sections"] != parent.p0_bundle.data["sections"]
    assert "ORACLE_PROF_NOUVEAU" not in str(changed["view"])
    assert changed["quality"]["sources"] == "RESERVE"
    records[child.version_ref] = child
    library = build_saved_application(tmp_path / "library", create=True,
                                      source=lambda production, version: records[version], word_profile="product-v7")
    for record in (ancestor, parent, child):
        library.execute("save", body={"production_ref": record.production_ref, "version_ref": record.version_ref}, correlation="unit.course.save")
    restarted = build_saved_application(tmp_path / "library", word_profile="product-v7")
    reopened = resume_with({record.version_ref: restarted.read_local_p0(record.production_ref, record.version_ref)
                           for record in (ancestor, parent, child)})
    assert reopened.read(child.production_ref, child.version_ref) == changed["view"]
    assert reopened.saved_source(parent.production_ref, parent.version_ref).sha256 == parent.sha256
    import io
    import zipfile
    for public in ("student", "correction"):
        raw = restarted.execute("word", child.production_ref, child.version_ref, kind=public, correlation="unit.course.export")
        with zipfile.ZipFile(io.BytesIO(raw)) as document:
            xml = document.read("word/document.xml")
            assert (b"ORACLE_PROF_NOUVEAU" in xml) == (public == "correction")


@pytest.mark.parametrize("edits,code", [
    ({"sections": []}, "P0_COURSE_PROJECTION_READ_ONLY"),
    ({"course_edits": {"program_header": {}}}, "P0_COURSE_EDITS_REJECTED"),
    ({"course_edits": {"questions": [{"id": "Q99", "prompt": "Autre"}]}}, "P0_COURSE_EDIT_ID"),
    ({"course_edits": {"questions": [{"id": "Q1", "prompt": "Autre"}, {"id": "Q1", "prompt": "Encore"}]}}, "P0_COURSE_EDIT_ID"),
    ({"course_edits": {"concepts": [{"id": "N1", "authority_status": "ADMITTED"}]}}, "P0_COURSE_EDITS_REJECTED"),
    ({"course_edits": {"documents": [{"id": "D1", "provenance": {}}]}}, "P0_COURSE_EDITS_REJECTED"),
])
def test_course_edit_mutations_preserve_parent(edits, code):
    _, parent = child_fixture()
    before = parent.sha256
    with pytest.raises(ValueError, match=code):
        apply_course_edits(parent.p0_bundle.data, edits)
    assert parent.sha256 == before


def test_supplied_reference_is_not_rewritten_as_an_admitted_source():
    _, parent = child_fixture()
    data = parent.p0_bundle.mutable_copy()
    data["course_chapter"]["documents"][0]["provenance"]["kind"] = "SUPPLIED_REFERENCE"
    with pytest.raises(ValueError, match="P0_COURSE_SUPPLIED_REFERENCE_EDIT_REQUIRES_ADMISSION"):
        apply_course_edits(data, {"course_edits": {"documents": [{"id": "D1", "text": "Texte substitué"}]}})


def test_illustrated_title_edit_preserves_assets_but_content_edit_is_rejected():
    parent, chapter, _, _ = media_chapter()
    record = record_version(parent, chapter, 10)
    data = apply_course_edits(record.p0_bundle.data, {"title": "Variante du titre", "course_edits": {}})
    assert P0Production(data).data["course_chapter"]["media_assets"] == chapter.data["media_assets"]
    assert as_plain(record.p0_bundle.data["course_chapter"]) == as_plain(chapter.data)
    with pytest.raises(ValueError, match="P0_COURSE_MEDIA_DEPENDENCY_CHANGED"):
        apply_course_edits(record.p0_bundle.data, {"course_edits": {"synthesis": "Une synthèse nouvelle."}})


def test_historical_reframe_requires_successful_validation_before_local_resume():
    from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction

    parent, child = child_fixture()
    data = child.mutable_copy()
    data["validations"][0]["status"] = "FAIL"
    failed = SavedProduction(data)
    service = resume_with({parent.version_ref: parent, failed.version_ref: failed})
    with pytest.raises(ValueError, match="P0_SAVED_LINEAGE_BINDING"):
        service.read(failed.production_ref, failed.version_ref)
    assert service.records == service.plans == service.resumed == {}


def test_verified_historical_reframe_keeps_exact_parent_and_source_reserve():
    parent, child = child_fixture()
    service = resume_with({parent.version_ref: parent, child.version_ref: child})
    view = service.read(child.production_ref, child.version_ref)
    result = service.execute("validate", {"command_id": token_hex(16), **identity(view)})
    assert view["bundle_sha256"] == child.p0_bundle.sha256
    assert result["status"] == "PASS" and result["quality"]["sources"] == "RESERVE"
    assert service.saved_source(parent.production_ref, parent.version_ref).sha256 == parent.sha256
    assert service.evidence[child.version_ref] == {}
