from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.word import OOXMLWordWriter
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from tests.support.r4_synthetic import record


@pytest.mark.parametrize("kind", ["student", "correction", "marking"])
def test_deterministic_complete_word_and_no_external_or_hidden_parts(kind):
    value = record(imported=True)
    command = ExportSavedCommand(OOXMLWordWriter())
    raw = command.execute(value, kind)
    assert raw == command.execute(value, kind)
    with ZipFile(BytesIO(raw)) as archive:
        assert set(archive.namelist()) == {"[Content_Types].xml", "_rels/.rels", "word/document.xml",
                                         "word/styles.xml", "word/_rels/document.xml.rels"}
        for name in archive.namelist():
            ET.fromstring(archive.read(name))
            assert b'TargetMode="External"' not in archive.read(name)
            assert b"vanish" not in archive.read(name)
        text = "\n".join(ET.fromstring(archive.read("word/document.xml")).itertext())
        for block in command.preview(value, kind).blocks:
            assert block.text in text
        if kind == "student":
            for answer in value.bundle.data["correction"]["answers"]:
                assert answer["expected_answer"] not in text
                assert answer["rationale"] not in text
            assert "CANDIDATE" not in text and "validation_ref" not in text
        else:
            assert "NON VALIDÉE" in text and "A16" in text and "Réserve artificielle" in text


def test_complete_answer_and_rationale_not_sliced_by_locator():
    value = record()
    data = value.mutable_copy()
    answer = data["bundle"]["correction"]["answers"][0]
    answer["expected_answer"] = "Texte intégral avant — 100000.00 EUR — fin indispensable."
    answer["rationale"] = "Justification complète : aucun découpage par un locator obsolète."
    from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
    output = ExportSavedCommand(OOXMLWordWriter()).preview(SavedProduction(data), "correction")
    assert answer["expected_answer"] in [b.text for b in output.blocks]
    assert answer["rationale"] in [b.text for b in output.blocks]


def test_invalid_xml_characters_are_rejected_not_silently_changed():
    from backend.modules.materialization_export.contracts.dto.word_document import (
        WordBlock,
        WordDocument,
    )
    document = WordDocument("student", "Version", (WordBlock("Normal", "texte\x00interdit"),))
    with pytest.raises(ValueError, match="XML_CHARACTER_REJECTED"):
        OOXMLWordWriter().write(document)
