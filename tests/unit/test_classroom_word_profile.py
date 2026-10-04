from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.classroom_word import W
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.modules.materialization_export.contracts.dto.lot1_word_table import (
    Lot1WordDocument,
    Lot1WordTable,
)
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)


def parts(document: WordDocument) -> dict[str, bytes]:
    with ZipFile(BytesIO(R6ReadableWordWriter().write(document))) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.mark.parametrize("kind", ["student", "correction", "marking"])
def test_profile_preserves_amounts_operators_and_unmatched_markers(kind: str) -> None:
    doc = WordDocument(kind, "FICTIF / À VALIDER", (
        WordBlock("Normal", "## Calcul\n**FRNG** = 570 − 443 = 127 k€\n*Contrôle* : FRNG - BFR = TN\nvaleur_brute * 2 ; 4*5 ; x_y ; **incomplet\n`code_unique`"),
        WordBlock("Note", "Version exacte : ver:" + "a" * 32),
        WordBlock("Note", "Données fictives. Aucun référentiel officiel attesté."),
    ))
    before = doc.as_dict()
    raw = parts(doc)
    root = ET.fromstring(raw["word/document.xml"])
    text = "\n".join("".join(node.itertext()) for node in root.iter(W + "p"))
    for required in ["570 − 443 = 127 k€", "FRNG - BFR = TN", "valeur_brute * 2 ; 4*5 ; x_y ; **incomplet", "code_unique", "Données fictives."]:
        assert required in text
    assert "ver:" not in text and "## Calcul" not in text and "**FRNG**" not in text
    assert root.find(".//" + W + "b") is not None
    assert root.find(".//" + W + "i") is not None
    assert doc.as_dict() == before
    assert parts(doc) == raw  # Deterministic artifact identities.
    assert b"NUMPAGES" in raw["word/footer1.xml"]
    assert root.find(".//" + W + "pgSz").get(W + "w") == "11906"  # type: ignore[union-attr]


def test_native_table_and_multiline_emphasis_preserve_all_cells() -> None:
    doc = Lot1WordDocument("student", "Sujet", (WordBlock("Normal", "**Première ligne**\nDeuxième ligne"),),
                          (Lot1WordTable(0, (("Poste", "Valeur"), ("Actif", "443"))),))
    root = ET.fromstring(parts(doc)["word/document.xml"])
    assert len(root.findall(".//" + W + "tbl")) == 1
    assert root.find(".//" + W + "br") is not None
    assert [node.text for node in root.iter(W + "t")] == ["Sujet", "Première ligne", None, "Deuxième ligne", "Poste", "Valeur", "Actif", "443"]


def test_technical_looking_business_text_is_not_silently_removed() -> None:
    doc = WordDocument("student", "Cours", (WordBlock("Normal", "Version exacte : ver:" + "b" * 32),))
    assert b"ver:" in parts(doc)["word/document.xml"]


def test_unknown_presentation_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="R6_WORD_PROFILE_REJECTED"):
        R6ReadableWordWriter(profile="other")
