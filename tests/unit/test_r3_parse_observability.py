"""Synthetic differential and closed-oracle tests; no provider or user fixtures."""
import ast
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from backend.adapters.outbound.generation import assessment_revision as inner
from backend.adapters.outbound.generation.openai import adapter as outer
from backend.adapters.outbound.generation.parse_diagnostic import (
    ParseCode,
    ParseDiagnostic,
    ParseStage,
    ParseStatus,
)
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse, OpenAIResponseStatus
from tests.support.r3_parse_observability_guard import (
    ADAPTER,
    BASELINE,
    GUARD_SYMBOLS,
    PATCH_PATHS,
    SELF,
    assert_guard_extension,
    assert_patch_git_state,
    patch_violations,
)
from tests.unit.test_openai_generation_adapter import _model, _payload, _provider, _request

ROOT = Path(__file__).resolve().parents[2]
MARKER = "PRIVATE_SENTINEL_NOT_FOR_DIAGNOSTICS"


def historical(path):
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    module = ModuleType("synthetic_historical_parser")
    exec(compile(raw, "<historical-parser>", "exec"), module.__dict__)
    return module


def outcome(function, *args, **kwargs):
    try:
        return ("RETURN", function(*args, **kwargs))
    except Exception as error:
        return ("RAISE", type(error), error.args)


def mapped(module, response, trace=None):
    params = {"request": _request(), "response": response,
              "provider_profile": _provider(), "model_profile": _model()}
    if trace is not None:
        params["diagnostic"] = trace
    return outcome(module._map_response, **params)


def altered(**changes):
    data = json.loads(_payload())
    data.update(changes)
    return json.dumps(data)


OUTER_CASES = [
    (None, "TEXT_EXTRACT", "OUTPUT_TEXT_MISSING"),
    ("{" + MARKER, "JSON_DECODE", "JSON_DECODE_FAILURE"),
    (json.dumps({"outcome": "OUTPUT"}), "OUTPUT_EXTRACT", "STRUCTURED_OUTPUT_MISSING"),
    (json.dumps({"sections": []}), "SCHEMA_VALIDATE", "REQUIRED_FIELD_MISSING"),
    (altered(extra=MARKER), "SCHEMA_VALIDATE", "SCHEMA_VALIDATION_FAILURE"),
    (altered(warnings=MARKER), "SCHEMA_VALIDATE", "TYPE_MISMATCH"),
    (altered(outcome=MARKER), "SCHEMA_VALIDATE", "ENUM_INVALID"),
    (altered(sections=[]), "SCHEMA_VALIDATE", "CARDINALITY_INVALID"),
    (altered(sections=[{"code": "Objectifs"}]), "TEXT_EXTRACT", "OUTPUT_TEXT_MISSING"),
    (altered(sections=[{"text": MARKER}]), "SCHEMA_VALIDATE", "REQUIRED_FIELD_MISSING"),
    (altered(warnings=[{"code": "X", "message": MARKER}] * 17),
     "SCHEMA_VALIDATE", "CARDINALITY_INVALID"),
]


@pytest.mark.parametrize(("text", "stage", "code"), OUTER_CASES,
                         ids=[f"outer-{i:02}" for i in range(len(OUTER_CASES))])
def test_outer_failure_classification_preserves_original_result(text, stage, code):
    response = OpenAIResponsesResponse(status=OpenAIResponseStatus.COMPLETED, output_text=text)
    trace = ParseDiagnostic()
    assert mapped(outer, response, trace) == mapped(historical(ADAPTER), response)
    assert trace.snapshot() == {"parse_stage": stage, "parse_code": code,
        "parse_status": "FAILED", "schema_target": "PREPARE_SUPPLEMENTS_V1"}
    assert MARKER not in repr(trace.snapshot())


@pytest.mark.parametrize("status", tuple(OpenAIResponseStatus))
@pytest.mark.parametrize("text", [_payload(), _payload(outcome="INSUFFICIENT_EVIDENCE",
    sections=[], uncertainties=[{"code": "GAP", "message": "Synthetic gap"}])])
def test_nominal_refusal_incomplete_and_failed_provider_semantics_unchanged(status, text):
    response = OpenAIResponsesResponse(status=status, output_text=text)
    assert mapped(outer, response, ParseDiagnostic()) == mapped(historical(ADAPTER), response)


def test_invalid_envelope_is_classified_without_changing_exception():
    response = SimpleNamespace(status=None)
    trace = ParseDiagnostic()
    assert mapped(outer, response, trace) == mapped(historical(ADAPTER), response)
    assert trace.snapshot()["parse_stage"] == "ENVELOPE"
    assert trace.snapshot()["parse_code"] == "RESPONSE_ENVELOPE_INVALID"


@pytest.mark.parametrize(("symbol", "error", "stage", "code"), [
    ("GenerationPortResult", ValueError, "DOMAIN_MAP", "DOMAIN_MAPPING_FAILURE"),
    ("_sections", RuntimeError, "SCHEMA_VALIDATE", "UNCLASSIFIED_PARSE_FAILURE"),
])
def test_known_mapping_and_unexpected_exceptions_are_not_string_inspected(monkeypatch, symbol, error, stage, code):
    before = historical(ADAPTER)
    def fail(*args, **kwargs):
        raise error(MARKER)
    monkeypatch.setattr(before, symbol, fail)
    monkeypatch.setattr(outer, symbol, fail)
    trace = ParseDiagnostic()
    response = OpenAIResponsesResponse(status=OpenAIResponseStatus.COMPLETED, output_text=_payload())
    assert mapped(outer, response, trace) == mapped(before, response)
    assert trace.snapshot()["parse_code"] == code
    assert trace.snapshot()["parse_stage"] == stage
    assert MARKER not in repr(trace.snapshot())


INNER_CASES = [
    ({}, "OUTPUT_EXTRACT", "STRUCTURED_OUTPUT_MISSING"),
    ({"sections": []}, "OUTPUT_EXTRACT", "TYPE_MISMATCH"),
    ({"sections": {}}, "OUTPUT_EXTRACT", "REQUIRED_FIELD_MISSING"),
    ({"sections": {"R3_RESULT_JSON": "{}", MARKER: 1}}, "OUTPUT_EXTRACT", "SCHEMA_VALIDATION_FAILURE"),
    ({"sections": {"R3_RESULT_JSON": 1}}, "TEXT_EXTRACT", "TYPE_MISMATCH"),
    ({"sections": {"R3_RESULT_JSON": "x" * (128 * 1024 + 1)}}, "TEXT_EXTRACT", "CARDINALITY_INVALID"),
    ({"sections": {"R3_RESULT_JSON": "{" + MARKER}}, "JSON_DECODE", "JSON_DECODE_FAILURE"),
    ({"sections": {"R3_RESULT_JSON": '{"x":1,"x":2}'}}, "JSON_DECODE", "SCHEMA_VALIDATION_FAILURE"),
    ({"sections": {"R3_RESULT_JSON": '{"x":NaN}'}}, "JSON_DECODE", "SCHEMA_VALIDATION_FAILURE"),
    ({"sections": {"R3_RESULT_JSON": "[" * 18 + "0" + "]" * 18}}, "SCHEMA_VALIDATE", "CARDINALITY_INVALID"),
    ({"sections": {"R3_RESULT_JSON": "[]"}}, "DOMAIN_MAP", "DOMAIN_MAPPING_FAILURE"),
]


@pytest.mark.parametrize(("payload", "stage", "code"), INNER_CASES,
                         ids=[f"inner-{i:02}" for i in range(len(INNER_CASES))])
def test_inner_failure_classification_preserves_original_result(payload, stage, code):
    before = historical("backend/adapters/outbound/generation/assessment_revision.py")
    trace = ParseDiagnostic()
    assert outcome(inner.parse_revision_result, payload, diagnostic=trace) == outcome(
        before.parse_revision_result, payload)
    assert trace.snapshot()["parse_status"] == "FAILED"
    assert trace.snapshot()["parse_stage"] == stage
    assert trace.snapshot()["parse_code"] == code
    assert MARKER not in repr(trace.snapshot())


def test_inner_nominal_complete_and_no_shared_trace():
    trace = ParseDiagnostic()
    assert inner.parse_revision_result({"sections": {"R3_RESULT_JSON": '{"synthetic":true}'}},
                                       diagnostic=trace) == {"synthetic": True}
    assert trace.snapshot()["parse_status"] == "COMPLETED"
    assert trace.snapshot()["parse_stage"] == "DOMAIN_MAP"
    assert trace.snapshot()["parse_code"] is None
    assert ParseDiagnostic().snapshot()["parse_status"] == "UNKNOWN"


def test_closed_schema_first_failure_and_unexpected_exception_privacy():
    assert len(ParseStage) == 6 and len(ParseCode) == 16 and len(ParseStatus) == 4
    trace = ParseDiagnostic()
    with pytest.raises(RuntimeError):
        with trace.capture():
            trace.begin(ParseStage.JSON_DECODE)
            trace.fail(ParseCode.JSON_DECODE_FAILURE)
            trace.begin(ParseStage.DOMAIN_MAP)
            raise RuntimeError(MARKER)
    saved = trace.snapshot()
    assert saved["parse_stage"] == "JSON_DECODE"
    assert saved["parse_code"] == "JSON_DECODE_FAILURE"
    saved["parse_code"] = MARKER
    assert MARKER not in repr(trace.snapshot())
    with pytest.raises(TypeError, match="PARSE_CODE_CLOSED"):
        trace.fail(MARKER)
    with pytest.raises(TypeError, match="PARSE_STAGE_CLOSED"):
        trace.begin(MARKER)
    assert not hasattr(trace, "__dict__")


def test_generate_preflight_resets_diagnostic_without_credential_or_dispatch():
    from tests.unit.test_openai_generation_adapter import _adapter
    adapter, transport, factory = _adapter()
    def stop(request):
        raise RuntimeError("SYNTHETIC_PREFLIGHT_STOP")
    adapter.bind_conversation_execution(before_request=stop, on_dispatch=lambda: None,
        on_response=lambda response: None, on_parsing=lambda status: None)
    adapter._parse_diagnostic = ParseDiagnostic()
    adapter._parse_diagnostic.fail(ParseCode.JSON_DECODE_FAILURE)
    with pytest.raises(RuntimeError, match="SYNTHETIC_PREFLIGHT_STOP"):
        adapter.generate(request=replace(_request(), objective="PREPARE_SUPPLEMENTS",
            output_contract={"contract_id": "R3-TRANSFORMATION-1.0"}))
    assert adapter.parse_diagnostic()["parse_status"] == "UNKNOWN"
    assert transport.calls == factory.build_calls == []


def test_concrete_adapter_private_readback_and_per_request_reset_with_synthetic_transport():
    from tests.unit.test_openai_generation_adapter import _adapter
    adapter, transport, _ = _adapter(OpenAIResponsesResponse(
        status=OpenAIResponseStatus.COMPLETED, output_text="{PRIVATE_SENTINEL"))
    request = replace(_request(), objective="PREPARE_SUPPLEMENTS",
        output_contract={"contract_id": "R3-TRANSFORMATION-1.0"})
    statuses = []
    adapter.bind_conversation_execution(before_request=lambda request: None,
        on_dispatch=lambda: None, on_response=lambda response: None, on_parsing=statuses.append)
    with pytest.raises(outer.GenerationPortError):
        adapter.generate(request=request)
    failed = adapter.parse_diagnostic()
    assert failed["parse_code"] == "JSON_DECODE_FAILURE"
    transport.response = OpenAIResponsesResponse(
        status=OpenAIResponseStatus.COMPLETED, output_text=_payload())
    result = adapter.generate(request=request)
    assert adapter.parse_diagnostic()["parse_status"] == "COMPLETED"
    assert adapter.parse_diagnostic()["parse_code"] is None
    assert "parse_stage" not in repr(result)
    adapter.generate(request=_request())
    assert adapter.parse_diagnostic()["parse_status"] == "UNKNOWN"
    assert statuses == ["FAILED", "SUCCEEDED", "SUCCEEDED"]
    assert len(transport.calls) == 3  # In-memory doubles only; zero SDK/network calls.


@pytest.mark.parametrize("mutation", ["extra", "missing", "same_count"])
def test_patch_inventory_closed_mutants(mutation):
    changed = set(PATCH_PATHS)
    if mutation != "extra":
        changed.remove(ADAPTER)
    if mutation != "missing":
        changed.add("backend/unapproved.py")
    assert patch_violations(ROOT, changed=changed)


@pytest.mark.parametrize("path", PATCH_PATHS)
def test_every_patch_source_mutation_is_rejected(tmp_path, path):
    from tests.support.r3_cap_a01_guard import PATHS as CAP_PATHS
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_prepare_contract_alignment_guard import PATHS

    for name in set(PATCH_PATHS) | set(PATHS) | set(CAP_PATHS) | set(LOCATOR_PATHS) | set(EDITORIAL_PATHS):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    assert patch_violations(tmp_path) == []
    target = tmp_path / path
    target.write_bytes(target.read_bytes() + (b"\nUNAPPROVED = True\n" if path == SELF else b"\n# drift\n"))
    assert patch_violations(tmp_path)


@pytest.mark.parametrize("path", tuple(GUARD_SYMBOLS))
def test_guard_extension_preserves_all_other_ast_nodes_and_exact_successor(path):
    assert_guard_extension(ROOT, path)
    before = subprocess.run(
        ["git", "show", f"{BASELINE}:{path}"], cwd=ROOT, check=True, capture_output=True).stdout
    old, new = ast.parse(before), ast.parse((ROOT / path).read_bytes())
    old_names = {n.name for n in old.body if isinstance(n, ast.FunctionDef)}
    new_names = {n.name for n in new.body if isinstance(n, ast.FunctionDef)}
    assert old_names == new_names


def test_patch_worktree_index_and_historical_guards():
    assert_patch_git_state(ROOT)


def test_staged_source_cannot_hide_behind_clean_working_bytes(monkeypatch):
    from tests.support import r3_parse_observability_guard as oracle
    original = oracle.subprocess.run
    def staged_drift(args, **kwargs):
        if args == ["git", "show", ":" + ADAPTER]:
            return subprocess.CompletedProcess(args, 0, stdout=(ROOT / ADAPTER).read_bytes() + b"\n# staged drift\n")
        return original(args, **kwargs)
    monkeypatch.setattr(oracle.subprocess, "run", staged_drift)
    with pytest.raises(AssertionError):
        assert_patch_git_state(ROOT)


def test_post_identity_table_is_part_of_oracle_fingerprint():
    from tests.support.r3_parse_observability_guard import ORACLE_AST_SHA256, POST, oracle_digest
    raw = (ROOT / SELF).read_bytes()
    changed = raw.replace(POST[ADAPTER].encode(), b"0" * 64)
    assert changed != raw and oracle_digest(changed) != ORACLE_AST_SHA256
