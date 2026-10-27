"""316 targeted export regression; no supplier, incident store or credentials."""

import json
import os
import shutil
import subprocess
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_partial_revision import plan_for
from test_partial_workspace import capture as capture  # noqa: PLC0414 -- pytest fixture re-export

from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter
from backend.adapters.outbound.export.stmg_reference_word import (
    CT,
    PKG,
    STMGReferenceWordWriter,
    _opc_xml,
)
from backend.modules.materialization_export.application.services.partial_projection import (
    partial_document,
)
from backend.modules.materialization_export.application.services.partial_revision import (
    revise_partial,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def writer():
    return STMGReferenceWordWriter(
        {
            k: "Synthetic " + k
            for k in ("level", "theme", "chapter", "question", "finality", "notions")
        },
        {"reference_id": "V2-FORMAT-TEST-001", "revision": "1.2"},
    )


def shape(element):
    return (element.tag, element.attrib, element.text, [shape(c) for c in element])


@pytest.mark.parametrize(
    "namespace,root_name,child,attributes",
    [
        (
            PKG,
            "Relationships",
            "Relationship",
            {"Id": "r1", "Type": "urn:style", "Target": "styles.xml"},
        ),
        (
            CT,
            "Types",
            "Override",
            {"PartName": "/word/document.xml", "ContentType": "application/test"},
        ),
    ],
)
def test_opc_default_namespace_preserves_qnames_values_and_global_registry(
    namespace, root_name, child, attributes
):
    root = ET.Element("{" + namespace + "}" + root_name)
    ET.SubElement(root, "{" + namespace + "}" + child, attributes)
    registry = ET._namespace_map.copy()
    raw = _opc_xml(root, namespace)
    assert b"ns0:" not in raw and (b'xmlns="' + namespace.encode() + b'"') in raw
    assert shape(ET.fromstring(raw)) == shape(root)
    assert ET._namespace_map == registry
    with pytest.raises(ValueError):
        _opc_xml(root, "urn:other")


def test_raw_student_opc_custom_metadata_blue_titles_and_no_pedagogical_loss(capture):
    base, plan = plan_for(capture)
    docs, _ = revise_partial(base, plan, capture.request.text_sha256)
    document = docs["student"]
    raw = writer().write(document)
    with ZipFile(BytesIO(raw)) as archive:
        for name in ("[Content_Types].xml", "word/_rels/document.xml.rels", "_rels/.rels"):
            assert b"ns0:" not in archive.read(name)
        root = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = root.findall(".//" + W + "body/" + W + "p")
        title = "".join(paragraphs[0].itertext())
        visible = "".join(root.itertext())
        assert title == "Cours synthétique"
        assert "BROUILLON PARTIEL NON VALIDÉ" in visible
        assert "SHA256" not in visible and "Révision locale" not in visible
        assert capture.request.command_id not in visible
        assert "TEACHER_ONLY" not in visible and "ONLY_NEW_LOCAL_ANSWER" not in visible
        props = ET.fromstring(archive.read("docProps/custom.xml"))
        metadata = {p.attrib["name"]: p[0].text for p in props}
        assert len({p.attrib["pid"] for p in props}) == len(props) == 3
        assert metadata["V2OriginalTitle"] == document.title
        internal = json.loads(metadata["V2InternalNotes"])
        assert [n["block_index"] for n in internal] == [1, 2, 3]
        assert any(capture.request.command_id in n["text"] for n in internal)
        for index, block in enumerate(document.blocks):
            assert (
                (block.text in {n["text"] for n in internal})
                if index in {1, 2, 3}
                else block.text.replace("\n", "") in visible
            )
        with ZipFile(BytesIO(Lot1OOXMLWordWriter().write(document))) as baseline:
            old = ET.fromstring(baseline.read("word/document.xml"))
            def matrices(tree):
                return [
                    [["".join(c.itertext()) for c in r.findall(W + "tc")] for r in t.findall(W + "tr")]
                    for t in tree.findall(".//" + W + "tbl")
                ]
            assert matrices(root) == matrices(old)
        styles = ET.fromstring(archive.read("word/styles.xml"))
        for name in ("Heading1", "Heading2"):
            style = next(s for s in styles if s.get(W + "styleId") == name)
            assert style.find(W + "rPr/" + W + "color").get(W + "val") == "4F81BD"
        for name in archive.namelist():
            if name.endswith(".rels"):
                rels = ET.fromstring(archive.read(name))
                assert len({r.attrib["Id"] for r in rels}) == len(rels)
                assert all(r.get("TargetMode") != "External" for r in rels)
        assert not any(n.startswith("word/media/") for n in archive.namelist())
    teacher = docs["correction"]
    assert writer().write(teacher) == Lot1OOXMLWordWriter().write(teacher)


def test_rejects_unrecognized_provenance_without_hiding_notes(capture):
    from dataclasses import replace

    from backend.modules.materialization_export.contracts.dto.word_document import WordBlock

    document = partial_document(capture, "student")
    blocks = list(document.blocks)
    blocks[2] = WordBlock("Note", "A PEDAGOGICAL NOTE THAT MUST NOT BE SILENTLY REMOVED")
    with pytest.raises(ValueError, match="PROVENANCE_SHAPE"):
        writer().write(replace(document, blocks=tuple(blocks)))


def test_raw_docx_in_secondary_engine_when_available(tmp_path, capture):
    engine = shutil.which("soffice")
    if engine is None:
        pytest.skip("SECONDARY_DOCX_ENGINE_NOT_INSTALLED: Word qualification is separate")
    path = tmp_path / "raw_student.docx"
    path.write_bytes(writer().write(partial_document(capture, "student")))
    output = tmp_path / "pdf"
    output.mkdir()
    env = {
        k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH") if k in os.environ
    }
    run = subprocess.run(
        [
            engine,
            "-env:UserInstallation=" + (tmp_path / "lo-profile").as_uri(),
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output),
            str(path),
        ],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert run.returncode == 0 and (output / "raw_student.pdf").is_file()
