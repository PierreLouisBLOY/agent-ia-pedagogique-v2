"""Minimal synthetic counterexamples; never uses an old live candidate."""

import ast
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from types import ModuleType

import pytest

from backend.adapters.outbound.generation.openai.prepare_contract import normalized_prepare_text
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.agent_runtime.agents.generation import GenerationPortError
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.validation_control.domain.policies import assessment_checks as cap
from backend.modules.validation_control.domain.policies.assessment_checks import evaluate_checks
from tests.support.r3_cap_a01_guard import (
    PATHS,
    POST,
    PRE,
    SELF,
    assert_git_state,
    assert_scope,
    oracle_digest,
    source_matches,
    violations,
)
from tests.support.r3_synthetic import bundle, supplements


def mutated(name):
    data = supplements()
    data["limitations"].append("UNFORMALIZED_CONTENT")
    q = data["questions"][0]
    case = data["case_data"]
    calc = data["correction"]["answers"][0]["calculations"][0]
    if name == "question_locator_missing":
        del q["locator"]
    elif name == "question_locator_type":
        q["locator"] = "invalid"
    elif name == "question_locator_offset":
        q["locator"]["start"] = 1
    elif name == "question_locator_bool":
        q["locator"]["start"] = True
    elif name == "question_dossier_unknown":
        q["dossier_id"] = "unknown"
    elif name == "question_duplicate":
        data["questions"][1]["question_id"] = q["question_id"]
    elif name == "question_id_unknown":
        data["correction"]["answers"][0]["question_id"] = "unknown"
    elif name == "unit_locator_missing":
        del case["source_unit_locator"]
    elif name == "unit_locator_offset":
        case["source_unit_locator"]["start"] = 1
    elif name == "unit_label_whole_sentence":
        text = bundle().data["subject"]["sections"][1]["text"]
        case["source_unit_locator"].update(start=0, end=len(text), exact_text=text)
    elif name == "scale_missing":
        del case["source_scale"]
    elif name == "scale_unknown":
        case["source_scale"] = "USD"
    elif name == "currency_unknown":
        case["currency"] = "USD"
    elif name == "numeric_number":
        case["base_case"]["totals"]["stable_uses"] = 200000
    elif name == "numeric_invalid":
        case["base_case"]["totals"]["stable_uses"] = "NaN"
    elif name == "unit_silent_coercion":
        case["source_scale"] = "kEUR"
    elif name == "case_reference_unknown":
        calc["case_id"] = "unknown"
    elif name == "expression_reference_unknown":
        calc["expression"] = {"ref": "computed.UNKNOWN"}
    elif name == "expression_invalid":
        calc["expression"] = {"op": "MUL", "operands": []}
    elif name == "expression_depth":
        expr = {"ref": "totals.stable_uses"}
        for _ in range(4):
            expr = {"op": "ADD", "operands": [expr, {"ref": "totals.stable_uses"}]}
        calc["expression"] = expr
    elif name == "expression_operands":
        calc["expression"]["operands"] *= 9
    elif name == "calculation_locator_missing":
        del calc["locator"]
    elif name == "calculation_locator_offset":
        calc["locator"]["start"] = 1
    elif name == "calculation_count":
        data["correction"]["answers"][0]["calculations"] *= 61
    elif name == "calculation_global_count":
        for answer in data["correction"]["answers"]:
            answer["calculations"] *= 21
    elif name == "case_duplicate":
        case["scenarios"] = [deepcopy(case["base_case"])]
    elif name == "all_three_locators":
        q["locator"]["start"] = 1
        case["source_unit_locator"]["start"] = 1
        calc["locator"]["start"] = 1
    elif name != "nominal":
        raise AssertionError(name)
    return data


NAMES = (
    "nominal",
    "question_locator_missing",
    "question_locator_type",
    "question_locator_offset",
    "question_locator_bool",
    "question_dossier_unknown",
    "question_duplicate",
    "question_id_unknown",
    "unit_locator_missing",
    "unit_locator_offset",
    "unit_label_whole_sentence",
    "scale_missing",
    "scale_unknown",
    "currency_unknown",
    "numeric_number",
    "numeric_invalid",
    "unit_silent_coercion",
    "case_reference_unknown",
    "expression_reference_unknown",
    "expression_invalid",
    "expression_depth",
    "expression_operands",
    "calculation_locator_missing",
    "calculation_locator_offset",
    "calculation_count",
    "calculation_global_count",
    "case_duplicate",
    "all_three_locators",
)


def observe(name):
    # Preserve the historical schema-vs-canonical diagnostic table explicitly.
    # The new wire anchor contract has its own dedicated mutation matrix.
    from tests.support.r3_locator_materialization_guard import BASELINE as LOCATOR_BASELINE

    path = "backend/adapters/outbound/generation/openai/prepare_contract.py"
    raw = subprocess.run(["git", "show", f"{LOCATOR_BASELINE}:{path}"], cwd=ROOT,
                         check=True, capture_output=True).stdout
    historical = ModuleType("historical_prepare_offsets")
    exec(compile(raw, "<historical-prepare-offsets>", "exec"), historical.__dict__)
    proposal = mutated(name)
    trace = ParseDiagnostic()
    try:
        with trace.capture():
            historical.normalized_prepare_text(json.dumps(proposal), trace)
        schema = "ACCEPTED"
    except GenerationPortError:
        schema = "REJECTED"
    data = bundle().mutable_copy()
    data.update(proposal)
    candidate = AssessmentBundle(data)
    checks = evaluate_checks(candidate, parent=None, references=tuple(candidate.data["references"]))
    return {
        "mutation": name,
        "schema": schema,
        "boundary": "SYNTHETIC_DIRECT_DOMAIN_AND_PREPARE_SCHEMA",
        "checks": [
            {"id": c.check_id, "status": c.status, "reason_code": c.reason_code}
            for c in checks
            if c.check_id in {"A03", "A07", "A15", "A06", "A16"}
        ],
    }


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "5215f6071ce4f6f1519b3cb3e6be65d1d2e5179c"
EXPECTED = [
    [
        "nominal",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "question_locator_missing",
        "REJECTED",
        [
            ["FAIL", "A03_INVALID_OR_NON_EVALUABLE"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "question_locator_type",
        "REJECTED",
        [
            ["FAIL", "A03_INVALID_OR_NON_EVALUABLE"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "question_locator_offset",
        "ACCEPTED",
        [
            ["FAIL", "A03_LOCATOR_INVALID"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "question_locator_bool",
        "REJECTED",
        [
            ["FAIL", "A03_LOCATOR_INVALID"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "question_dossier_unknown",
        "REJECTED",
        [
            ["FAIL", "A03_REJECTED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "question_duplicate",
        "ACCEPTED",
        [
            ["FAIL", "A03_REJECTED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_REJECTED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "question_id_unknown",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_CALC_LOCATOR_INVALID"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "unit_locator_missing",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_UNIT_LOCATOR_MISSING"],
            ["FAIL", "A15_INVALID_OR_NON_EVALUABLE"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "unit_locator_offset",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_UNIT_LOCATOR_INVALID"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "unit_label_whole_sentence",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_UNIT_REFERENCE_INVALID"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "scale_missing",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_INVALID_OR_NON_EVALUABLE"],
            ["FAIL", "A15_INVALID_OR_NON_EVALUABLE"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "scale_unknown",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_UNIT_REFERENCE_INVALID"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "currency_unknown",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_REJECTED"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "numeric_number",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_NUMERIC_VALUE_INVALID"],
            ["FAIL", "A15_INVALID_OR_NON_EVALUABLE"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "numeric_invalid",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_NUMERIC_VALUE_INVALID"],
            ["FAIL", "A15_INVALID_OR_NON_EVALUABLE"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "unit_silent_coercion",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_UNIT_REFERENCE_INVALID"],
            ["PASS", "CHECK_SATISFIED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "case_reference_unknown",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_REJECTED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "expression_reference_unknown",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_INVALID_OR_NON_EVALUABLE"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "expression_invalid",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_CALC_EXPRESSION_INVALID"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "expression_depth",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_CALC_LIMIT_EXCEEDED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "expression_operands",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_CALC_COLLECTION_INVALID"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "calculation_locator_missing",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_INVALID_OR_NON_EVALUABLE"],
            ["FAIL", "A16_INVALID_OR_NON_EVALUABLE"],
        ],
    ],
    [
        "calculation_locator_offset",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_CALC_LOCATOR_INVALID"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "calculation_count",
        "REJECTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_CALC_COLLECTION_INVALID"],
            ["FAIL", "A16_INVALID_OR_NON_EVALUABLE"],
        ],
    ],
    [
        "calculation_global_count",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_REJECTED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "case_duplicate",
        "ACCEPTED",
        [
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A15_REJECTED"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
    [
        "all_three_locators",
        "ACCEPTED",
        [
            ["FAIL", "A03_LOCATOR_INVALID"],
            ["PASS", "CHECK_SATISFIED"],
            ["FAIL", "A07_UNIT_LOCATOR_INVALID"],
            ["FAIL", "A15_CALC_LOCATOR_INVALID"],
            ["WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED"],
        ],
    ],
]


@pytest.mark.parametrize(("name", "schema", "expected"), EXPECTED)
def test_exact_closed_outcomes_for_synthetic_mutations(name, schema, expected):
    result = observe(name)
    assert result["schema"] == schema
    assert [[c["status"], c["reason_code"]] for c in result["checks"]] == expected


@pytest.mark.parametrize("name", NAMES)
def test_no_business_predicate_or_status_is_weakened(name):
    path = "backend/modules/validation_control/domain/policies/assessment_checks.py"
    raw = subprocess.run(
        ["git", "show", f"{BASELINE}:{path}"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    old = ModuleType("historical_cap")
    exec(compile(raw, "<historical-cap>", "exec"), old.__dict__)
    data = bundle().mutable_copy()
    data.update(mutated(name))
    candidate = AssessmentBundle(data)
    args = dict(parent=None, references=tuple(candidate.data["references"]))
    before, after = old.evaluate_checks(candidate, **args), cap.evaluate_checks(candidate, **args)
    assert [(c.check_id, c.status) for c in before] == [(c.check_id, c.status) for c in after]
    for left, right in zip(before, after, strict=True):
        if left.check_id not in {"A03", "A07", "A15"}:
            assert left == right
    old_nodes = {n.name: ast.dump(n) for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
    new_nodes = {
        n.name: ast.dump(n)
        for n in ast.parse((ROOT / path).read_bytes()).body
        if isinstance(n, ast.FunctionDef)
    }
    from tests.support.r3_editorial_correction_guard import assert_predicates

    assert_predicates(ROOT)
    for symbol in old_nodes.keys() - {"evaluate_checks", "check_rule"}:
        assert old_nodes[symbol] == new_nodes[symbol]


@pytest.mark.parametrize("index", [3, 7, 15])
def test_arbitrary_exception_values_are_never_exposed(index):
    for error in (
        ValueError("PRIVATE_SENTINEL"),
        KeyError("PRIVATE_SENTINEL"),
        TypeError("PRIVATE_SENTINEL"),
        ValueError(object()),
    ):
        reason = cap._targeted_reason(index, error)
        assert reason == f"A{index:02}_INVALID_OR_NON_EVALUABLE"
        assert "PRIVATE_SENTINEL" not in reason


@pytest.mark.parametrize("scale", ["EUR", "kEUR"])
def test_unit_conversion_and_nominal_warning_preserved(scale):
    from tests.support.r3_locator_fixtures import wire_supplements

    original = wire_supplements(scale)
    assert json.loads(normalized_prepare_text(json.dumps(original), ParseDiagnostic())) == original
    data = bundle(scale).mutable_copy()
    data["limitations"].append("UNFORMALIZED_CONTENT")
    candidate = AssessmentBundle(data)
    checks = cap.evaluate_checks(
        candidate, parent=None, references=tuple(candidate.data["references"])
    )
    assert [c.status for c in checks] == ["PASS"] * 15 + ["WARNING"]
    assert checks[15].reason_code == "SEMANTIC_HUMAN_REVIEW_REQUIRED"


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.usefixtures("historical_guard_sources")
def test_each_targeted_successor_identity_is_closed(tmp_path, path):
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS

    for item in set(PATHS) | set(LOCATOR_PATHS) | set(EDITORIAL_PATHS) | set(PORTABLE_PATHS) | set(D3_PATHS):
        target = tmp_path / item
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / item).read_bytes())
    assert violations(tmp_path) == []
    target = tmp_path / path
    target.write_bytes(target.read_bytes() + b"\nUNAPPROVED_CAP_MUTATION = True\n")
    assert violations(tmp_path)
    if path in PRE:
        assert not source_matches(tmp_path, path, PRE[path])


@pytest.mark.parametrize("path", PATHS)
def test_staged_drift_is_not_hidden_by_clean_working_bytes(monkeypatch, path):
    original = subprocess.run

    def mutated_index(args, **kwargs):
        if args == ["git", "show", ":" + path]:
            return subprocess.CompletedProcess(
                args, 0, stdout=(ROOT / path).read_bytes() + b"\nUNAPPROVED_INDEX_DRIFT = True\n"
            )
        return original(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mutated_index)
    with pytest.raises(AssertionError):
        assert_git_state(ROOT)


@pytest.mark.parametrize("mutation", ["missing", "extra", "same_count"])
def test_exact_inventory_not_count_only(mutation):
    paths = set(PATHS)
    if mutation != "extra":
        paths.remove(PATHS[0])
    if mutation != "missing":
        paths.add("backend/unapproved.py")
    assert violations(ROOT, changed=paths)


@pytest.mark.usefixtures("historical_guard_sources")
def test_frozen_scope_working_index_history_and_self_authentication():
    from tests.support.r3_cap_a01_guard import ORACLE_AST_SHA256
    from tests.support.r3_locator_materialization_guard import PRE as LOCATOR_PRE
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches

    assert_scope(ROOT)
    assert_git_state(ROOT)
    raw = (ROOT / SELF).read_bytes()
    assert (oracle_digest(raw) == ORACLE_AST_SHA256
            or locator_matches(ROOT, SELF, LOCATOR_PRE[SELF]))
    assert (
        oracle_digest(raw.replace(next(iter(POST.values())).encode(), b"0" * 64))
        != ORACLE_AST_SHA256
    )
    for path in PRE:
        assert source_matches(ROOT, path, PRE[path])
        assert not source_matches(ROOT, path, "0" * 64)
