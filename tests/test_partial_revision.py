"""312delta only: synthetic local edits through actual Application/HTTP factories."""

import copy
import hashlib
import json
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_partial_workspace import artifacts, digest, port, send
from test_partial_workspace import (
    capture as capture,  # noqa: PLC0414 -- pytest fixture re-export
)

from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter
from backend.infrastructure.composition.factories.local_browser import build_local_saved
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.materialization_export.application.services.partial_projection import (
    partial_document,
)
from backend.modules.materialization_export.application.services.partial_revision import (
    revise_partial,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def plan_for(capture):
    docs = {k: partial_document(capture, k) for k in ("student", "correction")}
    plan = {
        "schema": "V2-PARTIAL-LOCAL-REVISION-1.0",
        "id": "SYNTHETIC-312",
        "source_sha256": capture.request.text_sha256,
        "base_projection_sha256": fingerprint({k: d.as_dict() for k, d in docs.items()}),
        "changes": [
            {
                "views": ["student", "correction"],
                "block_index": 4,
                "before_sha256": hashlib.sha256(
                    docs["student"].blocks[4].text.encode()
                ).hexdigest(),
                "text": "NEW_LOCAL_CONTEXT",
                "reason": "Synthetic explicit edit",
            }
        ],
        "insertions": [
            {
                "views": ["student", "correction"],
                "after_block_index": 5,
                "blocks": [{"style": "Note", "text": "NEW_LOCAL_TYPOLOGY"}],
                "tables": [
                    {"after_block_index": 0, "rows": [["Type", "Evidence"], ["Synthetic", "Case"]]}
                ],
                "reason": "Synthetic addition",
            }
        ],
        "table_changes": [],
        "heights": [{"table_index": 2, "twips": 900}],
        "teacher_append": [{"style": "Normal", "text": "ONLY_NEW_LOCAL_ANSWER_NOT_PROVIDER"}],
    }
    return docs, plan


def test_revision_preserves_capture_and_history_separates_student_and_heights(capture):
    before = capture.text
    docs, plan = plan_for(capture)
    derived, trace = revise_partial(docs, plan, capture.request.text_sha256)
    assert capture.text == before and trace["capture_unchanged"]
    for kind, d in derived.items():
        assert d.blocks[0] == docs[kind].blocks[0] and d.blocks[2] == docs[kind].blocks[2]
        assert len(d.tables) == 7
        text = "\n".join(b.text for b in d.blocks)
        assert "NEW_LOCAL_CONTEXT" in text and "NEW_LOCAL_TYPOLOGY" in text
        assert ("ONLY_NEW_LOCAL_ANSWER" in text) == (kind == "correction")
        if kind == "correction":
            assert "TEACHER_ONLY_INTERRUPTED" in text
            assert text.count("Réponse non capturée") == 2
            assert "Proposition non validée — non issue de la réponse fournisseur." in text
        with ZipFile(BytesIO(Lot1OOXMLWordWriter().write(d))) as z:
            xml = ET.fromstring(z.read("word/document.xml"))
            heights = xml.findall(".//" + W + "trHeight")
            assert all(
                t.find(W + "tr/" + W + "tc/" + W + "p/" + W + "pPr/" + W + "keepNext") is not None
                for t in xml.findall(".//" + W + "tbl")
            )
            assert heights and all(
                n.get(W + "hRule") == "atLeast" and n.get(W + "val") == "900" for n in heights
            )
    assert all(not d.table_min_row_heights for d in docs.values())


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "base",
        "before",
        "duplicate",
        "protected",
        "height_bool",
        "height_large",
        "extra",
        "append_missing",
    ],
)
def test_revision_refuses_wrong_identity_conflicts_protected_blocks_and_bad_height(
    capture, mutation
):
    docs, plan = plan_for(capture)
    if mutation == "source":
        plan["source_sha256"] = "0" * 64
    if mutation == "base":
        plan["base_projection_sha256"] = "0" * 64
    if mutation == "before":
        plan["changes"][0]["before_sha256"] = "0" * 64
    if mutation == "duplicate":
        plan["changes"].append(copy.deepcopy(plan["changes"][0]))
    if mutation == "protected":
        plan["changes"][0]["block_index"] = 0
    if mutation == "height_bool":
        plan["heights"][0]["twips"] = True
    if mutation == "height_large":
        plan["heights"][0]["twips"] = 9000
    if mutation == "extra":
        plan["status"] = "VALIDATED"
    if mutation == "append_missing":
        plan["teacher_append"] = []
    with pytest.raises(ValueError):
        revise_partial(docs, plan, capture.request.text_sha256)


def test_pinned_revision_save_reopen_inventory_and_tampering_without_effects(tmp_path, capture):
    manifest, _ = artifacts(tmp_path, capture)
    _, plan = plan_for(capture)
    revision = manifest.parent / "revision.json"
    revision.write_text(json.dumps(plan), encoding="utf-8")
    content = json.loads(manifest.read_bytes())
    content["local_revision"] = {"file": revision.name, "sha256": digest(revision.read_bytes())}
    manifest.write_text(json.dumps(content), encoding="utf-8")
    pin = digest(manifest.read_bytes())
    root = tmp_path / "library312"
    instance = build_local_saved(
        LocalBrowserHttpConfiguration(port=port()),
        root,
        create=True,
        partial_manifest=manifest,
        partial_manifest_sha256=pin,
    )
    source_bytes = (manifest.parent / "text.txt").read_bytes()
    try:
        opened = json.loads(send(instance)[2])["data"]
        assert not opened["saved"] and not opened["effect_permitted"] and opened["revision"]
        body = {
            "source_sha256": capture.request.text_sha256,
            "projection_sha256": opened["projection_sha256"],
        }
        assert send(instance, "POST", "/save", body)[0] == 403
        assert (
            send(instance, "POST", "/save", body, {"x-r2-nonce": opened["transport_nonce"]})[0]
            == 200
        )
        inv = json.loads(send(instance, path="/inventory")[2])["data"]
        assert inv["capture_inventory"]["complete_answers"] == 3
        assert inv["capture_inventory"]["missing"] == [
            "Q1-4 incomplete",
            "Q1-5 absent",
            "Q1-6 absent",
        ]
        assert inv["revision"]["new_answers_origin"] == "LOCAL_UNVALIDATED_NOT_PROVIDER"
        assert send(instance, path="/word/student")[0] == 200
    finally:
        instance.close()
    reopened = build_local_saved(
        LocalBrowserHttpConfiguration(port=port()),
        root,
        partial_manifest=manifest,
        partial_manifest_sha256=pin,
    )
    try:
        state = json.loads(send(reopened)[2])["data"]
        assert state["saved"] and state["version_ref"] == opened["version_ref"]
        descriptor = (root / "captured-partial-native-tables-v1.json").read_bytes()
        revision.write_text("{}", encoding="utf-8")
        assert send(reopened)[0] == 409 and send(reopened, path="/word/correction")[0] == 409
        assert (root / "captured-partial-native-tables-v1.json").read_bytes() == descriptor
        assert (manifest.parent / "text.txt").read_bytes() == source_bytes
    finally:
        reopened.close()
