"""315 delta: synthetic references, real filesystem locks, normal factories and OOXML."""

import json
import os
import subprocess
import sys
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_partial_revision import plan_for
from test_partial_workspace import artifacts, digest, port, send
from test_partial_workspace import capture as capture  # noqa: PLC0414 -- pytest fixture re-export

from backend.adapters.inbound.cli.local_browser import main
from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter
from backend.adapters.outbound.persistence.format_reference import LocalFormatReferenceStore
from backend.infrastructure.composition.factories.local_browser import build_local_saved
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.resource_library.application.commands.register_format_reference import (
    RegisterFormatReference,
)
from backend.modules.resource_library.application.queries.read_format_reference import (
    ReadFormatReference,
)
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def reference(source, raw=b"SYNTHETIC_BINARY_DOCX"):
    source.mkdir(exist_ok=True)
    (source / "reference.docx").write_bytes(raw)
    decision = b"SYNTHETIC_OWNER_DECISION"
    record = FormatReference(
        {
            "schema": "FORMAT-REFERENCE-1.0",
            "reference_id": "V2-FORMAT-TEST-001",
            "title": "Synthetic format",
            "document_type": "cours_version_eleve",
            "level": "Première STMG",
            "scope": {"approved_for": ["format"], "excluded": ["teacher", "third_party_media"]},
            "approval_status": "OWNER_APPROVED_REFERENCE",
            "decision_date": "2026-10-24",
            "decision_sha256": digest(decision),
            "source_sha256": digest(raw),
            "size_bytes": len(raw),
            "storage_ref": "format-reference:V2-FORMAT-TEST-001/document.docx",
            "provenance": {
                "kind": "OWNER_PROVIDED_DOCX",
                "filename": "reference.docx",
                "decision_ref": "owner-decision:" + digest(decision),
            },
            "media_policy": "NO_REDISTRIBUTION_WITHOUT_RIGHTS",
        }
    )
    return record, decision


def test_register_read_restart_idempotent_and_explicit_authority(tmp_path):
    source, library = tmp_path / "source", tmp_path / "library"
    record, _ = reference(source)
    store = LocalFormatReferenceStore(library, source)
    with pytest.raises(ValueError):
        RegisterFormatReference(store, record).execute(record, "reference.docx")
    cmd = RegisterFormatReference(store, record, enabled=True)
    assert cmd.execute(record, "reference.docx").version_ref == record.version_ref
    assert cmd.execute(record, "reference.docx").as_dict() == record.as_dict()
    restarted = ReadFormatReference(LocalFormatReferenceStore(library, source), record)
    assert restarted.execute(record.reference_id).version_ref == record.version_ref
    with pytest.raises(ValueError):
        restarted.execute("V2-FORMAT-OTHER")


@pytest.mark.parametrize(
    "mutation",
    ["missing", "wrong_hash", "outside", "absolute", "binary", "metadata", "contradictory"],
)
def test_refuses_missing_paths_hash_tampering_and_conflict(tmp_path, mutation):
    source, library = tmp_path / "source", tmp_path / "library"
    record, _ = reference(source)
    store = LocalFormatReferenceStore(library, source)
    locator = "reference.docx"
    if mutation == "missing":
        locator = "absent.docx"
    if mutation == "wrong_hash":
        (source / locator).write_bytes(b"wrong")
    if mutation == "outside":
        locator = "../source/reference.docx"
    if mutation == "absolute":
        locator = str(source / locator)
    if mutation in {"binary", "metadata", "contradictory"}:
        store.register(record, locator)
        directory = library / "format-references" / record.reference_id
        if mutation == "binary":
            (directory / "document.docx").write_bytes(b"altered")
        if mutation == "metadata":
            changed = record.as_dict()
            changed["title"] = "silently changed"
            from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded

            (directory / "record.json").write_bytes(encoded(changed))
        if mutation == "contradictory":
            changed = record.as_dict()
            changed["title"] = "Other admitted identity"
            record = FormatReference(changed)
    with pytest.raises((ValueError, OSError, RuntimeError)):
        if mutation in {"binary", "metadata"}:
            ReadFormatReference(store, record).execute(record.reference_id)
        else:
            store.register(record, locator)


def test_interruption_after_binary_refuses_implicit_repair(tmp_path, monkeypatch):
    source, library = tmp_path / "source", tmp_path / "library"
    record, _ = reference(source)
    store = LocalFormatReferenceStore(library, source)
    original = store._fresh

    def fail_record(directory, name, raw):
        if name == "record.json":
            raise RuntimeError("SYNTHETIC_INTERRUPTION")
        return original(directory, name, raw)

    monkeypatch.setattr(store, "_fresh", fail_record)
    with pytest.raises(RuntimeError):
        store.register(record, "reference.docx")
    monkeypatch.setattr(store, "_fresh", original)
    orphan = library / "format-references" / record.reference_id / "document.docx"
    before = orphan.read_bytes()
    with pytest.raises((ValueError, OSError)):
        store.register(record, "reference.docx")
    assert orphan.read_bytes() == before


def test_concurrent_contradictory_registration_other_process_refused(tmp_path, monkeypatch):
    source, library = tmp_path / "source", tmp_path / "library"
    record, _ = reference(source)
    store = LocalFormatReferenceStore(library, source)
    changed = record.as_dict()
    changed["title"] = "CONTRADICTORY_CONCURRENT"
    original = store._fresh
    attempts = []

    def concurrent(directory, name, raw):
        if name == "document.docx":
            script = """import json,sys
from pathlib import Path
from backend.adapters.outbound.persistence.format_reference import LocalFormatReferenceStore
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference
try:
 LocalFormatReferenceStore(Path(sys.argv[1]),Path(sys.argv[2])).register(FormatReference(json.loads(sys.argv[3])),"reference.docx")
except OSError:
 sys.exit(23)
sys.exit(0)
"""
            env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
            result = subprocess.run(
                [sys.executable, "-c", script, str(library), str(source), json.dumps(changed)],
                capture_output=True,
                timeout=20,
                env=env,
            )
            attempts.append(result.returncode)
        return original(directory, name, raw)

    monkeypatch.setattr(store, "_fresh", concurrent)
    store.register(record, "reference.docx")
    assert attempts == [23]
    assert store.read(record.reference_id).as_dict() == record.as_dict()
    with pytest.raises(ValueError):
        store.register(FormatReference(changed), "reference.docx")


@pytest.mark.parametrize(
    "field,value",
    [
        ("size_bytes", True),
        ("decision_date", "bad"),
        ("approval_status", "UNREVIEWED"),
        ("source_sha256", "bad"),
        ("storage_ref", "../outside"),
    ],
)
def test_closed_metadata_rejects_invalid_identity(tmp_path, field, value):
    record, _ = reference(tmp_path / "source")
    changed = record.as_dict()
    changed[field] = value
    with pytest.raises(ValueError):
        FormatReference(changed)


def configured(tmp_path, capture):
    manifest, _ = artifacts(tmp_path, capture)
    base, plan = plan_for(capture)
    revision = manifest.parent / "revision.json"
    revision.write_text(json.dumps(plan), encoding="utf-8")
    record, decision = reference(manifest.parent / "source")
    (manifest.parent / "decision.md").write_bytes(decision)
    library = tmp_path / "library315"
    admission = {
        "schema": "FORMAT-REFERENCE-LOCAL-ADMISSION-1.0",
        "target_root": str(library),
        "role": "ISOLATED_FORMAT_REFERENCE_TEST",
        "source_root": str(manifest.parent / "source"),
        "source_locator": "reference.docx",
        "decision_file": "decision.md",
        "record": record.as_dict(),
        "identification": {
            k: k + " synthetic"
            for k in ("level", "theme", "chapter", "question", "finality", "notions")
        },
    }
    path = manifest.parent / "format.json"
    path.write_text(json.dumps(admission), encoding="utf-8")
    content = json.loads(manifest.read_bytes())
    content["format_reference"] = {"file": path.name, "sha256": digest(path.read_bytes())}
    content["local_revision"] = {"file": revision.name, "sha256": digest(revision.read_bytes())}
    manifest.write_text(json.dumps(content), encoding="utf-8")
    return manifest, digest(manifest.read_bytes()), library, record, base, plan


def test_normal_composition_save_restart_export_and_teacher_unchanged(tmp_path, capture):
    manifest, pin, library, record, base, plan = configured(tmp_path, capture)
    from backend.modules.materialization_export.application.services.partial_revision import (
        revise_partial,
    )

    derived, _ = revise_partial(base, plan, capture.request.text_sha256)

    def build(create=False, register=False):
        return build_local_saved(
            LocalBrowserHttpConfiguration(port=port()),
            library,
            create=create,
            partial_manifest=manifest,
            partial_manifest_sha256=pin,
            partial_word_profile="stmg-format-001",
            register_format_reference=register,
        )

    app = build(True, True)
    try:
        opened = json.loads(send(app)[2])["data"]
        assert not opened["effect_permitted"] and not opened["saved"]
        ref = json.loads(send(app, path="/reference")[2])["data"]
        assert ref["binary_verified"] and ref["version_ref"] == record.version_ref
        assert send(app, "POST", "/reference", {})[0] != 200
        assert send(app, path="/word/student")[0] == 409
        body = {
            "source_sha256": opened["source_sha256"],
            "projection_sha256": opened["projection_sha256"],
        }
        assert send(app, "POST", "/save", body)[0] == 403
        assert send(app, "POST", "/save", body, {"x-r2-nonce": opened["transport_nonce"]})[0] == 200
        student = send(app, path="/word/student")[2]
        teacher = send(app, path="/word/correction")[2]
        assert teacher == Lot1OOXMLWordWriter().write(derived["correction"])
        with ZipFile(BytesIO(student)) as z:
            xml = ET.fromstring(z.read("word/document.xml"))
            assert len(xml.findall(".//" + W + "tbl")) == 7
            assert xml.find(".//" + W + "pgSz").get(W + "w") == "11906"
            assert xml.find(".//" + W + "pgMar").get(W + "top") == "720"
            assert b"PAGE" in z.read("word/footer1.xml")
            text = "".join(xml.itertext())
            assert "TEACHER_ONLY" not in text and "ONLY_NEW_LOCAL_ANSWER" not in text
            notes = json.loads(ET.fromstring(z.read("docProps/custom.xml"))[1][0].text)
            internal = {entry["text"] for entry in notes}
            assert all(b.text.replace("\n", "") in text or b.text in internal for b in derived["student"].blocks)
    finally:
        app.close()
    app = build()
    try:
        reopened = json.loads(send(app)[2])["data"]
        assert reopened["saved"] and reopened["version_ref"] == opened["version_ref"]
        assert send(app, path="/word/student")[2] == student
        assert json.loads(send(app, path="/reference")[2])["data"] == ref
        (library / "format-references" / record.reference_id / "document.docx").write_bytes(
            b"tampered"
        )
        assert send(app, path="/word/student")[0] != 200
    finally:
        app.close()


def test_cli_rejects_profile_without_pinned_saved_only_manifest():
    assert main(["--port", "8944", "--partial-word-profile", "stmg-format-001"]) == 1
    assert main(["--port", "8944", "--register-format-reference"]) == 1


def test_student_synthesis_column_widths_and_default_writer_unchanged(capture):
    from backend.adapters.outbound.export.stmg_reference_word import STMGReferenceWordWriter
    from backend.modules.materialization_export.application.services.partial_projection import (
        partial_document,
    )

    identification = {
        k: "Synthetic " + k
        for k in ("level", "theme", "chapter", "question", "finality", "notions")
    }
    writer = STMGReferenceWordWriter(identification)
    document = partial_document(capture, "student")
    with ZipFile(BytesIO(writer.write(document))) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        table = root.findall(".//" + W + "tbl")[-1]
        assert [n.get(W + "w") for n in table.find(W + "tblGrid")] == ["2400", "4300", "3380"]
        for row in table.findall(W + "tr"):
            assert [
                cell.find(W + "tcPr/" + W + "tcW").get(W + "w") for cell in row.findall(W + "tc")
            ] == ["2400", "4300", "3380"]
    teacher = partial_document(capture, "correction")
    assert writer.write(teacher) == Lot1OOXMLWordWriter().write(teacher)


def test_saved_version_cannot_silently_select_another_profile(tmp_path, capture):
    manifest, pin, library, _, _, _ = configured(tmp_path, capture)
    app = build_local_saved(
        LocalBrowserHttpConfiguration(port=port()),
        library,
        create=True,
        partial_manifest=manifest,
        partial_manifest_sha256=pin,
    )
    try:
        opened = json.loads(send(app)[2])["data"]
        body = {
            "source_sha256": opened["source_sha256"],
            "projection_sha256": opened["projection_sha256"],
        }
        assert send(app, "POST", "/save", body, {"x-r2-nonce": opened["transport_nonce"]})[0] == 200
    finally:
        app.close()
    previous = (library / "captured-partial-native-tables-v1.json").read_bytes()
    changed = build_local_saved(
        LocalBrowserHttpConfiguration(port=port()),
        library,
        partial_manifest=manifest,
        partial_manifest_sha256=pin,
        partial_word_profile="stmg-format-001",
        register_format_reference=True,
    )
    try:
        assert send(changed)[0] == 409
        assert send(changed, path="/word/student")[0] == 409
        assert (library / "captured-partial-native-tables-v1.json").read_bytes() == previous
    finally:
        changed.close()
