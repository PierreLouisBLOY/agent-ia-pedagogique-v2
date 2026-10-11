"""Portable declared doubles: no private documents, SQLite or provider access."""
import copy

import pytest

from backend.adapters.outbound.generation.openai.p0_content import bind_p0_content
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
)
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_content_projection import request_for
from tools.mega_no_count.mega_content_ids import (
    CANDIDATE_STATUS,
    bind_candidate_status,
    normalize_ids,
)
from tools.mega_no_count.mega_no_count_gate import Budget, canonical, preflight


@pytest.mark.parametrize("family", ["COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"])
def test_case_mapping_and_local_status_keep_content_and_immutable_bindings(family):
    request = request_for(family)
    generated = dict(P0GenerationDouble().generate(request=request))
    content = {key: generated[key] for key in ("title", "sections", "questions", "corrections", "marking", "limitations")}
    for collection, field in (("sections", "section_id"), ("questions", "question_id"), ("corrections", "question_id"), ("marking", "question_id")):
        for row in content[collection]:
            row[field] = row[field].lower()
    content["limitations"] = ["DECLARED SYNTHETIC FIXTURE — unverified local source"]
    original = copy.deepcopy(content)
    with pytest.raises(ValueError):
        bind_p0_content(request, content)
    result, mapping = normalize_ids(content)
    result, annotation = bind_candidate_status(result)
    assert content == original and mapping and annotation == CANDIDATE_STATUS
    candidate = bind_p0_content(request, result)
    assert CreateP0Candidate().execute(candidate.mutable_copy(), evidence=request["evidence"]).sha256 == candidate.sha256
    for field in ("context", "references", "lineage", "production_ref", "version_ref"):
        assert candidate.mutable_copy()[field] == request[field]
    restored = copy.deepcopy(result)
    for collection, field in (("sections", "section_id"), ("questions", "question_id"), ("corrections", "question_id"), ("marking", "question_id")):
        for row in restored[collection]:
            row[field] = row[field].lower()
    restored["limitations"].pop()
    assert restored == original


def example():
    return {"sections": [{"section_id": "s1"}], "questions": [{"question_id": "q1"}],
        "corrections": [{"question_id": "q1"}], "marking": [], "limitations": ["SYNTHETIC"]}


@pytest.mark.parametrize("identifier", ["s", "1", "s.1", "section 1", "s" + "x" * 64, "ś1", "q1", 1])
def test_id_not_repaired_beyond_casing(identifier):
    content = example()
    content["sections"][0]["section_id"] = identifier
    with pytest.raises(ValueError, match="SHAPE_NOT_CASE_ONLY"):
        normalize_ids(content)


@pytest.mark.parametrize("identifier", ["s1", "S1"])
def test_duplicate_or_collision_refused(identifier):
    content = example()
    content["sections"].append({"section_id": identifier})
    with pytest.raises(ValueError, match="NORMALIZATION_COLLISION"):
        normalize_ids(content)


def test_foreign_reference_not_invented():
    content = example()
    content["corrections"][0]["question_id"] = "Q1"
    with pytest.raises(ValueError, match="REFERENCE_NOT_IN_ORIGINAL"):
        normalize_ids(content)


@pytest.mark.parametrize("limitations", [[], [""], "not an array", ["EXISTING"] * 16])
def test_original_limitation_preconditions_not_masked(limitations):
    content = example()
    content["limitations"] = limitations
    with pytest.raises(ValueError):
        bind_candidate_status(content)


def test_marking_error_is_preserved_and_refused_by_original_contract():
    request = request_for("ASSESSMENT")
    generated = dict(P0GenerationDouble().generate(request=request))
    content = {key: generated[key] for key in ("title", "sections", "questions", "corrections", "marking", "limitations")}
    content["marking"][0]["points"] = "19.00"
    normalized, _ = normalize_ids(content)
    normalized, _ = bind_candidate_status(normalized)
    with pytest.raises(ValueError, match="P0_MARKING_TOTAL"):
        bind_p0_content(request, normalized)


def test_inherited_consumption_cannot_reset_or_replay_m01():
    from decimal import Decimal
    ledger = Budget()
    ledger.reserve("M01", "CREATE", {"max_cost_usd": "0.0764345"})
    ledger.finish("M01", "CREATE", confirmed=True)
    with pytest.raises(ValueError, match="REPLAY_REFUSED"):
        ledger.reserve("M01", "CREATE", {"max_cost_usd": "0.0764345"})
    assert ledger.reserved == Decimal("0.0764345")
    ledger.reserve("M01", "REVIEW", {"max_cost_usd": "0.140000"})
    ledger.finish("M01", "REVIEW", confirmed=True)
    assert ledger.reserved == Decimal("0.2164345")
    for op in ("COUNT", "MODIFY"):
        with pytest.raises(ValueError, match="UNAPPROVED_OPERATION"):
            ledger.reserve("M01", op, {"max_cost_usd": "0.010000"})


def test_cache_write_margin_can_refuse_even_with_input_ceiling_met():
    body = {"background": False, "model": "gpt-5.6-terra", "instructions": "SYNTHETIC", "input": "SYNTHETIC",
        "max_output_tokens": 4096, "service_tier": "default", "store": False, "stream": False,
        "reasoning": {"effort": "low"}, "tools": [], "tool_choice": "none", "text": {}}
    tariff = {"model": "gpt-5.6-terra", "input_usd_per_million": "2.00", "output_usd_per_million": "12.00",
        "cache_write_input_factor": "1.25", "conservative_input_usd_per_million": "2.50"}
    def counter(request):
        return {"model": request["model"], "recognition": "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER", "encoding": "o200k_base",
            "network_forbidden_during_count": True, "local_text_tokens": 30000}
    with pytest.raises(ValueError, match="FINANCIAL_BOUND_EXCEEDED"):
        preflight(canonical(body), tariff, expected_sha=None, count=counter)
