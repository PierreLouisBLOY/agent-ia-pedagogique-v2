"""Exact synthetic anchors, canonical offsets and closed successor adversaries."""
import json
import subprocess
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from backend.adapters.outbound.generation.openai.locator_materialization import (
    LocatorMaterializationError,
    calculation_locators,
    materialize_anchor,
    materialized_prepare_text,
)
from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.adapters.outbound.generation.openai.prepare_contract import normalized_prepare_text
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.agent_runtime.agents.generation import GenerationPortError
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import locate
from tests.support.r3_locator_fixtures import wire_supplements
from tests.support.r3_locator_materialization_guard import (
    PATHS,
    POST,
    PRE,
    SELF,
    assert_git_state,
    assert_scope,
    authenticated,
    source_matches,
    violations,
)
from tests.support.r3_synthetic import subject, supplements
from tests.unit.test_openai_generation_adapter import _model
from tests.unit.test_r3_prepare_contract_alignment import prepare_request

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(("text", "quote", "start"), [
    ("préfixe Q1 fin", "Q1", 8),
    ("😀é e\u0301 : Q1", "Q1", 8),
    (" EUR ", " EUR ", 0),
    ("xx k€ fin", "k€", 3),
    ("xx milliers d'euros fin", "milliers d'euros", 3),
])
def test_exact_unique_subject_or_unit_anchor_uses_python_indices(text, quote, start):
    sections = [{"section_id": "DOSSIER_1", "text": text}]
    loc = materialize_anchor("DOSSIER_1", quote, sections)
    assert loc == {"section_id": "DOSSIER_1", "start": start,
                   "end": start + len(quote), "exact_text": quote}
    assert locate(loc, sections) == quote


@pytest.mark.parametrize(("text", "quote", "code"), [
    ("Question", "question", "LOCATOR_ANCHOR_NOT_FOUND"),
    ("Question", " Question", "LOCATOR_ANCHOR_NOT_FOUND"),
    ("é", "e\u0301", "LOCATOR_ANCHOR_NOT_FOUND"),
    ("Q1 Q1", "Q1", "LOCATOR_ANCHOR_AMBIGUOUS"),
    ("aaa", "aa", "LOCATOR_ANCHOR_AMBIGUOUS"),
    ("EUR EUR", "EUR", "LOCATOR_ANCHOR_AMBIGUOUS"),
    ("euros", "EUR", "LOCATOR_ANCHOR_NOT_FOUND"),
    ("Q1", "", "LOCATOR_ANCHOR_NOT_FOUND"),
])
def test_no_normalization_first_match_or_missing_anchor_repair(text, quote, code):
    with pytest.raises(LocatorMaterializationError, match="^" + code + "$"):
        materialize_anchor("DOSSIER_1", quote, [{"section_id": "DOSSIER_1", "text": text}])


@pytest.mark.parametrize("sections", [[], [{"section_id": "DOSSIER_2", "text": "Q1"}],
    [{"section_id": "DOSSIER_1", "text": "Q1"}] * 2,
    [{"section_id": "DOSSIER_1", "text": None}]])
def test_section_must_exist_exactly_once(sections):
    with pytest.raises(LocatorMaterializationError, match="^LOCATOR_SECTION_UNKNOWN$"):
        materialize_anchor("DOSSIER_1", "Q1", sections)


@pytest.mark.parametrize(("text", "values", "starts"), [
    ("100.00 EUR", ["100.00"], [0]),
    ("😀 1.00 ; é 2.00.", ["2.00", "1.00"], [11, 2]),
    ("1.00 puis 1.00", ["1.00", "1.00"], [0, 10]),
    ("1.00 / 2.00 / 1.00", ["1.00", "2.00", "1.00"], [0, 7, 14]),
    ("1.00 / 1.00 / 1.00", ["1.00", "1.00"], [0, 7]),
])
def test_calculation_assignment_is_exact_ordered_non_reusing(text, values, starts):
    locators = calculation_locators("q1", text, values)
    assert [loc["start"] for loc in locators] == starts
    for loc, value in zip(locators, values, strict=True):
        assert locate(loc, [{"section_id": "q1", "text": text}]) == value
    assert len({(loc["start"], loc["end"]) for loc in locators}) == len(locators)
    assert calculation_locators("q1", text, values) == locators


@pytest.mark.parametrize(("text", "values"), [
    ("1.00", ["1.00", "1.00"]), ("1,00", ["1.00"]),
    ("11.00", ["11.00", "1.00"]), ("1.00", ["1"]), ("1.00", [1]),
])
def test_missing_or_overlapping_calculation_occurrences_fail_closed(text, values):
    with pytest.raises(LocatorMaterializationError, match="^CALC_VALUE_OCCURRENCE_INSUFFICIENT$"):
        calculation_locators("q1", text, values)


@pytest.mark.parametrize(("qid", "text"), [("", "1.00"), ("q1", ""), (None, "1.00")])
def test_invalid_answer_section(qid, text):
    with pytest.raises(LocatorMaterializationError, match="^CALC_ANSWER_SECTION_INVALID$"):
        calculation_locators(qid, text, ["1.00"])


@pytest.mark.parametrize("fault", ["question_start", "question_end", "unit_start", "unit_end",
                                  "calc_locator", "whole_legacy", "extra_anchor"])
def test_provider_offsets_and_old_forms_rejected_before_materialization(fault):
    data = wire_supplements()
    if fault == "whole_legacy":
        data = supplements()
    elif fault == "calc_locator":
        data["correction"]["answers"][0]["calculations"][0]["locator"] = {"section_id": "q1"}
    else:
        target = data["case_data"]["source_unit_locator"] if fault.startswith("unit") else data["questions"][0]["locator"]
        target[fault.split("_")[-1]] = 0
    trace = ParseDiagnostic()
    with pytest.raises(GenerationPortError), trace.capture():
        materialized_prepare_text(json.dumps(data), prepare_request(), trace)
    assert trace.snapshot()["parse_stage"] == "SCHEMA_VALIDATE"


@pytest.mark.parametrize("scale", ["EUR", "kEUR"])
def test_lossless_semantic_fields_and_canonical_internal_shape(scale):
    wire = wire_supplements(scale)
    before = deepcopy(wire)
    req = replace(prepare_request(), resolved_inputs={"subject": subject(scale)})
    assert json.loads(normalized_prepare_text(json.dumps(wire), ParseDiagnostic())) == wire
    result = json.loads(materialized_prepare_text(json.dumps(wire), req, ParseDiagnostic()))
    assert wire == before
    assert result == supplements(scale)
    assert req.resolved_inputs["subject"]["content"] == subject(scale)["content"]


def test_neutral_contract_stays_canonical_but_provider_has_no_locator_authority():
    req = prepare_request()
    before = req.output_contract
    wire = build_openai_request(request=req, model_profile=_model())
    contract = json.loads(wire.input_json)["output_contract"]
    assert "locator" not in contract["calculation_fields"]
    assert "locator" in req.output_contract["calculation_fields"]
    assert req.output_contract == before
    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["properties"]) == set(node["required"])
                assert not {"start", "end"} & set(node["properties"])
            for child in node.values():
                check(child)
        elif isinstance(node, list):
            for child in node:
                check(child)
    check(wire.output_schema)


@pytest.mark.parametrize("path", PATHS)
def test_every_successor_file_mutation_is_rejected(tmp_path, path):
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS

    for item in set(PATHS) | set(EDITORIAL_PATHS) | set(PORTABLE_PATHS) | set(D3_PATHS):
        target = tmp_path / item
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / item).read_bytes())
    assert violations(tmp_path) == []
    target = tmp_path / path
    target.write_bytes(target.read_bytes() + b"\nUNAPPROVED = True\n")
    assert violations(tmp_path)
    if path in PRE:
        assert not source_matches(tmp_path, path, PRE[path])


@pytest.mark.parametrize("path", PATHS)
def test_index_drift_never_hidden_by_correct_working_bytes(monkeypatch, path):
    original = subprocess.run
    def drift(args, **kwargs):
        if args == ["git", "show", ":" + path]:
            return subprocess.CompletedProcess(args, 0, stdout=(ROOT / path).read_bytes() + b"\n# drift\n")
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", drift)
    with pytest.raises(AssertionError):
        assert_git_state(ROOT)


@pytest.mark.parametrize("fault", ["missing", "extra", "same_count"])
def test_exact_inventory_not_count_only(fault):
    paths = set(PATHS)
    if fault != "extra":
        paths.remove(PATHS[0])
    if fault != "missing":
        paths.add("backend/unapproved.py")
    assert violations(ROOT, changed=paths)


def test_frozen_tables_symbols_canonical_predicates_and_working_index(tmp_path):
    assert_scope(ROOT)
    assert_git_state(ROOT)
    for path in PRE:
        assert source_matches(ROOT, path, PRE[path])
        assert not source_matches(ROOT, path, "0" * 64)
    target = tmp_path / SELF
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / SELF).read_bytes().replace(next(iter(POST.values())).encode(), b"0" * 64))
    assert not authenticated(tmp_path)
