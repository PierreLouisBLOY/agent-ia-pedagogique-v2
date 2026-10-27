"""Opt-in plain chapter succession; all data and stores are synthetic."""
import copy

import pytest

from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
    COURSE_LINEAGE_CONTRACT,
    CourseChapter,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.unit.test_course_chapter import child_fixture
from tests.unit.test_course_media_persistence import record_version


def lineage_fixture():
    _, parent = child_fixture()
    data = as_plain(parent.p0_bundle.data["course_chapter"])
    data["contract_id"] = COURSE_LINEAGE_CONTRACT
    chapter = CourseChapter(data)
    chapter.bind_context(parent.p0_bundle.context)
    return parent, chapter


def test_explicit_plain_lineage_preserves_three_ancestors_and_rejects_thirty_third(tmp_path):
    parent, chapter = lineage_fixture()
    store = LocalSavedProductionStore(tmp_path / "store", create=True)
    originals = [record_version(parent, chapter, n, False) for n in range(1, 4)]
    for record in originals:
        store.save(record)
    with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
        store.save(record_version(parent, chapter, 4, False))
    for n in range(4, 33):
        store.save(record_version(parent, chapter, n))
    final = record_version(parent, chapter, 32)
    assert store.save(final) is False
    before = {r.version_ref: r.sha256 for r in store.list_versions()}
    with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
        store.save(record_version(parent, chapter, 33))
    assert {r.version_ref: r.sha256 for r in store.list_versions()} == before
    changed = final.mutable_copy()
    changed["reservations"].append("changed")
    with pytest.raises(ValueError, match="R4_IDENTITY_CONFLICT"):
        store.save(SavedProduction(changed))
    reopened = build_saved_application(tmp_path / "store")
    assert len(reopened.execute("list", correlation="lineage.list")["versions"]) == 32
    for record in (*originals, final):
        opened = reopened.execute("open", record.production_ref, record.version_ref,
                                  correlation="lineage.open")
        assert opened["record_sha256"] == before[record.version_ref]
        assert opened["active_authority"] == "NONE_RESTORED"
    for kind in ("student", "correction"):
        raw = reopened.execute("word", final.production_ref, final.version_ref,
                               kind=kind, correlation="lineage.word")
        assert raw == build_saved_application(tmp_path / "store").execute(
            "word", final.production_ref, final.version_ref, kind=kind,
            correlation="lineage.restart.word")


def test_imported_plain_lineage_keeps_three_version_limit(tmp_path):
    parent, chapter = lineage_fixture()
    store = LocalSavedProductionStore(tmp_path / "store", create=True)
    def imported(number):
        data = record_version(parent, chapter, number).mutable_copy()
        data["origin"] = "IMPORTED_DOCUMENTARY"
        return SavedProduction(data)
    for number in range(1, 4):
        store.save(imported(number))
    before = {r.version_ref: r.sha256 for r in store.list_versions()}
    with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
        store.save(imported(4))
    assert {r.version_ref: r.sha256 for r in store.list_versions()} == before


@pytest.mark.parametrize("mutation", ["unknown", "media_fields", "missing_answers", "wrong_document", "wrong_question_order"])
def test_plain_lineage_keeps_closed_contract_and_content_bindings(mutation):
    _, chapter = lineage_fixture()
    data = copy.deepcopy(as_plain(chapter.data))
    if mutation == "unknown":
        data["contract_id"] = "COURSE-CHAPTER-LINEAGE-3.1"
    elif mutation == "media_fields":
        data["visual_briefs"] = []
        data["media_assets"] = []
    elif mutation == "missing_answers":
        data["teacher_answers"].pop()
    elif mutation == "wrong_document":
        data["questions"][0]["document_ids"] = ["UNKNOWN"]
    else:
        data["questions"][0]["number"] = 2
    with pytest.raises(ValueError):
        CourseChapter(data)


def test_plain_lineage_rejects_wrong_program_and_separates_teacher_projection():
    parent, chapter = lineage_fixture()
    wrong = as_plain(chapter.data)
    wrong["program_header"]["question_ref"] = "framework-element:wrong"
    with pytest.raises(ValueError, match="COURSE_PROGRAM_BINDING"):
        CourseChapter(wrong).bind_context(parent.p0_bundle.context)
    student = chapter.projection()
    teacher = chapter.projection(teacher=True)
    assert "teacher_answers" not in student
    assert teacher["teacher_answers"] == as_plain(chapter.data)["teacher_answers"]
    for document in student["documents"]:
        assert "provenance" not in document
    for capacity in student["capabilities"]:
        assert set(capacity) == {"id", "label"}
