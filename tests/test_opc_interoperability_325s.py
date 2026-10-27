"""OPC-only representation fix; baseline sources and original documents stay intact."""
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.opc_xml import opc_xml
from backend.adapters.outbound.export.product_word import ProductWordWriter
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.adapters.outbound.export.stmg_reference_word import _opc_xml
from backend.modules.materialization_export.contracts.dto.media_asset import CourseMedia
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
    WordMedia,
)

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
OPC = {"[Content_Types].xml": CT, "word/_rels/document.xml.rels": PKG}


def sample(kind="student", *, media=False):
    blocks = (WordBlock("Heading1", "Observation"),
              WordBlock("Normal", "FICTIF : distinguer un fait d’une interprétation."),
              WordBlock("Heading2", "Question 1"),
              WordBlock("Normal", "Quel fait est observable ?"))
    if kind == "correction":
        blocks += (WordBlock("Normal", "Réponse professeur synthétique : citer les informations."),)
    attachments = ()
    if media:
        from tests.unit.test_course_media import media_chapter

        _, _, brief, asset = media_chapter()
        pair = CourseMedia(brief, asset)
        attachments = (WordMedia("Question 1", pair),)
    return WordDocument(kind, "Qualification OPC synthétique", blocks, production_media=attachments)


@pytest.mark.parametrize("namespace,root_name,child_name", [(CT, "Types", "Override"), (PKG, "Relationships", "Relationship")])
def test_default_namespace_roundtrip_no_input_or_global_mutation(namespace, root_name, child_name):
    root = ET.Element("{" + namespace + "}" + root_name)
    root.text = "texte & <é>"
    child = ET.SubElement(root, "{" + namespace + "}" + child_name, {"Target": "média & image.png"})
    child.tail = " fin "
    before = ET.tostring(root)
    registry = dict(ET._namespace_map)
    raw = opc_xml(root, namespace)
    assert b'xmlns="' + namespace.encode() + b'"' in raw and b"ns0:" not in raw
    assert ET.tostring(ET.fromstring(raw)) == before
    assert ET.tostring(root) == before and dict(ET._namespace_map) == registry


def test_foreign_namespace_refused_and_stmg_error_kept():
    root = ET.Element("{" + CT + "}Types")
    ET.SubElement(root, "{urn:foreign}Child")
    with pytest.raises(ValueError, match="^OPC_XML_NAMESPACE$"):
        opc_xml(root, CT)
    with pytest.raises(ValueError, match="^FORMAT_REFERENCE_OPC_NAMESPACE$"):
        _opc_xml(root, CT)


@pytest.mark.parametrize("kind,media", [("student", False), ("correction", False), ("student", True), ("correction", True)])
@pytest.mark.skipif(not os.environ.get("V2_325S_BASELINE_SOURCE"),
                    reason="Historical 325 R3 source archive required for byte comparison")
def test_only_two_opc_parts_change_from_r3(kind, media, tmp_path):
    baseline = Path(os.environ["V2_325S_BASELINE_SOURCE"])
    code = '''import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("fixture325s",sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
d=m.sample(sys.argv[3],media=sys.argv[4]=="True")
w=m.ProductWordWriter() if sys.argv[4]=="True" else m.R6ReadableWordWriter(profile="diffusion-v6")
Path(sys.argv[2]).write_bytes(w.write(d))
'''
    environment = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "TEMP", "TMP") if k in os.environ}
    environment.update(PYTHONPATH=str(baseline), PYTHONDONTWRITEBYTECODE="1")
    # The new fixture imports the helper absent from R3. Alias only that unused
    # test import; all three baseline writers and their dependencies stay real.
    prelude = 'import types,sys;m=types.ModuleType("backend.adapters.outbound.export.opc_xml");m.opc_xml=None;sys.modules[m.__name__]=m\n'
    old = tmp_path / "before.docx"
    subprocess.run([sys.executable, "-c", prelude + code, __file__, str(old), kind, str(media)],
                   cwd=baseline, env=environment, check=True, capture_output=True, timeout=45)
    document = sample(kind, media=media)
    new = (ProductWordWriter() if media else R6ReadableWordWriter(profile="diffusion-v6")).write(document)
    with ZipFile(old) as before, ZipFile(BytesIO(new)) as after:
        assert before.namelist() == after.namelist()
        changed = {name for name in before.namelist() if before.read(name) != after.read(name)}
        assert changed == set(OPC)
        for name, namespace in OPC.items():
            assert ET.tostring(ET.fromstring(before.read(name))) == ET.tostring(ET.fromstring(after.read(name)))
            assert b'xmlns="' + namespace.encode() + b'"' in after.read(name)
        for name in before.namelist():
            a, b = before.getinfo(name), after.getinfo(name)
            assert (a.date_time, a.compress_type, a.external_attr) == (b.date_time, b.compress_type, b.external_attr)
        if media:
            assert after.read("word/media/figure_1.png") == document.production_media[0].media.asset.raw
