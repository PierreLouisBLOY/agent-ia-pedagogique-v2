"""Synthetic captured content; real Application, native writer, filesystem and CLI."""
import hashlib
import json
import socket
from dataclasses import replace
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_captured_partial import read, setup_capture

from backend.adapters.inbound.cli.local_browser import main
from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter
from backend.adapters.outbound.export.word import OOXMLWordWriter
from backend.infrastructure.composition.factories.local_browser import build_local_saved
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.materialization_export.application.services.partial_chapter import capture_tree
from backend.modules.materialization_export.application.services.partial_projection import (
    partial_document,
)
from backend.modules.materialization_export.contracts.dto.lot1_word_table import (
    Lot1WordDocument,
    Lot1WordTable,
)
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import CapturedPartial
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionView,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = "/api/v2/captured-partial"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture(scope="module")
def capture(tmp_path_factory):
    task = tmp_path_factory.mktemp("synthetic-capture")
    with pytest.MonkeyPatch.context() as patch:
        case = setup_capture(task, patch)
        outcome = read(case)
        assert outcome.success and outcome.data is not None
        original = outcome.data
    table = {"columns": ["Structure", "Indice", "Réponse"], "rows": [["Synthétique", "Fait", ""], ["Autre", "", ""]]}
    chapter = {"context": {"title": "Contexte synthétique", "text": "Donnée <script> jamais exécutable"},
        "documents": [{"id": f"D{n}", "title": f"Support synthétique {n}", "text": f"Fait observé {n}",
            "table": table if n == 4 else None} for n in range(1, 5)],
        "parts": [{"title": "Progression synthétique"}],
        "questions": [{"id": f"Q1-{n}", "prompt": f"Question synthétique {n}",
            "response": {"lines": 6, "table": None if n == 4 else table}} for n in range(1, 7)],
        "concepts": [{"id": f"N{n}", "definition": f"Définition {n}", "explanation": f"Explication {n}",
            "example": f"Exemple {n}"} for n in range(1, 7)], "synthesis": "Synthèse synthétique",
        "transfer": {"title": "Transfert synthétique", "question_ids": ["Q1-6"]},
        "teacher_answers": [{"id": f"Q1-{n}", "expected_answer": f"TEACHER_ONLY_ANSWER_{n}",
            "rationale": "TEACHER_ONLY_REASON", "vigilance": "TEACHER_ONLY_CAUTION", "remediation": "TEACHER_ONLY_HELP"}
            for n in range(1, 4)]}
    text = json.dumps({"title": "Cours synthétique", "course_chapter": chapter}, ensure_ascii=False, separators=(",", ":"))
    assert text.endswith("]}}")
    text = text[:-3] + ',{"id":"Q1-4","expected_answer":"TEACHER_ONLY_INTERRUPTED'
    raw = text.encode()
    result_hash = digest(b"SYNTHETIC_RESULT_" + raw)
    request = replace(original.request, result_sha256=result_hash, text_sha256=digest(raw), text_bytes=len(raw))
    data = original.metadata.as_dict()
    data["schema"] = "P0-PILOT-COMMAND-INSPECTION-1.1"
    data["response_metadata"].update(result_sha256=result_hash, output_text_sha256=request.text_sha256,
        output_text_bytes=len(raw))
    for event in data["receipts"]:
        if event["state"] == "RESULT":
            event["sha256"] = result_hash
    return CapturedPartial(request, text, P1CampaignInspectionView.from_mapping(data))


def artifacts(tmp_path, capture):
    root = tmp_path / "artifacts"
    root.mkdir()
    request = capture.request
    files = {"text.txt": capture.text.encode(), "metadata.json": json.dumps(capture.metadata.as_dict()).encode(),
        "read.json": json.dumps({"state": "PARTIAL_CAPTURE_RECOVERED_UNVALIDATED",
            "inspection_profile_sha256": request.profile_sha256,
            **{key: getattr(request, key) for key in ("command_id", "result_sha256", "text_sha256", "text_bytes")}}).encode()}
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    manifest = {"schema": "V2-CAPTURED-PARTIAL-LOCAL-1.0", "request": {
        key: getattr(request, key) for key in ("command_id", "profile_sha256", "request_sha256", "result_sha256", "text_sha256", "text_bytes")},
        "text_file": "text.txt", "metadata_file": "metadata.json", "metadata_sha256": digest(files["metadata.json"]),
        "read_record_file": "read.json", "read_record_sha256": digest(files["read.json"])}
    path = root / "manifest.json"
    path.write_bytes(json.dumps(manifest).encode())
    return path, digest(path.read_bytes())


def app(tmp_path, capture):
    manifest, pin = artifacts(tmp_path, capture)
    configuration = LocalBrowserHttpConfiguration(port=port())
    instance = build_local_saved(configuration, tmp_path / "library", create=True,
        partial_manifest=manifest, partial_manifest_sha256=pin)
    return instance, manifest, pin


def send(instance, method="GET", path="", body=None, extra=None):
    configuration = instance.server.service.configuration
    headers = {"host": f"127.0.0.1:{configuration.port}", "origin": f"http://127.0.0.1:{configuration.port}",
        "x-local-intent": "conversation-v1"}
    if extra:
        headers.update(extra)
    return instance.server.service.respond(method, ROOT + path, headers, "SYNTHETIC_PARTIAL",
        b"" if body is None else json.dumps(body).encode())


def test_native_tables_both_views_and_student_isolation(capture):
    for kind in ("student", "correction"):
        document = partial_document(capture, kind)
        assert len(document.tables) == 6
        assert all(t.rows[-1][-1] == "" for t in document.tables)
        raw = Lot1OOXMLWordWriter().write(document)
        with ZipFile(BytesIO(raw)) as archive:
            xml = ET.fromstring(archive.read("word/document.xml"))
            tables = xml.findall(".//" + W + "tbl")
            assert len(tables) == 6
            for native, expected in zip(tables, document.tables, strict=True):
                assert all(row.find(W + "trPr/" + W + "cantSplit") is not None for row in native.findall(W + "tr"))
                rows = tuple(tuple("".join(p.text or "" for p in cell.iter(W + "t"))
                    for cell in row.findall(W + "tc")) for row in native.findall(W + "tr"))
                assert rows == expected.rows
            text = "".join(node.text or "" for node in xml.iter(W + "t"))
            assert "BROUILLON PARTIEL NON VALIDÉ" in text
            assert "[\"Structure\"" not in text
            assert ("TEACHER_ONLY" in text) == (kind == "correction")
            assert not any("vba" in name.lower() for name in archive.namelist())
        if kind == "correction":
            assert text.count("Réponse non capturée") == 2 and "Réponse interrompue" in text


def test_ordinary_writer_and_lot1_contract_unchanged():
    doc = WordDocument("student", "Titre synthétique", (WordBlock("Normal", "Texte"),))
    assert Lot1OOXMLWordWriter().write(doc) == OOXMLWordWriter().write(doc)
    with pytest.raises(ValueError):
        Lot1WordDocument("correction", "Titre", ())
    legacy = Lot1WordDocument("student", "Titre", (WordBlock("Normal", "Avant"),),
        tables=(Lot1WordTable(0, (("A", "B"), ("Texte", ""))),))
    with ZipFile(BytesIO(Lot1OOXMLWordWriter().write(legacy))) as archive:
        assert ET.fromstring(archive.read("word/document.xml")).find(".//" + W + "cantSplit") is None


@pytest.mark.parametrize("text", ['{"a":1,"a":2,"b":"fin', '{"a":[1,],"b":"fin', '{"a":NaN}', '{"a":"terminé"}', '{"a":tru'])
def test_malformed_or_complete_source_not_silently_repaired(text):
    with pytest.raises(ValueError):
        capture_tree(text)


def test_application_save_reopen_http_guards_and_no_effects(tmp_path, capture):
    instance, manifest, pin = app(tmp_path, capture)
    original = {p.name: p.read_bytes() for p in manifest.parent.iterdir()}
    try:
        status, _, raw, _ = send(instance)
        assert status == 200
        opened = json.loads(raw)["data"]
        assert not opened["saved"] and opened["effect_permitted"] is False
        assert send(instance, path="/word/student")[0] == 409
        body = {"source_sha256": capture.request.text_sha256, "projection_sha256": opened["projection_sha256"]}
        assert send(instance, "POST", "/save", body)[0] == 403
        headers = {"x-r2-nonce": opened["transport_nonce"]}
        assert send(instance, "POST", "/save", body, {**headers, "origin": "https://foreign.invalid"})[0] == 403
        assert send(instance, "POST", "/save", {**body, "source_sha256": "0" * 64}, headers)[0] == 409
        assert send(instance, "POST", "/save", body, headers)[0] == 200
        state = (tmp_path / "library" / "captured-partial-native-tables-v1.json").read_bytes()
        assert send(instance, "POST", "/save", body, headers)[0] == 200
        assert (tmp_path / "library" / "captured-partial-native-tables-v1.json").read_bytes() == state
        for kind in ("student", "correction"):
            assert send(instance, path="/word/" + kind)[0] == 200
        assert {p.name: p.read_bytes() for p in manifest.parent.iterdir()} == original
    finally:
        instance.close()
    reopened = build_local_saved(LocalBrowserHttpConfiguration(port=port()), tmp_path / "library",
        partial_manifest=manifest, partial_manifest_sha256=pin)
    try:
        data = json.loads(send(reopened)[2])["data"]
        assert data["saved"] and data["version_ref"] == opened["version_ref"]
    finally:
        reopened.close()


def test_source_and_derived_identity_changes_refused(tmp_path, capture, monkeypatch):
    instance, manifest, _ = app(tmp_path, capture)
    try:
        opened = json.loads(send(instance)[2])["data"]
        assert send(instance, "POST", "/save", {"source_sha256": capture.request.text_sha256,
            "projection_sha256": opened["projection_sha256"]},
            {"x-r2-nonce": opened["transport_nonce"]})[0] == 200
        import backend.modules.materialization_export.application.services.partial_workspace as module
        original = module.partial_document
        monkeypatch.setattr(module, "partial_document", lambda c, k: replace(original(c, k), title="Divergent"))
        assert send(instance)[0] == 409
        monkeypatch.setattr(module, "partial_document", original)
        (manifest.parent / "text.txt").write_text("Divergent", encoding="utf-8")
        assert send(instance)[0] == 409 and send(instance, path="/word/student")[0] == 409
    finally:
        instance.close()


def test_inventory_via_application_has_fidelity_proofs_without_raw_text(tmp_path, capture):
    instance, _, _ = app(tmp_path, capture)
    try:
        status, _, raw, _ = send(instance, path="/inventory")
        assert status == 200
        data = json.loads(raw)["data"]
        assert data["tables_equal_in_both_views"] and len(data["table_sha256s"]) == 6
        assert data["complete_answers"] == 3 and data["missing"] == ["Q1-4 incomplete", "Q1-5 absent", "Q1-6 absent"]
        assert "TEACHER_ONLY" not in raw.decode()
    finally:
        instance.close()


def test_changed_derivative_before_first_save_is_refused_without_write(tmp_path, capture, monkeypatch):
    instance, _, _ = app(tmp_path, capture)
    try:
        opened = json.loads(send(instance)[2])["data"]
        import backend.modules.materialization_export.application.services.partial_workspace as module
        original = module.partial_document
        monkeypatch.setattr(module, "partial_document", lambda c, k: replace(original(c, k), title="Changed after open"))
        assert send(instance, "POST", "/save", {"source_sha256": capture.request.text_sha256,
            "projection_sha256": opened["projection_sha256"]}, {"x-r2-nonce": opened["transport_nonce"]})[0] == 409
        assert not (tmp_path / "library" / "captured-partial-native-tables-v1.json").exists()
    finally:
        instance.close()


@pytest.mark.parametrize("which", ["root", "manifest"])
def test_normalized_source_path_refused_before_library_creation(tmp_path, monkeypatch, which):
    import backend.infrastructure.composition.factories.local_browser as module
    def forbidden(*args, **kwargs):
        pytest.fail("Library was created before normalized path was refused")
    monkeypatch.setattr(module, "build_saved_application", forbidden)
    alias = module._ROOT.parent / "not-source" / ".." / module._ROOT.name / "forbidden-library"
    root = alias if which == "root" else tmp_path / "library"
    manifest = (alias / "manifest.json") if which == "manifest" else tmp_path / "manifest.json"
    with pytest.raises(ValueError, match="PARTIAL_OUTSIDE_SOURCE_REQUIRED"):
        build_local_saved(LocalBrowserHttpConfiguration(port=19431), root, create=True,
            partial_manifest=manifest, partial_manifest_sha256="a" * 64)


def test_real_cli_saved_only_without_console_or_credential(tmp_path, capture, monkeypatch):
    manifest, pin = artifacts(tmp_path, capture)
    def forbidden(*args, **kwargs):
        pytest.fail("Credential or generation attempted in partial saved-only mode")
    import getpass

    from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
    from backend.infrastructure.composition.factories.local_browser import LocalRead15Composition
    monkeypatch.setattr(getpass, "getpass", forbidden)
    monkeypatch.setattr(NormalP0GenerationAdapter, "generate", forbidden)
    monkeypatch.setattr(LocalRead15Composition, "serve_forever", lambda self: None)
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC_NOT_A_CREDENTIAL")
    assert main(["--port", str(port()), "--saved-only", "--saved-root", str(tmp_path / "library"), "--create-saved",
        "--partial-manifest", str(manifest), "--partial-manifest-sha256", pin]) == 0


@pytest.mark.parametrize("flags", [["--enable-conversation"], ["--enable-review-modify"],
    ["--live-authorization", "C:/synthetic/live"], ["--p0-normal-profile", "C:/synthetic/profile"],
    ["--r5-scope", "C:/synthetic/scope"], ["--runtime", "C:/synthetic/runtime"]])
def test_cli_rejects_all_effect_selections_before_startup(flags):
    assert main(["--port", "19431", "--saved-only", "--saved-root", "C:/synthetic/library",
        "--partial-manifest", "C:/synthetic/manifest", "--partial-manifest-sha256", "a" * 64, *flags]) == 1
