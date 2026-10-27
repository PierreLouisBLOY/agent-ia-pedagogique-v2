"""Declared failure doubles only; temporary synthetic receipts, no real provider."""
import errno
import json
import socket
import traceback
from dataclasses import replace

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_diagnostic import (
    MAX_FAILURE_DIAGNOSTIC_BYTES,
    failure_code,
    validate_failure_document,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.openai.contracts import (
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.infrastructure.filesystem import LocalFileSecurityCode, LocalFileSecurityError
from tests.unit.test_p0_normal_generation import synthetic_configuration

CANARY = "SYNTHETIC_PRIVATE_EXCEPTION_AUTHORIZATION_PASSAGE_BODY"


@pytest.fixture(autouse=True)
def forbid_network_and_sdk(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("REAL_PROVIDER_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(
        "backend.adapters.outbound.openai.transport.OpenAISDKResponsesTransportFactory.build", refuse
    )


def configured(tmp_path):
    config, _, _, dispatch, _, _, _, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    adapter.authorize(request=dispatch)
    return adapter, dispatch, transport


def diagnostic(adapter):
    proof = adapter.receipt.read("DISPATCH")["preflight"]
    return adapter.receipt.read_failure_diagnostic(grant=adapter.grant, preflight=proof)


def assert_still_used(adapter, dispatch, transport):
    before = {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")}
    calls = transport.calls
    with pytest.raises(ValueError, match="ALREADY_USED"):
        adapter.authorize(request=dispatch)
    with pytest.raises(ValueError, match="ALREADY_USED"):
        adapter.generate(request=dispatch)
    assert transport.calls == calls
    assert {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")} == before


@pytest.mark.parametrize("code", list(OpenAITransportErrorCode))
def test_transport_enum_retained_unknown_and_no_second_send(tmp_path, code, capsys, caplog):
    adapter, dispatch, transport = configured(tmp_path)
    error = OpenAITransportError(code)
    error.args = (CANARY,)
    transport.failure = error
    with pytest.raises(ValueError, match="^P0_NORMAL_OUTCOME_UNKNOWN$") as caught:
        adapter.generate(request=dispatch)
    doc = diagnostic(adapter)
    assert doc["stage"] == "TRANSPORT_CREATE"
    assert (doc["code_source"], doc["technical_code"]) == ("OPENAI_TRANSPORT", code.value)
    assert doc["outcome_marker"] == "UNKNOWN" and doc["marker_recorded"] is True
    assert doc["provider_attempts"] == transport.calls == 1
    assert adapter.receipt.exists("UNKNOWN") and not adapter.receipt.exists("RESULT")
    assert not adapter.receipt.exists("CONSUMED")
    assert CANARY not in json.dumps(doc) + "".join(traceback.format_exception(caught.value))
    assert CANARY not in str(capsys.readouterr()) + caplog.text
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.confirmed_dispatch()
    assert_still_used(adapter, dispatch, transport)


def test_untyped_hostile_exception_is_not_formatted_or_copied(tmp_path, capsys, caplog):
    class HostileError(RuntimeError):
        def __str__(self):
            raise AssertionError("EXCEPTION_MUST_NOT_BE_FORMATTED")
    adapter, dispatch, transport = configured(tmp_path)
    transport.failure = HostileError(CANARY)
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.generate(request=dispatch)
    doc = diagnostic(adapter)
    assert doc["technical_code"] is None and doc["code_source"] is None
    assert CANARY not in json.dumps(doc) + str(capsys.readouterr()) + caplog.text
    assert_still_used(adapter, dispatch, transport)


@pytest.mark.parametrize("point,stage", [
    ("metadata", "RESPONSE_METADATA"), ("RESULT", "RESULT_PUBLISH"),
    ("RESPONSE_CAPTURED", "RESPONSE_CAPTURE_PUBLISH"),
])
def test_returned_response_and_capture_failures_preserve_unknown(tmp_path, monkeypatch, point, stage):
    adapter, dispatch, transport = configured(tmp_path)
    if point == "metadata":
        transport.response = replace(transport.response, usage=None)
    else:
        original = adapter.receipt.publish
        def failing(name, value):
            if name == point:
                raise OSError(errno.EIO, CANARY)
            return original(name, value)
        monkeypatch.setattr(adapter.receipt, "publish", failing)
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.generate(request=dispatch)
    doc = diagnostic(adapter)
    assert doc["stage"] == stage and doc["marker_recorded"] is True
    assert adapter.receipt.exists("UNKNOWN")
    assert not adapter.receipt.exists("RESPONSE_CAPTURED")
    assert adapter.receipt.exists("RESULT") is (point == "RESPONSE_CAPTURED")
    assert not adapter.receipt.exists("CONSUMED")
    assert CANARY not in json.dumps(doc)
    if point != "metadata":
        assert (doc["code_source"], doc["technical_code"]) == ("OS_ERRNO", errno.EIO)
    assert_still_used(adapter, dispatch, transport)


@pytest.mark.parametrize("failed", ["diagnostic", "UNKNOWN", "both"])
def test_secondary_persistence_failure_never_masks_or_retries(tmp_path, monkeypatch, failed):
    adapter, dispatch, transport = configured(tmp_path)
    transport.failure = OpenAITransportError(OpenAITransportErrorCode.CONNECTION)
    original = adapter.receipt.publish
    attempts = {"UNKNOWN": 0, "diagnostic": 0}
    def marker(name, value):
        if name == "UNKNOWN":
            attempts[name] += 1
            if failed in {"UNKNOWN", "both"}:
                raise OSError(errno.EIO, CANARY)
        return original(name, value)
    original_diagnostic = adapter.receipt.publish_failure_diagnostic
    def evidence(value):
        attempts["diagnostic"] += 1
        if failed in {"diagnostic", "both"}:
            raise OSError(errno.EIO, CANARY)
        return original_diagnostic(value)
    monkeypatch.setattr(adapter.receipt, "publish", marker)
    monkeypatch.setattr(adapter.receipt, "publish_failure_diagnostic", evidence)
    with pytest.raises(ValueError, match="^P0_NORMAL_OUTCOME_UNKNOWN$"):
        adapter.generate(request=dispatch)
    assert attempts == {"UNKNOWN": 1, "diagnostic": 1}
    assert adapter.receipt.exists("RESERVED") and not adapter.receipt.exists("CONSUMED")
    assert adapter.receipt.exists("UNKNOWN") is (failed == "diagnostic")
    doc = diagnostic(adapter)
    assert (doc is None) is (failed != "UNKNOWN")
    if doc:
        assert doc["technical_code"] == "CONNECTION" and doc["marker_recorded"] is False
    before = {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")}
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.confirmed_dispatch()
    assert_still_used(adapter, dispatch, transport)
    assert attempts == {"UNKNOWN": 1, "diagnostic": 1}
    assert before == {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")}


@pytest.mark.parametrize("secondary", ["none", "exists", "publish"])
def test_after_capture_primary_parser_error_survives_secondary_failure(tmp_path, monkeypatch, secondary):
    adapter, dispatch, transport = configured(tmp_path)
    transport.response = replace(transport.response, output_text="{broken")
    original_exists, original_publish = adapter.receipt.exists, adapter.receipt.publish
    from backend.adapters.outbound.generation.openai import p0_normal
    original_parse = p0_normal.parse_content
    parsing = [False]
    def parse(*args, **kwargs):
        parsing[0] = True
        return original_parse(*args, **kwargs)
    monkeypatch.setattr(p0_normal, "parse_content", parse)
    def exists(name):
        if name == "PARSING_REJECTED" and secondary == "exists" and parsing[0]:
            raise OSError(errno.EIO, CANARY)
        return original_exists(name)
    def publish(name, value):
        if name == "PARSING_REJECTED" and secondary == "publish":
            raise OSError(errno.EIO, CANARY)
        return original_publish(name, value)
    monkeypatch.setattr(adapter.receipt, "exists", exists)
    monkeypatch.setattr(adapter.receipt, "publish", publish)
    with pytest.raises(ValueError) as caught:
        adapter.generate(request=dispatch)
    assert CANARY not in str(caught.value)
    doc = diagnostic(adapter)
    assert doc["stage"] == "CONTENT_PARSE" and doc["outcome_marker"] == "PARSING_REJECTED"
    assert doc["marker_recorded"] is (secondary == "none")
    assert original_exists("RESPONSE_CAPTURED") and not original_exists("CONSUMED")
    assert not original_exists("UNKNOWN")
    assert_still_used(adapter, dispatch, transport)


def test_guard_failure_keeps_existing_safe_public_error_and_typed_code(tmp_path, monkeypatch):
    adapter, dispatch, transport = configured(tmp_path)
    def guard(*args, **kwargs):
        raise ValueError("P0_RICH_COURSE_NOTION_UNKNOWN")
    monkeypatch.setattr("backend.adapters.outbound.generation.openai.p0_normal.guard_and_bind", guard)
    with pytest.raises(ValueError, match="P0_RICH_COURSE_NOTION_UNKNOWN"):
        adapter.generate(request=dispatch)
    doc = diagnostic(adapter)
    assert doc["stage"] == "GUARD_AND_BIND"
    assert doc["technical_code"] == "P0_RICH_COURSE_NOTION_UNKNOWN"
    assert adapter.receipt.exists("PARSING_REJECTED") and not adapter.receipt.exists("UNKNOWN")
    assert_still_used(adapter, dispatch, transport)


@pytest.mark.parametrize("point", ["PARSED", "CONSUMED"])
def test_terminal_write_failure_is_not_reclassified_as_parsing_or_unknown(tmp_path, monkeypatch, point):
    adapter, dispatch, transport = configured(tmp_path)
    original = adapter.receipt.publish
    def fail(name, value):
        if name == point:
            raise OSError(errno.EIO, CANARY)
        return original(name, value)
    monkeypatch.setattr(adapter.receipt, "publish", fail)
    with pytest.raises(OSError):
        adapter.generate(request=dispatch)
    doc = diagnostic(adapter)
    assert doc["stage"] == point + "_PUBLISH"
    assert doc["outcome_marker"] == "UNCONFIRMED" and doc["marker_recorded"] is False
    assert not adapter.receipt.exists("UNKNOWN") and not adapter.receipt.exists("PARSING_REJECTED")
    assert not adapter.receipt.exists("CONSUMED")
    assert adapter.receipt.exists("PARSED") is (point == "CONSUMED")
    assert_still_used(adapter, dispatch, transport)


def test_nominal_and_recovery_do_not_create_failure_diagnostic(tmp_path):
    adapter, dispatch, transport = configured(tmp_path)
    result = adapter.generate(request=dispatch)
    assert result["production_ref"] == dispatch["production_ref"]
    assert adapter.receipt.exists("CONSUMED") and diagnostic(adapter) is None
    before = {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")}
    assert adapter.recover_confirmed(request=dispatch)["production_ref"] == dispatch["production_ref"]
    assert {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")} == before
    assert_still_used(adapter, dispatch, transport)


def test_no_diagnostic_writer_before_successful_authorized_reserve(tmp_path, monkeypatch):
    config, _, _, dispatch, _, _, _, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    calls = []
    monkeypatch.setattr(adapter.receipt, "publish_failure_diagnostic", lambda value: calls.append(value))
    with pytest.raises(ValueError, match="AUTHORIZE_REQUIRED"):
        adapter.generate(request=dispatch)
    assert not list(adapter.receipt.root.iterdir())
    adapter.authorize(request=dispatch)
    monkeypatch.setattr(adapter.receipt, "reserve", lambda **kwargs: (_ for _ in ()).throw(ValueError("SYNTHETIC_RESERVE_FAILED")))
    with pytest.raises(ValueError, match="SYNTHETIC_RESERVE_FAILED"):
        adapter.generate(request=dispatch)
    assert calls == [] and transport.calls == 0


def test_legacy_unknown_without_new_diagnostic_remains_byte_identical_and_refused(tmp_path):
    adapter, dispatch, transport = configured(tmp_path)
    _, proof, _ = adapter._check(dispatch)
    adapter.receipt.reserve(grant=adapter.grant, dispatch=dispatch,
                            body=adapter.body(adapter._check(dispatch)[0]), preflight=proof)
    adapter.receipt.publish("UNKNOWN", adapter.receipt.event("UNKNOWN", adapter.grant, proof))
    before = {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")}
    assert adapter.receipt.read("UNKNOWN")["schema"] == "P0-NORMAL-TECHNICAL-RECEIPT-1.0"
    assert diagnostic(adapter) is None
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.confirmed_dispatch()
    assert_still_used(adapter, dispatch, transport)
    assert {p.name: p.read_bytes() for p in adapter.receipt.root.glob("*.json")} == before


def test_closed_classification_and_reader_binding(tmp_path):
    assert failure_code(ValueError(CANARY)) == (None, None)
    assert failure_code(LocalFileSecurityError(LocalFileSecurityCode.PATH_CHANGED)) == (
        "LOCAL_FILESYSTEM", "PATH_CHANGED"
    )
    error = OpenAITransportError(OpenAITransportErrorCode.SERVER)
    error.code = CANARY
    assert failure_code(error) == (None, None)
    adapter, dispatch, transport = configured(tmp_path)
    transport.failure = OSError(errno.EIO, CANARY)
    with pytest.raises(ValueError):
        adapter.generate(request=dispatch)
    value = diagnostic(adapter)
    for key, replacement in [("stage", CANARY), ("technical_code", CANARY),
                             ("code_source", CANARY), ("provider_attempts", True),
                             ("marker_recorded", 1), ("namespace_sha256", "9" * 64)]:
        with pytest.raises(ValueError):
            validate_failure_document({**value, key: replacement}, namespace=adapter.receipt.namespace)
    with pytest.raises(ValueError):
        validate_failure_document({**value, "exception": CANARY}, namespace=adapter.receipt.namespace)
    proof = adapter.receipt.read("DISPATCH")["preflight"]
    with pytest.raises(ValueError, match="BINDING"):
        adapter.receipt.read_failure_diagnostic(grant={**adapter.grant, "request_sha256": "9" * 64}, preflight=proof)
    with pytest.raises(ValueError, match="ALREADY_USED"):
        adapter.receipt.publish_failure_diagnostic(value)


def test_public_http_error_is_unchanged_and_has_no_private_diagnostic(tmp_path):
    adapter, dispatch, transport = configured(tmp_path)
    transport.failure = OpenAITransportError(OpenAITransportErrorCode.AUTHENTICATION)
    transport.failure.args = (CANARY,)
    endpoint = P0CreationEndpoint(lambda *args: dict(adapter.generate(request=dispatch)),
                                  lambda *args: {}, [], nonce="SYNTHETIC")
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/generate", b"{}", "SYNTHETIC")
    assert status == 409 and json.loads(raw)["error"]["code"] == "P0_NORMAL_OUTCOME_UNKNOWN"
    assert CANARY not in raw.decode() and "AUTHENTICATION" not in raw.decode()
    assert diagnostic(adapter)["technical_code"] == "AUTHENTICATION"


@pytest.mark.parametrize("mutation", ["grant_sha256", "request_sha256", "preflight_sha256",
                                     "namespace_sha256", "duplicate", "nonfinite", "noncanonical"])
def test_actual_diagnostic_bytes_cannot_substitute_or_expand_evidence(tmp_path, mutation):
    adapter, dispatch, transport = configured(tmp_path)
    transport.failure = OpenAITransportError(OpenAITransportErrorCode.SERVER)
    with pytest.raises(ValueError):
        adapter.generate(request=dispatch)
    doc = diagnostic(adapter)
    raw = canonical(doc)
    if mutation == "duplicate":
        raw = raw[:-1] + b',"stage":"TRANSPORT_CREATE"}'
    elif mutation == "nonfinite":
        raw = b'{"stage":NaN}'
    elif mutation == "noncanonical":
        raw += b"\n"
    else:
        raw = canonical({**doc, mutation: "9" * 64})
    path = adapter.receipt.root / f"p0-diagnostic.{adapter.receipt.namespace}.json"
    # Explicitly corrupt only this synthetic test object, never owner evidence.
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        diagnostic(adapter)
    assert transport.calls == 1 and not adapter.receipt.exists("CONSUMED")


def test_cross_namespace_and_preflight_binding_are_checked_before_read(tmp_path):
    adapter, dispatch, _ = configured(tmp_path)
    _, proof, _ = adapter._check(dispatch)
    grant = adapter.grant
    for changed_grant, changed_proof in [
        ({**grant, "namespace_sha256": "9" * 64}, proof),
        (grant, {"request_sha256": "9" * 64, "request_bytes": grant["request_bytes"]}),
        (grant, {"request_sha256": grant["request_sha256"], "request_bytes": -1}),
    ]:
        with pytest.raises(ValueError, match="BINDING"):
            adapter.receipt.read_failure_diagnostic(grant=changed_grant, preflight=changed_proof)


@pytest.mark.parametrize("mutation", [
    {"stage": "CREDENTIAL_RESOLVE"}, {"provider_attempts": 0},
    {"outcome_marker": "UNCONFIRMED", "marker_recorded": False},
    {"stage": "CONSUMED_PUBLISH"},
])
def test_contradictory_stage_marker_attempt_matrix_is_refused(tmp_path, mutation):
    adapter, dispatch, transport = configured(tmp_path)
    transport.failure = OpenAITransportError(OpenAITransportErrorCode.SERVER)
    with pytest.raises(ValueError):
        adapter.generate(request=dispatch)
    doc = diagnostic(adapter)
    with pytest.raises(ValueError, match="STAGE|BINDING"):
        validate_failure_document({**doc, **mutation}, namespace=adapter.receipt.namespace)


def test_partial_reservation_does_not_open_a_diagnostic_writer(tmp_path, monkeypatch):
    adapter, dispatch, transport = configured(tmp_path)
    original = adapter.receipt.publish
    diagnostics = []
    def publish(name, value):
        if name == "DISPATCH":
            raise OSError(errno.EIO, CANARY)
        return original(name, value)
    monkeypatch.setattr(adapter.receipt, "publish", publish)
    monkeypatch.setattr(adapter.receipt, "publish_failure_diagnostic", diagnostics.append)
    with pytest.raises(OSError):
        adapter.generate(request=dispatch)
    assert adapter.receipt.exists("RESERVED") and not adapter.receipt.exists("DISPATCH")
    assert diagnostics == [] and transport.calls == 0
    assert_still_used(adapter, dispatch, transport)


def test_sidecar_does_not_become_a_lifecycle_namespace_or_p1_slot(tmp_path):
    from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
        P0ContinuityProductLedger,
    )
    adapter, dispatch, transport = configured(tmp_path)
    transport.failure = OpenAITransportError(OpenAITransportErrorCode.SERVER)
    with pytest.raises(ValueError):
        adapter.generate(request=dispatch)
    # Invoke the unchanged inventory on this declared synthetic root only.
    ledger = object.__new__(P0ContinuityProductLedger)
    ledger.root = adapter.receipt.root
    assert set(ledger._normal_namespaces()) == {adapter.receipt.namespace}
    assert list(adapter.receipt.root.glob("*.P1.*.json")) == []
    assert_still_used(adapter, dispatch, transport)


def test_writer_and_reader_share_the_exact_sidecar_size_bound(tmp_path):
    adapter, dispatch, _ = configured(tmp_path)
    _, proof, _ = adapter._check(dispatch)
    sample = {
        "schema": "P0-NORMAL-FAILURE-DIAGNOSTIC-1.0",
        "timestamp_utc": "2026-10-15T12:00:00.+00:00",
        "namespace_sha256": adapter.receipt.namespace,
        "grant_sha256": sha(canonical(adapter.grant)),
        "request_sha256": adapter.grant["request_sha256"],
        "preflight_sha256": sha(canonical(proof)),
        "provider_attempts": 1, "stage": "TRANSPORT_CREATE",
        "code_source": None, "technical_code": None,
        "outcome_marker": "UNKNOWN", "marker_recorded": False,
    }
    digits = MAX_FAILURE_DIAGNOSTIC_BYTES - len(canonical(sample))
    sample["timestamp_utc"] = "2026-10-15T12:00:00." + "0" * digits + "+00:00"
    assert len(canonical(sample)) == MAX_FAILURE_DIAGNOSTIC_BYTES
    path = adapter.receipt.root / f"p0-diagnostic.{adapter.receipt.namespace}.json"
    oversized = {**sample, "timestamp_utc": sample["timestamp_utc"].replace(".", ".0")}
    with pytest.raises(ValueError, match="DIAGNOSTIC_SIZE"):
        adapter.receipt.publish_failure_diagnostic(oversized)
    assert not path.exists()
    adapter.receipt.publish_failure_diagnostic(sample)
    assert path.read_bytes() == canonical(sample)
    assert adapter.receipt.read_failure_diagnostic(grant=adapter.grant, preflight=proof) == sample
