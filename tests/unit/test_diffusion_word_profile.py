from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.diffusion_word import diffusion_document, diffusion_text
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)
from tests.unit.test_classroom_word_profile import parts


@pytest.mark.parametrize("marker", ["[S01]", "[C01–C06]", "[F02–F19, F24]", "[Sxx]", "[Cxx]", "[Fxx]", "[C03 ; F20]", "[C07 ; principe du cycle S04]", "[C04 ; données FICTIVES F05–F08, F17–F19, F21]"])
def test_closed_provenance_markers_do_not_remove_business_numbers(marker):
    assert diffusion_text("Valeur " + marker + " : 120 − 134 = −14,0 k€") == "Valeur : 120 − 134 = −14,0 k€"


def test_v5_removes_metadata_only_keeps_business_justification_and_legacy_v4():
    doc = WordDocument("correction", "FICTIF / À VALIDER", (
        WordBlock("Note", "CANDIDATE — NON VALIDÉE. Sauvegarder/exporter ne vaut pas valider."),
        WordBlock("Normal", "120 − 134 = −14,0 k€ [S05]"),
        WordBlock("Heading2", "Justification"),
        WordBlock("Normal", "Le besoin dépasse le financement stable de 14,0 k€."),
        WordBlock("Heading2", "Justification"),
        WordBlock("Normal", "Référence de correction exacte Atelier Boréal V2, question 1; résultats calculés sur les données fictives du cas."),
    ))
    original = doc.as_dict()
    raw = R6ReadableWordWriter(profile="diffusion-v5").write(doc)
    with ZipFile(BytesIO(raw)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        text = "\n".join(n.text or "" for n in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
    assert "Cas fictif" in text and "120 − 134 = −14,0 k€" in text
    assert "Le besoin dépasse le financement stable de 14,0 k€." in text
    assert "CANDIDATE" not in text and "Référence de correction" not in text and "[S05]" not in text
    assert doc.as_dict() == original and diffusion_document(diffusion_document(doc)) == diffusion_document(doc)
    assert b"CANDIDATE" in parts(doc)["word/document.xml"]
    assert R6ReadableWordWriter(profile="diffusion-v5").write(doc) == raw


def test_legitimate_application_method_and_business_brackets_stay_literal():
    assert diffusion_text("Application du taux [TVA] : 4*5 = 20; x_y") == "Application du taux [TVA] : 4*5 = 20; x_y"
