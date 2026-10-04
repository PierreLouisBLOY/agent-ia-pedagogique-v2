from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.adapters.outbound.export.word import OOXMLWordWriter
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)


@pytest.mark.parametrize("kind", ["student", "correction", "marking"])
def test_table_cells_units_and_surrounding_text_survive_native_table_projection(kind: str) -> None:
    text = "Données fictives en k€\n| Poste | Brut | Net |\n| --- | ---: | ---: |\n| Actif | 570 | 443 |\n| Total | 570 | 443 |\nArrondir à une décimale."
    document = WordDocument(kind, "Document fictif", (WordBlock("Normal", text),))
    before = document.as_dict()
    payload = R6ReadableWordWriter().write(document)
    assert document.as_dict() == before
    with ZipFile(BytesIO(payload)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
        ns = {"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        tables = root.findall(".//w:tbl", ns)
        assert len(tables) == 1
        cells = [["".join(c.itertext()) for c in r.findall("w:tc", ns)]
                 for r in tables[0].findall("w:tr", ns)]
        assert cells == [["Poste", "Brut", "Net"], ["Actif", "570", "443"], ["Total", "570", "443"]]
        content = "\n".join(root.itertext())
        assert "Données fictives en k€" in content
        assert "Arrondir à une décimale." in content
        assert tables[0].find("w:tr/w:trPr/w:tblHeader", ns) is not None
        assert all(row.find("w:trPr/w:cantSplit", ns) is not None
                   for row in tables[0].findall("w:tr", ns))


@pytest.mark.parametrize("kind", ["student", "correction", "marking"])
def test_non_table_documents_remain_byte_identical(kind: str) -> None:
    doc = WordDocument(kind, "Document", (WordBlock("Normal", "FICTIF / À VALIDER\nTexte inchangé"),))
    assert R6ReadableWordWriter(profile="readable-v1").write(doc) == OOXMLWordWriter().write(doc)


@pytest.mark.parametrize("kind", ["student", "correction", "marking"])
def test_ragged_table_is_refused_without_discarding_cells(kind: str) -> None:
    doc = WordDocument(kind, "Document", (WordBlock("Normal", "| Poste | Valeur |\n| --- | --- |\n| A | 12 | donnée supplémentaire |"),))
    with pytest.raises(ValueError, match="LOT1_WORD_TABLE_REJECTED"):
        R6ReadableWordWriter().write(doc)
