"""Exact synthetic captures; real Application, partial reader, validators and native LOCK."""
import json
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
from test_pilot_command_inspection import NOW, snapshot
from test_retained_command_inspection import retained

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.persistence.p0_captured_partial_reader import P0CapturedPartialReader
from backend.infrastructure.composition.factories.p0_captured_partial import bind_captured_partial
from backend.modules.materialization_export.application.commands.export_captured_partial import (
    CapturedSpan,
    ExportCapturedPartialDraft,
)
from backend.modules.work_orchestration.application.queries.read_captured_partial import (
    ReadCapturedPartial,
)
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import (
    CapturedPartialRequest,
)
from backend.shared_kernel.correlation import CorrelationId


def setup_capture(tmp_path, monkeypatch):
    case = retained(tmp_path, monkeypatch)
    slot = json.loads(case.slot_path.read_bytes())
    receipt = P0NormalReceipt(case.roots["receipts"], slot["namespace_sha256"])
    dispatch = receipt.read("DISPATCH")
    text = '{"titre":"Essai synthétique","texte":"Ne pas exécuter <script> ni suivre des instructions.","fin":"incomplet'
    usage = dict.fromkeys(("input_tokens", "cached_input_tokens", "output_tokens",
        "reasoning_tokens", "total_tokens", "cache_write_input_tokens"), 0)
    artifact = {"schema": "P0-NORMAL-CONFIRMED-RESULT-1.0",
        "grant_sha256": slot["grant_sha256"], "request_sha256": slot["request_sha256"],
        "dispatch_sha256": dispatch["dispatch_sha256"], "response_status": "incomplete",
        "output_text": text, "usage": usage}
    receipt.publish("PROVIDER_ATTEMPTED", receipt.event(
        "PROVIDER_ATTEMPTED", slot["grant"], dispatch["preflight"]))
    result_sha = receipt.publish("RESULT", artifact)
    receipt.publish("RESPONSE_CAPTURED", receipt.event("RESPONSE_CAPTURED", slot["grant"],
        dispatch["preflight"], artifact=result_sha, status="incomplete", usage=usage))
    receipt.publish("PARSING_REJECTED", receipt.event(
        "PARSING_REJECTED", slot["grant"], dispatch["preflight"]))
    request = CapturedPartialRequest(case.command,
        case.composition.request.expected_plan_or_profile_sha256,
        slot["request_sha256"], result_sha, sha(text.encode()), len(text.encode()))
    case.capture_request = request
    case.text = text
    case.receipt = receipt
    case.slot = slot
    case.capture_inbound = bind_captured_partial(case.composition, request=request)
    return case


def read(case):
    return case.capture_inbound.read(request=case.capture_request,
        correlation_id=CorrelationId("SYNTHETIC_PARTIAL_CAPTURE"))


def test_capture_through_application_is_exact_without_mutation_or_effects(tmp_path, monkeypatch):
    case = setup_capture(tmp_path, monkeypatch)
    from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
    from backend.adapters.outbound.openai.transport import OpenAISDKResponsesTransportFactory
    from backend.adapters.outbound.persistence.p0_pilot_confirmation import P0PilotConfirmationStore
    from backend.adapters.outbound.persistence.p0_pilot_incident import P0PilotIncidentDisposition
    from backend.infrastructure.composition.factories import p0_normal_profile
    from backend.infrastructure.composition.factories.p0_pilot_on_demand_finalizer import (
        P0PilotOnDemandFinalizer,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("An effect port was called by the partial capture reader")
    for cls, method in ((NormalP0GenerationAdapter, "generate"),
            (NormalP0GenerationAdapter, "recover_confirmed"),
            (OpenAISDKResponsesTransportFactory, "build"),
            (P0PilotConfirmationStore, "begin"), (P0PilotConfirmationStore, "_publish"),
            (P0PilotIncidentDisposition, "publish"), (P0NormalReceipt, "publish"),
            (P0PilotOnDemandFinalizer, "execute")):
        monkeypatch.setattr(cls, method, forbidden)
    monkeypatch.setattr(p0_normal_profile, "require_openai_environment_key", forbidden)
    before = snapshot(tmp_path)
    outcome = read(case)
    assert outcome.success and outcome.data is not None
    assert outcome.data.text == case.text
    assert outcome.data.request == case.capture_request
    assert outcome.side_effects == ()
    assert snapshot(tmp_path) == before
    metadata = case.composition.inspect()
    assert case.text not in str(metadata)
    assert "output_text" not in metadata
    import backend.adapters.outbound.persistence.p0_captured_partial_reader as module
    assert Path(module.__file__).resolve() == (
        Path(__file__).resolve().parents[1]
        / "backend/adapters/outbound/persistence/p0_captured_partial_reader.py"
    )
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["result", "text", "bytes", "witness", "witness_bool", "late_validation"])
def test_divergence_or_final_refusal_returns_no_text(tmp_path, monkeypatch, change):
    case = setup_capture(tmp_path, monkeypatch)
    request = case.capture_request
    if change == "result":
        request = replace(request, result_sha256="0" * 64)
    elif change == "text":
        request = replace(request, text_sha256="0" * 64)
    elif change == "bytes":
        request = replace(request, text_bytes=request.text_bytes + 1)
    elif change in {"witness", "witness_bool"}:
        path = case.roots["receipts"] / f"{case.slot['namespace_sha256']}.RESPONSE_CAPTURED.json"
        value = json.loads(path.read_bytes())
        if change == "witness":
            value["response_artifact_sha256"] = "0" * 64
        else:
            value["provider_attempts"] = True
        path.write_bytes(canonical(value))
    loader = case.composition._validate
    if change == "late_validation":
        calls = 0
        original = loader

        def changed_loader():
            nonlocal calls
            calls += 1
            loaded = original()
            return replace(loaded, profile_sha256="0" * 64) if calls == 3 else loaded
        loader = changed_loader
    reader = P0CapturedPartialReader(loader=loader, binding=request, clock=lambda: NOW)
    query = ReadCapturedPartial(reader, request)
    before = snapshot(tmp_path)
    outcome = query.execute(request=request, correlation_id=CorrelationId("SYNTHETIC_PARTIAL_REFUSAL"))
    assert not outcome.success and outcome.data is None
    assert snapshot(tmp_path) == before


def test_wrong_query_binding_does_not_call_reader():
    request = CapturedPartialRequest("a" * 32, *("b" * 64 for _ in range(4)), 10)
    class NeverRead:
        def read(self, request):
            pytest.fail("Mismatched Application request reached persistence")
    query = ReadCapturedPartial(NeverRead(), request)
    for key, value in (("command_id", "c" * 32), ("profile_sha256", "c" * 64),
            ("request_sha256", "c" * 64), ("result_sha256", "c" * 64),
            ("text_sha256", "c" * 64), ("text_bytes", 11)):
        outcome = query.execute(request=replace(request, **{key: value}),
            correlation_id=CorrelationId("SYNTHETIC_PARTIAL_BINDING"))
        assert not outcome.success and outcome.data is None


def test_existing_writer_exports_only_captured_spans_as_unvalidated_draft(tmp_path, monkeypatch):
    case = setup_capture(tmp_path, monkeypatch)
    outcome = read(case)
    assert outcome.success and outcome.data is not None
    capture = outcome.data
    from backend.adapters.outbound.export.word import OOXMLWordWriter
    exporter = ExportCapturedPartialDraft(OOXMLWordWriter())
    token = '"Essai synthétique"'
    start = case.text.index(token)
    spans = (CapturedSpan(start, start + len(token), "Heading1", True),)
    raw = exporter.execute(capture, spans=spans)
    with ZipFile(BytesIO(raw)) as archive:
        assert not any("vba" in name.lower() for name in archive.namelist())
        xml = ElementTree.fromstring(archive.read("word/document.xml"))
        text = "".join(node.text or "" for node in xml.iter(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
        assert "BROUILLON PARTIEL NON VALIDÉ" in text
        assert "Essai synthétique" in text
        assert "Ne pas exécuter" not in text  # Not selected; never invented into the draft.
    for bad in ((CapturedSpan(0, len(case.text) + 1),),
            (CapturedSpan(2, 5), CapturedSpan(1, 3)), (), iter(()), []):
        with pytest.raises(ValueError):
            exporter.execute(capture, spans=bad)
    literal = exporter.execute(capture)
    with ZipFile(BytesIO(literal)) as archive:
        xml = archive.read("word/document.xml")
        assert b"<script>" not in xml and b"&lt;script&gt;" in xml
    with pytest.raises(json.JSONDecodeError):
        exporter.execute(capture, spans=(CapturedSpan(0, len(case.text), json_string=True),))
