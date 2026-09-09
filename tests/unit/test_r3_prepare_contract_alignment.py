"""Strict producer contract and closed successor mutations, synthetic only."""
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from backend.adapters.outbound.generation.assessment_revision import (
    AssessmentRevisionAdapter,
    parse_revision_result,
)
from backend.adapters.outbound.generation.openai.adapter import _map_response
from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.adapters.outbound.generation.openai.prepare_contract import (
    FIELDS,
    is_prepare_request,
    normalized_prepare_text,
    prepare_output_schema,
)
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.adapters.outbound.openai.schema import lower_openai_strict_schema
from backend.agent_runtime.agents.generation import (
    GenerationOperation,
    GenerationPortError,
    GenerationPortResultStatus,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    PREPARE,
    AssessmentRevisionRequest,
)
from tests.support.r3_fakes import FakeR3Generation
from tests.support.r3_parse_observability_guard import PATCH_PATHS, patch_violations
from tests.support.r3_prepare_contract_alignment_guard import (
    BASELINE,
    PATHS,
    POST,
    SELF,
    assert_successor_git_state,
    assert_successor_scope,
    oracle_digest,
    successor_violations,
)
from tests.support.r3_synthetic import PROD, V1, production, subject, supplements
from tests.unit.test_openai_generation_adapter import _model, _provider

ROOT = Path(__file__).resolve().parents[2]


def prepare_request():
    prod = production()
    port = FakeR3Generation()
    AssessmentRevisionAdapter(port).propose(AssessmentRevisionRequest(
        PREPARE, PROD, V1, subject(), prod.data["pedagogical_context"],
        tuple(prod.data["references"])))
    return port.calls[0]


def test_actual_producer_root_exactly_matches_five_domain_fields():
    request = prepare_request()
    assert is_prepare_request(request)
    emitted = build_openai_request(request=request, model_profile=_model())
    schema = emitted.output_schema
    assert tuple(schema["properties"]) == FIELDS
    assert schema["required"] == list(FIELDS)
    assert schema["additionalProperties"] is False
    assert schema == lower_openai_strict_schema(prepare_output_schema())
    assert "R3_RESULT_JSON" not in schema["properties"]
    assert "directly" in emitted.instructions
    def closed(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            for child in node.values():
                closed(child)
        elif isinstance(node, list):
            for child in node:
                closed(child)
    closed(schema)


@pytest.mark.parametrize("field", FIELDS)
def test_each_missing_root_field_rejected_without_defaults(field):
    data = supplements()
    del data[field]
    trace = ParseDiagnostic()
    with trace.capture(), pytest.raises(GenerationPortError):
        normalized_prepare_text(json.dumps(data), trace)
    assert trace.snapshot()["parse_code"] == "REQUIRED_FIELD_MISSING"


@pytest.mark.parametrize("fault", [
    "extra", "wrapper", "legacy", "root_array", "nested_extra", "nested_missing",
    "bool_offset", "wrong_questions_type", "numeric_money", "oversized_array",
    "bad_enum", "expression_depth", "expression_extra", "float_integer", "duplicate",
    "nan", "invalid_json", "oversized_text", "fences", "none", "unicode_surrogate",
])
def test_bad_provider_data_is_never_repaired(fault):
    data = supplements()
    if fault == "extra":
        data["extra"] = "PRIVATE_SENTINEL"
    elif fault == "wrapper":
        data = {"result": data}
    elif fault == "legacy":
        data = {"outcome": "OUTPUT", "sections": [{"code": "R3_RESULT_JSON",
                "text": json.dumps(data)}], "warnings": [], "uncertainties": []}
    elif fault == "root_array":
        data = [data]
    elif fault == "nested_extra":
        data["questions"][0]["extra"] = True
    elif fault == "nested_missing":
        del data["correction"]["version_ref"]
    elif fault == "bool_offset":
        data["questions"][0]["locator"]["start"] = True
    elif fault == "wrong_questions_type":
        data["questions"] = {}
    elif fault == "numeric_money":
        data["marking"]["total_points"] = 20
    elif fault == "oversized_array":
        data["limitations"] = ["x"] * 17
    elif fault == "bad_enum":
        data["case_data"]["source_scale"] = "UNKNOWN"
    elif fault == "expression_depth":
        expression = {"ref": "totals.stable_resources"}
        for _ in range(4):
            expression = {"op": "ADD", "operands": [expression, {"ref": "totals.stable_uses"}]}
        data["correction"]["answers"][0]["calculations"][0]["expression"] = expression
    elif fault == "expression_extra":
        data["correction"]["answers"][0]["calculations"][0]["expression"]["extra"] = True
    elif fault == "float_integer":
        data["marking"]["dossiers"][0]["duration_minutes"] = 20.0
    text = json.dumps(data)
    text = {
        "duplicate": '{"questions":[],' + text[1:],
        "nan": '{"questions":NaN}',
        "invalid_json": "{PRIVATE_SENTINEL",
        "oversized_text": " " * (128 * 1024 + 1),
        "fences": "```json\n" + text + "\n```",
        "none": None,
        "unicode_surrogate": '"\\ud800"',
    }.get(fault, text)
    trace = ParseDiagnostic()
    with pytest.raises(GenerationPortError), trace.capture():
        normalized_prepare_text(text, trace)
    assert trace.snapshot()["parse_status"] == "FAILED"
    assert "PRIVATE_SENTINEL" not in repr(trace.snapshot())


@pytest.mark.parametrize("scale", ["EUR", "kEUR"])
def test_normalization_preserves_every_field_and_internal_parser(scale):
    original = supplements(scale)
    normalized = normalized_prepare_text(json.dumps(original), ParseDiagnostic())
    assert json.loads(normalized) == original
    assert parse_revision_result({"sections": {"R3_RESULT_JSON": normalized}}) == original
    assert original == supplements(scale)


@pytest.mark.parametrize("status", list(OpenAIResponseStatus))
def test_provider_status_cannot_be_upgraded(status):
    response = OpenAIResponsesResponse(status=status, output_text=json.dumps(supplements()))
    kwargs = dict(request=prepare_request(), response=response,
                  provider_profile=_provider(), model_profile=_model(), diagnostic=ParseDiagnostic())
    if status is OpenAIResponseStatus.FAILED:
        with pytest.raises(GenerationPortError):
            _map_response(**kwargs)
    else:
        result = _map_response(**kwargs)
        assert result.status is {
            OpenAIResponseStatus.COMPLETED: GenerationPortResultStatus.SUCCEEDED,
            OpenAIResponseStatus.INCOMPLETE: GenerationPortResultStatus.PARTIAL,
            OpenAIResponseStatus.REFUSED: GenerationPortResultStatus.REFUSED,
        }[status]
        if status is OpenAIResponseStatus.COMPLETED:
            assert parse_revision_result(result.structured_payload) == supplements()
        if status is OpenAIResponseStatus.REFUSED:
            assert not result.structured_payload


@pytest.mark.parametrize("override", [
    {"operation": GenerationOperation.GENERATE},
    {"objective": "HARDEN_DOSSIER_3"},
    {"production_kind": "lesson_plan"},
    {"output_contract": {"contract_id": "OTHER"}},
    {"expected_sections": ("OTHER",)},
])
def test_selection_is_exact_and_other_requests_byte_equivalent(override):
    request = replace(prepare_request(), **override)
    assert not is_prepare_request(request)
    path = "backend/adapters/outbound/generation/openai/mapping.py"
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    historical = ModuleType("historical_mapping")
    exec(compile(raw, "<historical-mapping>", "exec"), historical.__dict__)
    assert build_openai_request(request=request, model_profile=_model()) == (
        historical.build_openai_request(request=request, model_profile=_model()))


def copied_sources(tmp_path):
    for path in set(PATHS) | set(PATCH_PATHS):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())


@pytest.mark.parametrize("path", PATHS)
def test_every_successor_source_mutation_is_rejected(tmp_path, path):
    copied_sources(tmp_path)
    assert successor_violations(tmp_path) == []
    target = tmp_path / path
    target.write_bytes(target.read_bytes() + (
        b"\nUNAPPROVED = True\n" if path == SELF else b"\n# unapproved drift\n"))
    assert successor_violations(tmp_path)
    assert patch_violations(tmp_path)


@pytest.mark.parametrize("fault", ["extra", "missing", "same_count"])
def test_closed_successor_inventory_rejects_mutants(fault):
    changed = set(PATHS)
    if fault != "extra":
        changed.remove(PATHS[0])
    if fault != "missing":
        changed.add("backend/unapproved.py")
    assert successor_violations(ROOT, changed=changed)


@pytest.mark.parametrize("path", PATHS)
def test_index_mutation_is_independently_rejected(monkeypatch, path):
    original = subprocess.run
    def changed_index(args, **kwargs):
        if args == ["git", "show", ":" + path]:
            return subprocess.CompletedProcess(args, 0, stdout=(ROOT / path).read_bytes()
                + (b"\nUNAPPROVED = True\n" if path == SELF else b"\n# index drift\n"))
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", changed_index)
    with pytest.raises(AssertionError):
        assert_successor_git_state(ROOT)


def test_frozen_post_table_and_unapproved_ast_are_authenticated():
    from tests.support.r3_prepare_contract_alignment_guard import ORACLE_AST_SHA256

    raw = (ROOT / SELF).read_bytes()
    mutant = raw.replace(next(iter(POST.values())).encode(), b"0" * 64)
    assert raw != mutant and oracle_digest(mutant) != ORACLE_AST_SHA256
    assert_successor_scope(ROOT)
    assert_successor_git_state(ROOT)
