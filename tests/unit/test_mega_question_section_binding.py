"""Declared synthetic fixtures exercise the existing canonical creation contract."""
import copy

import pytest

from backend.adapters.outbound.generation.openai.p0_content import bind_p0_content
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
)
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_content_projection import request_for
from tools.mega_no_count.mega_content_ids import bind_candidate_status, normalize_ids
from tools.mega_no_count.mega_question_section_binding import bind_question_title_section


def fixture(family):
    request = request_for(family)
    generated = dict(P0GenerationDouble().generate(request=request))
    content = {key: generated[key] for key in ("title", "sections", "questions", "corrections", "marking", "limitations")}
    content["sections"] = []
    return request, content


@pytest.mark.parametrize("family", ["QCM", "QUIZ", "OPEN_QUESTIONS", "EXERCISE", "ASSESSMENT"])
def test_question_only_title_projection_creates_canonical_candidate_without_changing_teaching_content(family):
    request, original = fixture(family)
    if family in {"QCM", "QUIZ", "OPEN_QUESTIONS"}:
        assert request["context"]["resource_type"] == "QUESTION_SET"
        assert request["context"]["question_mode"] == family
    before = copy.deepcopy(original)
    with pytest.raises(ValueError, match="P0_SECTIONS"):
        bind_p0_content(request, original)
    projected, note = bind_question_title_section(original, family)
    assert original == before
    assert note["text_source"] == "EXACT_ORIGINAL_TITLE"
    assert projected["sections"][0]["text"] == original["title"]
    for key in original.keys() - {"sections"}:
        assert projected[key] == original[key]
    normalized, _ = normalize_ids(projected)
    normalized, _ = bind_candidate_status(normalized)
    candidate = bind_p0_content(request, normalized)
    assert CreateP0Candidate().execute(candidate.mutable_copy(), evidence=request["evidence"]).sha256 == candidate.sha256
    for key in ("production_ref", "version_ref", "context", "references", "lineage"):
        assert candidate.mutable_copy()[key] == request[key]


def test_existing_sections_never_rewritten_and_projection_is_idempotent():
    _, content = fixture("QCM")
    projected, _ = bind_question_title_section(content, "QCM")
    again, note = bind_question_title_section(projected, "QCM")
    assert again == projected and note is None
    again["sections"][0]["text"] = "Changed copy"
    assert projected["sections"][0]["text"] == content["title"]


@pytest.mark.parametrize("family", ["COURSE", "UNKNOWN", "", "qcm"])
def test_no_section_fabricated_for_empty_course_or_unknown_family(family):
    _, content = fixture("QCM")
    with pytest.raises(ValueError, match="FAMILY_NOT_QUESTION_BASED"):
        bind_question_title_section(content, family)


@pytest.mark.parametrize("key,value", [("sections", None), ("sections", {}), ("questions", []), ("questions", None),
                                       ("title", ""), ("title", " "), ("title", "x" * 201), ("title", 3)])
def test_malformed_preconditions_are_not_repaired(key, value):
    _, content = fixture("QCM")
    content[key] = value
    with pytest.raises(ValueError):
        bind_question_title_section(content, "QCM")


def test_invalid_answer_and_assessment_marking_still_fail_canonical_guard():
    request, content = fixture("QCM")
    content["corrections"][0]["expected_answer"] = "Not an option"
    projected, _ = bind_question_title_section(content, "QCM")
    with pytest.raises(ValueError):
        bind_p0_content(request, projected)
    request, content = fixture("ASSESSMENT")
    content["marking"][0]["points"] = "0.00"
    projected, _ = bind_question_title_section(content, "ASSESSMENT")
    with pytest.raises(ValueError):
        bind_p0_content(request, projected)
