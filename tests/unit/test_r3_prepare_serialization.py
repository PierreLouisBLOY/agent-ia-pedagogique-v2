"""Contextual R3 serialization and exact historical R2/guard non-regression."""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.adapters.outbound.openai.contracts import OpenAIReasoningEffort, OpenAIResponsesRequest
from backend.infrastructure.composition.factories.conversation import (
    conversation_provider_configuration,
    r2_count_handoff,
    r2_request_parameters,
)
from backend.infrastructure.composition.factories.r3_prepare_serialization import (
    r3_prepare_request_parameters,
)
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ProviderInvocationLimits,
    ProviderWorkloadKind,
)
from tests.support.r3_serializer_8192_guard import (
    BASELINE,
    PATHS,
    POST,
    PRE,
    R2_SOURCE,
    SELF,
    assert_git_state,
    assert_scope,
    digest,
    oracle_digest,
    source_matches,
    violations,
)
from tests.unit.test_openai_conversation_mapping import model as r2_model
from tests.unit.test_openai_conversation_mapping import request as r2_request
from tests.unit.test_r3_prepare_contract_alignment import prepare_request

ROOT = Path(__file__).resolve().parents[2]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def profile(bound=8192):
    return replace(conversation_provider_configuration().model_profiles[0],
        context_limits=ModelContextLimits(1_050_000, 32768, bound),
        invocation_limits=ProviderInvocationLimits(1, 90000, 32768, bound, 32768 + bound))


def wire(bound=8192):
    return replace(build_openai_request(request=prepare_request(), model_profile=profile(bound)),
                   service_tier="default", reasoning_effort=OpenAIReasoningEffort.LOW)


def serialize(request=None, selected=None, operation="PREPARE_SUPPLEMENTS"):
    return r3_prepare_request_parameters(
        request if request is not None else wire(),
        model_profile=selected if selected is not None else profile(), operation=operation)


def test_r2_historical_canonical_bytes_and_serialization_behavior():
    raw = subprocess.run(["git", "show", f"{BASELINE}:{R2_SOURCE}"], cwd=ROOT,
                         check=True, capture_output=True).stdout
    assert raw == (ROOT / R2_SOURCE).read_bytes()
    tree = ast.parse(raw)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "r2_request_parameters")
    namespace = {"OpenAIResponsesRequest": OpenAIResponsesRequest}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<r2-historical-serializer>", "exec"), namespace)
    technical = build_openai_request(request=r2_request(), model_profile=r2_model())
    old = namespace["r2_request_parameters"](technical)
    current = r2_request_parameters(technical)
    assert canonical(old) == canonical(current)
    assert list(old) == list(current)
    assert len(canonical(current)) == 3251
    assert hashlib.sha256(canonical(current)).hexdigest() == (
        "c3ce923d5b8ee48157e189be9a3015fea753293026d714b07fbb5e0054cd43b3")
    assert r2_count_handoff(current)["count_request_sha256"] == (
        "4a5a2388a2a594c02030ecd5394d74de1d56371095fd85938734138feeb0f4cc")
    for output in (1, 4095, 4097, 8192, 8193):
        for mapper in (namespace["r2_request_parameters"], r2_request_parameters):
            with pytest.raises(ValueError, match="R2_REQUEST_REJECTED"):
                mapper(replace(technical, max_output_tokens=output))


@pytest.mark.parametrize("bound", [4096, 8192])
def test_exact_profile_reservation_is_serialized(bound):
    request = wire(bound)
    result = serialize(request, profile(bound))
    assert result["max_output_tokens"] == bound
    assert request.max_output_tokens == bound
    assert profile(bound).invocation_limits.max_total_tokens == 32768 + bound
    if bound == 4096:
        assert canonical(result) == canonical(r2_request_parameters(request))
        assert list(result) == list(r2_request_parameters(request))


def test_no_other_semantic_field_changes_and_no_count_authority():
    old = serialize(wire(4096), profile(4096))
    new = serialize()
    assert [key for key in old if old[key] != new[key]] == ["max_output_tokens"]
    assert new["reasoning"] == {"effort": "low"}
    assert new["model"] == "gpt-5.6-terra"
    assert r2_count_handoff(old)["count_request_sha256"] == r2_count_handoff(new)["count_request_sha256"]
    assert r2_count_handoff(old)["generation_request_sha256"] != r2_count_handoff(new)["generation_request_sha256"]


@pytest.mark.parametrize("output", [0, -1, True, 8193, 9000, "8192", 8192.0])
def test_invalid_or_over_bound_output_fails_closed(output):
    with pytest.raises(ValueError, match="R3_PREPARE_PROFILE_LIMIT_REJECTED"):
        serialize(replace(wire(), max_output_tokens=output))


def test_4096_profile_cannot_authorize_8192_request():
    with pytest.raises(ValueError, match="R3_PREPARE_PROFILE_LIMIT_REJECTED"):
        serialize(wire(), profile(4096))


@pytest.mark.parametrize("fault", [
    "model", "disabled", "structured", "workload", "context_output", "input",
    "output", "missing_output", "missing_input", "missing_total", "total",
    "attempts", "timeout", "arbitrary_higher_profile",
])
def test_incoherent_or_unapproved_profile_rejected(fault):
    p = profile()
    changes = {
        "model": {"model_code": ModelCode("other")},
        "disabled": {"enabled": False}, "structured": {"structured_output_required": False},
        "workload": {"supported_workloads": (ProviderWorkloadKind.REVIEW,)},
        "context_output": {"context_limits": ModelContextLimits(1_050_000, 32768, 4096)},
        "input": {"invocation_limits": ProviderInvocationLimits(1, 90000, 32767, 8192, 40960)},
        "output": {"invocation_limits": ProviderInvocationLimits(1, 90000, 32768, 4096, 40960)},
        "missing_output": {"invocation_limits": ProviderInvocationLimits(1, 90000, 32768, None, 40960)},
        "missing_input": {"invocation_limits": ProviderInvocationLimits(1, 90000, None, 8192, 40960)},
        "missing_total": {"invocation_limits": ProviderInvocationLimits(1, 90000, 32768, 8192, None)},
        "total": {"invocation_limits": ProviderInvocationLimits(1, 90000, 32768, 8192, 40961)},
        "attempts": {"invocation_limits": ProviderInvocationLimits(2, 90000, 32768, 8192, 40960)},
        "timeout": {"invocation_limits": ProviderInvocationLimits(1, 90001, 32768, 8192, 40960)},
        "arbitrary_higher_profile": {
            "context_limits": ModelContextLimits(1_050_000, 32768, 8193),
            "invocation_limits": ProviderInvocationLimits(1, 90000, 32768, 8193, 40961)},
    }
    with pytest.raises(ValueError, match="R3_PREPARE_PROFILE_LIMIT_REJECTED"):
        serialize(wire(), replace(p, **changes[fault]))


@pytest.mark.parametrize("delta", [
    {"model": "other"}, {"reasoning_effort": OpenAIReasoningEffort.HIGH},
    {"service_tier": "flex"}, {"service_tier": None},
])
def test_other_technical_profile_drift_rejected(delta):
    with pytest.raises(ValueError, match="R3_PREPARE_PROFILE_LIMIT_REJECTED"):
        serialize(replace(wire(), **delta))


@pytest.mark.parametrize("fault", ["operation", "input_operation", "objective", "schema",
                                  "schema_name", "invalid_json", "non_object", "r2"])
def test_serializer_is_only_for_prepare(fault):
    request, operation = wire(), "PREPARE_SUPPLEMENTS"
    if fault == "operation":
        operation = "HARDEN_DOSSIER_3"
    elif fault in {"input_operation", "objective"}:
        data = json.loads(request.input_json)
        data["operation" if fault == "input_operation" else "objective"] = "UNAUTHORIZED"
        request = replace(request, input_json=json.dumps(data))
    elif fault == "schema":
        request = replace(request, output_schema={})
    elif fault == "schema_name":
        request = replace(request, schema_name="other")
    elif fault == "invalid_json":
        request = replace(request, input_json="{")
    elif fault == "non_object":
        request = replace(request, input_json="[]")
    else:
        request = build_openai_request(request=r2_request(), model_profile=r2_model())
    with pytest.raises(ValueError, match="R3_PREPARE_"):
        serialize(request, operation=operation)


@pytest.mark.usefixtures("historical_guard_sources")
def test_successor_scope_and_working_index_and_history():
    assert_scope(ROOT)
    assert_git_state(ROOT)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.usefixtures("historical_guard_sources")
def test_each_successor_source_mutation_is_rejected(tmp_path, path):
    from tests.support.r3_cap_a01_guard import PATHS as CAP_PATHS
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS

    for item in set(PATHS) | set(CAP_PATHS) | set(LOCATOR_PATHS) | set(EDITORIAL_PATHS) | set(PORTABLE_PATHS) | set(D3_PATHS):
        target = tmp_path / item
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / item).read_bytes())
    assert violations(tmp_path) == []
    target = tmp_path / path
    target.write_bytes(target.read_bytes() + b"\nUNAPPROVED_SERIALIZER_MUTATION = True\n")
    assert violations(tmp_path)
    if path in PRE:
        assert not source_matches(tmp_path, path, PRE[path])


@pytest.mark.parametrize("fault", ["missing", "extra", "same_count"])
def test_closed_inventory_rejects_mutation(fault):
    changed = set(PATHS)
    if fault != "extra":
        changed.remove(PATHS[0])
    if fault != "missing":
        changed.add("backend/unapproved_serializer.py")
    assert violations(ROOT, changed=changed)


@pytest.mark.parametrize("path", PATHS)
def test_index_drift_is_rejected_independently(monkeypatch, path):
    original = subprocess.run
    def mutate(args, **kwargs):
        if args == ["git", "show", ":" + path]:
            return subprocess.CompletedProcess(args, 0, stdout=(ROOT / path).read_bytes()
                + b"\nUNAPPROVED_INDEX_MUTATION = True\n")
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", mutate)
    with pytest.raises(AssertionError):
        assert_git_state(ROOT)


def test_oracle_table_tampering_is_rejected():
    from tests.support.r3_cap_a01_guard import source_matches as cap_source_matches
    from tests.support.r3_serializer_8192_guard import ORACLE_AST_SHA256

    raw = (ROOT / SELF).read_bytes()
    altered = raw.replace(next(iter(POST.values())).encode(), b"0" * 64)
    assert altered != raw and oracle_digest(altered) != ORACLE_AST_SHA256
    for path, historical in PRE.items():
        assert source_matches(ROOT, path, historical)
        assert not source_matches(ROOT, path, "0" * 64)
        assert (digest((ROOT / path).read_bytes()) == POST[path]
                or cap_source_matches(ROOT, path, POST[path]))
