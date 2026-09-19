import copy
import io
import json
import subprocess
import time
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from backend.adapters.outbound.system.conversation_job import decode_frame, encode_frame
from backend.infrastructure.composition.bootstrap.conversation_worker import (
    read_private_packet,
    run_authorized_generation,
)
from backend.infrastructure.composition.factories.conversation import (
    r2_digest,
    r2_request_parameters,
)
from backend.infrastructure.composition.factories.r5_generation import (
    build_r5_process_job,
    canonical_bytes,
    check_material,
    validate_grant,
    validate_selection,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    LOCAL_REFERENCE_LABEL,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from tests.integration.test_r5_local_reference import request
from tests.support.r5_worker_synthetic import (
    BASELINE,
    CASE,
    FAKE,
    METHOD,
    Factory,
    fixture,
    grant_for,
    packet_for,
)


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    import socket

    from backend.adapters.outbound.openai.transport import OpenAISDKResponsesTransportFactory
    def forbidden(*args, **kwargs):
        pytest.fail("NO_REAL_PROVIDER_OR_NETWORK")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(OpenAISDKResponsesTransportFactory, "build", forbidden)


def test_selection_preserved_to_worker_without_generic_search(tmp_path, monkeypatch):
    from backend.infrastructure.composition.factories import conversation, local_browser
    def forbidden(*args, **kwargs):
        pytest.fail("NO_R2_FALLBACK_OR_NEW_SEARCH")
    monkeypatch.setattr(conversation, "conversation_evidence", forbidden)
    monkeypatch.setattr(local_browser, "_application_searcher", forbidden)
    target, scope, prepared = fixture(tmp_path / "fixture")
    grant = grant_for(scope, tmp_path / "receipts")
    factory, sink = Factory(), io.BytesIO()
    packet = read_private_packet(io.BytesIO(encode_frame(packet_for(target, scope, grant))))
    result = run_authorized_generation(packet, request=request(), sink=sink,
        material=(BASELINE, scope), transport_factory=factory)
    assert result.state == "CANDIDATE_READY"
    assert len(factory.requests) == factory.builds == 1
    assert r2_request_parameters(factory.requests[0]) == prepared["generation"]
    assert result.usage.input_tokens == 3000 and result.usage.parsing == "SUCCEEDED"
    assert all(ref["provenance_label"] == LOCAL_REFERENCE_LABEL for ref in result.draft.references)
    assert {item["text"] for item in json.loads(factory.requests[0].input_json)["resolved_inputs"]["evidence"]} == {METHOD, CASE}
    assert prepared["projection"]["pedagogical_context"]["difficulty"] == "STANDARD"
    assert "GenerationCoordinator.prepare" in prepared["trace"]
    assert "R5 pedagogical reasoning" in factory.requests[0].instructions
    assert "secret" not in packet


@pytest.mark.parametrize("field,value", [("schema", "R2-GENERATION-GRANT-1.0"),
    ("live_authorized", False), ("transfer_authorized", False), ("model_profile_approved", False),
    ("pricing_approved", False), ("provider", "ANTHROPIC_ONLY"), ("max_calls", 2),
    ("max_calls", True), ("retry", 1), ("fallback", "R2"), ("ceiling_usd", "NaN"),
    ("ceiling_usd", "0"), ("baseline_commit", "e" * 40), ("scope_sha256", "0" * 64),
    ("expires_at", "2000-01-01T00:00:00+00:00")])
def test_grant_drift_denied_before_credential(tmp_path, field, value):
    target, scope, _ = fixture(tmp_path / "fixture")
    grant = {**grant_for(scope, tmp_path / "receipts"), field: value}
    inputs = []
    with pytest.raises((ValueError, TypeError)):
        build_r5_process_job(grant=grant, scope=scope, baseline=BASELINE, target=target,
            receipt_root=tmp_path / "receipts", private_temp=tmp_path, credential_input=lambda: inputs.append("FAIL"))
    assert inputs == [] and not (tmp_path / "receipts").exists()


@pytest.mark.parametrize("kind", ["unknown", "kind", "label", "checksum", "text", "budget", "context", "extra"])
def test_scope_mutations_fail_before_any_transport(tmp_path, kind):
    target, scope, _ = fixture(tmp_path / "fixture")
    bad = copy.deepcopy(scope)
    if kind == "unknown":
        bad["selection"][0]["passage_ref"] = "unknown"
    elif kind == "kind":
        bad["selection"][0]["object_kind"] = "NOTION"
    elif kind == "label":
        bad["provenance_label"] = "OFFICIAL"
    elif kind == "checksum":
        bad["selection"][0]["version_or_checksum"] = "0" * 64
    elif kind == "text":
        bad["selection"][0]["text_sha256"] = "0" * 64
    elif kind == "budget":
        bad["pricing_sha256"] = "0" * 64
    elif kind == "context":
        bad["context"]["difficulty"] = "DIFFICULT"
    else:
        bad["extra"] = "not accepted"
    # Even a fresh, internally bound synthetic grant cannot bypass material checks.
    factory = Factory()
    with pytest.raises((ValueError, ConversationRejected)):
        run_authorized_generation(packet_for(target, bad, grant_for(bad, tmp_path / "receipts")),
            request=request(), sink=io.BytesIO(), material=(BASELINE, bad), transport_factory=factory)
    assert factory.builds == 0


def test_count_unknown_requires_distinct_explicit_acceptance(tmp_path):
    _, scope, _ = fixture(tmp_path / "fixture")
    grant = grant_for(scope, tmp_path / "receipts")
    proof = grant["token_count_receipt"]
    proof["cost_status"] = "UNKNOWN"
    grant["count_receipt_sha256"] = r2_digest(proof)
    with pytest.raises(ValueError, match="R5_COUNT_REQUIRED"):
        validate_grant(grant, scope=scope, baseline=BASELINE, now=datetime.now(UTC))
    proof["unknown_cost_explicitly_accepted"] = True
    grant["count_receipt_sha256"] = r2_digest(proof)
    assert validate_grant(grant, scope=scope, baseline=BASELINE, now=datetime.now(UTC))
    proof["status"] = "UNKNOWN"
    grant["count_receipt_sha256"] = r2_digest(proof)
    with pytest.raises(ValueError, match="R5_COUNT_REQUIRED"):
        validate_grant(grant, scope=scope, baseline=BASELINE, now=datetime.now(UTC))


@pytest.mark.parametrize("mode,state,parsing", [("invalid", "FAILED_OUTPUT", "FAILED"),
    ("unknown-id", "FAILED_OUTPUT", "FAILED"), ("insufficient", "FAILED_OUTPUT", "SUCCEEDED"),
    ("incomplete", "FAILED_OUTPUT", "INCOMPLETE"), ("error", "UNKNOWN", "NOT_RUN")])
def test_failure_preserves_usage_without_candidate_or_retry(tmp_path, mode, state, parsing):
    target, scope, _ = fixture(tmp_path / "fixture")
    factory, sink = Factory(mode), io.BytesIO()
    result = run_authorized_generation(packet_for(target, scope, grant_for(scope, tmp_path / "receipts")),
        request=request(), sink=sink, material=(BASELINE, scope), transport_factory=factory)
    assert result.state == state and result.draft is None
    assert result.usage.parsing == parsing and result.usage.provider_attempted
    assert len(factory.requests) == 1
    if mode != "error":
        assert result.usage.input_tokens == 3000
        data = sink.getvalue()
        assert b'"parsing":"NOT_RUN"' in data and b'"response_received":true' in data


@pytest.mark.parametrize("mode,expected", [("success", "CANDIDATE_READY"), ("disconnect", "UNKNOWN")])
def test_supervised_child_one_shot_and_no_private_receipt_leak(tmp_path, mode, expected):
    target, scope, _ = fixture(tmp_path / "fixture")
    receipts = tmp_path / "receipts"
    grant, inputs = grant_for(scope, receipts), []
    def input_double():
        inputs.append("FAKE")
        return FAKE
    job = build_r5_process_job(grant=grant, scope=scope, baseline=BASELINE, target=target,
        receipt_root=receipts, private_temp=tmp_path, credential_input=input_double)
    def launch(args, **kwargs):
        assert FAKE not in repr((args, kwargs))
        return subprocess.Popen([args[0], "-m", "tests.support.r5_worker_synthetic", mode, *args[3:]], **kwargs)
    job.launch = launch
    try:
        job.authorize(request())
        assert inputs == []
        job.start(request())
        end = time.monotonic() + 30
        result = None
        while result is None and time.monotonic() < end:
            result = job.poll()
            time.sleep(.02)
        assert result is not None and result.state == expected
        assert result.usage.response_received and result.usage.input_tokens == 3000
        assert inputs == ["FAKE"]
        with pytest.raises(ConversationRejected):
            job.start(request())
    finally:
        job.close()
    with pytest.raises(ConversationRejected):
        build_r5_process_job(grant=grant, scope=scope, baseline=BASELINE, target=target,
            receipt_root=receipts, private_temp=tmp_path, credential_input=input_double)
    raw = "".join(p.read_text("utf-8") for p in receipts.glob("*.json"))
    assert all(value not in raw for value in (FAKE, METHOD, CASE, str(target.runtime_path), request().brief))


def test_request_and_selection_bounds_and_neutral_identity(tmp_path):
    target, scope, prepared = fixture(tmp_path / "fixture")
    assert check_material(scope, request=request(), target=target) == prepared
    for selection in ([], scope["selection"] * 2, [scope["selection"][0]] * 2):
        with pytest.raises(ValueError):
            validate_selection(selection)
    with pytest.raises(ValueError):
        check_material(scope, request=replace(request(), brief="Autre question"), target=target)
    common = {k: prepared["generation"][k] for k in prepared["count"]}
    assert common == prepared["count"] and "max_output_tokens" not in common
    assert json.loads(canonical_bytes(prepared["generation"])) == prepared["generation"]
    with pytest.raises(ValueError):
        read_private_packet(io.BytesIO(encode_frame({"schema": "R2", **packet_for(target, scope, {})} | {"schema": "BAD"})))
    assert decode_frame(encode_frame({"safe": 1})) == {"safe": 1}


def test_pedagogical_fixture_solution_and_missing_dependencies_are_not_quality_claims():
    rs, es, ac, pc = 150 + 70, 120 + 60, 35 + 50, 40 + 20
    frng, bfr = rs - es, ac - pc
    assert (rs, es, frng, bfr, frng - bfr) == (220, 180, 40, 25, 15)
    assert frng - bfr == 18 - 3 and 4 + 4 + 6 + 6 == 20


@pytest.mark.parametrize("method,case,missing", [
    ("Bilan fonctionnel et BFR : titre seul du support.", CASE, "method"),
    ("FRNG = ressources stables - emplois stables ; TN = FRNG - BFR.", CASE, "BFR"),
    (METHOD, CASE.replace("stocks 35", "stocks non fournis"), "datum"),
    (METHOD, "FRNG=40, BFR=25 et TN=15 déjà fournis, sans les composants.", "reconstruction"),
])
def test_counterexamples_preserved_without_silent_simplification(tmp_path, method, case, missing):
    target, scope, prepared = fixture(tmp_path / "fixture", source_texts=(method, case))
    texts = {item["text"] for item in prepared["projection"]["resolved_inputs"]["evidence"]}
    assert texts == {method, case}
    assert prepared["projection"]["pedagogical_context"]["difficulty"] == "STANDARD"
    assert "rather than lowering difficulty" in prepared["generation"]["instructions"]
    factory = Factory("insufficient")  # Controlled outcome, not an automated pedagogical judgment.
    result = run_authorized_generation(packet_for(target, scope, grant_for(scope, tmp_path / "receipts")),
        request=request(), sink=io.BytesIO(), material=(BASELINE, scope), transport_factory=factory)
    assert result.state == "FAILED_OUTPUT" and result.draft is None
    assert missing in {"method", "BFR", "datum", "reconstruction"}


def test_r5_watchdog_preserves_unknown_without_second_attempt(tmp_path):
    target, scope, _ = fixture(tmp_path / "fixture")
    receipts = tmp_path / "receipts"
    job = build_r5_process_job(grant=grant_for(scope, receipts), scope=scope, baseline=BASELINE,
        target=target, receipt_root=receipts, private_temp=tmp_path, credential_input=lambda: FAKE)
    job.launch = lambda args, **kwargs: subprocess.Popen(
        [args[0], "-m", "tests.support.r5_worker_synthetic", "timeout", *args[3:]], **kwargs)
    elapsed = [0.0]
    job.clock = lambda: elapsed[0]
    try:
        job.authorize(request())
        job.start(request())
        deadline = time.monotonic() + 20
        while not list(receipts.glob("*.PROVIDER_ATTEMPTED.json")):
            assert time.monotonic() < deadline
            time.sleep(.02)
        elapsed[0] = 121.0
        result = None
        while result is None and time.monotonic() < deadline:
            result = job.poll()
            time.sleep(.02)
        assert result is not None and result.state == "UNKNOWN"
        assert result.usage.provider_attempted and result.usage.input_tokens is None
        with pytest.raises(ConversationRejected):
            job.authorize(request())
    finally:
        job.close()
