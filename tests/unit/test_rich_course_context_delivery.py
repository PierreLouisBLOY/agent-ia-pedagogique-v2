"""Explicit format/number and delivery invariants; all data are synthetic."""

import copy

import pytest

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.course_delivery import (
    validate_course_delivery,
)
from tests.unit.test_course_chapter import chapter_data
from tests.unit.test_stmg_institutional_alignment import Catalog, app, context, prepare


def rich_context():
    data = context()
    data.update(contract_id="P0-CONTEXT-COURSE-3.0", course_format="CHAPTER")
    data["local_progression"]["chapter"] = "1"
    return data


def delivery_fixture():
    service = app(Catalog())
    confirmed = prepare(service, rich_context())["context"]
    chapter = chapter_data(confirmed)
    chapter["contract_id"] = "COURSE-CHAPTER-LINEAGE-3.0"
    chapter["documents"][0]["function"] = "METHOD"
    chapter["documents"][0]["provenance"] = {
        "kind": "LOCAL_FICTION",
        "source_ref": "LOCAL_APPLICATION_CONSTRUCTION",
    }
    return P0Context(confirmed), chapter


@pytest.mark.parametrize(
    "number", [None, "", "01", "0", "100", "Chapitre II", 1, True, " 1", "1.0"]
)
def test_rich_number_is_explicit_decimal_text_not_an_interpreted_title(number):
    data = rich_context()
    data["local_progression"]["chapter"] = number
    with pytest.raises(ValueError):
        P0Context(data)


@pytest.mark.parametrize("number", ["1", "99"])
def test_explicit_number_boundaries(number):
    data = rich_context()
    data["local_progression"]["chapter"] = number
    assert P0Context(data).data["local_progression"]["chapter"] == number


def test_legacy_explained_and_free_local_progression_are_unchanged():
    data = context()
    assert P0Context(data).as_dict() == data
    assert P0Context(data).course_format == "EXPLAINED"
    data.update(contract_id="P0-CONTEXT-COURSE-3.0", course_format="EXPLAINED")
    assert P0Context(data).as_dict() == data


def test_format_cannot_be_added_to_other_families_or_legacy_contract():
    data = rich_context()
    data["resource_type"] = "EXERCISE"
    with pytest.raises(ValueError, match="P0_COURSE_FORMAT"):
        P0Context(data)
    data = context()
    data["course_format"] = "CHAPTER"
    with pytest.raises(ValueError):
        P0Context(data)


@pytest.mark.parametrize("level", ["BTS_CG_YEAR_1", "BTS_CG_YEAR_2"])
def test_bts_rich_refuses_unsupported_header_before_any_resolver_or_dispatch(level):
    data = rich_context()
    data["level"] = level
    with pytest.raises(ValueError, match="P0_RICH_COURSE_LEVEL_UNSUPPORTED"):
        P0Context(data)


def test_rich_requires_its_contract_and_method_without_content_repair():
    ctx, chapter = delivery_fixture()
    with pytest.raises(ValueError, match="P0_RICH_COURSE_REQUIRED"):
        validate_course_delivery(ctx, None, [])
    changed = copy.deepcopy(chapter)
    changed["documents"][0]["function"] = "Observer"
    with pytest.raises(ValueError, match="METHOD_REQUIRED"):
        validate_course_delivery(ctx, changed, [])
    validate_course_delivery(ctx, chapter, [])


@pytest.mark.parametrize(
    "location", ["document", "cell", "context", "concept", "question", "synthesis"]
)
def test_substantive_teacher_copy_is_rejected_across_student_fields(location):
    ctx, chapter = delivery_fixture()
    sentinel = "La réponse réservée au professeur contient cette phrase distinctive pour contrôler une fuite exacte."
    chapter["teacher_answers"][0]["expected_answer"] = sentinel
    if location == "document":
        chapter["documents"][0]["text"] = sentinel
    elif location == "cell":
        chapter["documents"][0]["table"]["rows"][0][0] = sentinel
    elif location == "context":
        chapter["context"]["text"] = sentinel
    elif location == "concept":
        chapter["concepts"][0]["example"] = sentinel
    elif location == "question":
        chapter["questions"][0]["prompt"] = sentinel
    else:
        chapter["synthesis"] = sentinel
    with pytest.raises(ValueError, match="TEACHER_BLOCK_IN_STUDENT"):
        validate_course_delivery(ctx, chapter, [])


def test_short_fact_and_an_explicitly_taught_definition_are_not_false_leaks():
    ctx, chapter = delivery_fixture()
    chapter["teacher_answers"][0]["expected_answer"] = "2"
    chapter["documents"][0]["text"] = "2 participants préparent une activité."
    chapter["teacher_answers"][1]["expected_answer"] = chapter["concepts"][0]["definition"]
    validate_course_delivery(ctx, chapter, [])


@pytest.mark.parametrize("field", ["expected_answer", "rationale", "vigilance", "remediation"])
def test_unattested_official_claim_scan_includes_all_teacher_fields(field):
    ctx, chapter = delivery_fixture()
    chapter["teacher_answers"][0][field] = (
        "En BTS CG 1, cette activité est officiellement prescrite."
    )
    with pytest.raises(ValueError, match="PROGRAM_ALIGNMENT_UNVERIFIED_HUMAN_REVIEW_REQUIRED"):
        validate_course_delivery(ctx, chapter, [])


def test_rich_document_attribution_requires_an_exact_provided_evidence_id():
    ctx, chapter = delivery_fixture()
    evidence_id = "evidence:" + "9" * 32
    chapter["documents"][0]["provenance"] = {
        "kind": "SUPPLIED_REFERENCE",
        "source_ref": evidence_id,
    }
    with pytest.raises(ValueError, match="DOCUMENT_REFERENCE"):
        validate_course_delivery(ctx, chapter, [])
    validate_course_delivery(ctx, chapter, [{"evidence_id": evidence_id}])
