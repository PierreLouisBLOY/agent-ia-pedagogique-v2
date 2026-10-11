from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.classroom_word import W
from backend.adapters.outbound.export.diffusion_word_v6 import (
    diffusion_v6_document,
    diffusion_v6_text,
)
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.modules.materialization_export.contracts.dto.lot1_word_table import (
    Lot1WordDocument,
    Lot1WordTable,
)
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)


@pytest.mark.parametrize("phrase", ["convention pilote", "convention du pilote", "Convention du pilote"])
def test_literal_wording_retains_amounts_answers_and_origin(phrase):
    doc = WordDocument("correction", "Corrigé", (WordBlock("Normal",
        "Selon la " + phrase + ", 1 200 − 900 = 300 €. Le passage SQLite sélectionné donne la méthode."),))
    old = doc.as_dict()
    projected = diffusion_v6_document(doc)
    assert "de l’exercice" in projected.blocks[0].text
    assert "SQLite" not in projected.blocks[0].text
    assert "1 200 − 900 = 300 €" in projected.blocks[0].text
    assert doc.as_dict() == old
    assert diffusion_v6_document(projected) == projected
    assert "SQLite" in diffusion_v6_text("passage SQLite sélectionné", kind="student")


def test_explicit_v6_course_spacing_changes_no_words_fonts_or_other_profiles():
    doc = WordDocument("student", "Document élève", (WordBlock("Heading1", "Cours"),
                                                WordBlock("Normal", "Entreprise, association, 20 points.")))
    raws = {profile: R6ReadableWordWriter(profile=profile).write(doc)
            for profile in ("diffusion-v5", "diffusion-v6")}
    roots = {}
    for profile, raw in raws.items():
        with ZipFile(BytesIO(raw)) as z:
            roots[profile] = ET.fromstring(z.read("word/styles.xml"))
            text = ET.fromstring(z.read("word/document.xml"))
        assert [node.text for node in text.iter(W + "t")] == [
            "Document élève", "Cours", "Entreprise, association, 20 points."]
        assert roots[profile].find("./" + W + "style[@"+W+"styleId='Normal']/"+W+"rPr/"+W+"sz").get(W+"val") == "23"
    assert roots["diffusion-v6"].find(".//"+W+"spacing").get(W+"after") == "80"
    assert roots["diffusion-v5"].find(".//"+W+"spacing").get(W+"after") == "140"
    assert R6ReadableWordWriter(profile="diffusion-v6").write(doc) == raws["diffusion-v6"]
    ordinary = WordDocument("student", "Exercice", (WordBlock("Normal", "Montant : 20 €."),))
    assert R6ReadableWordWriter(profile="diffusion-v6").write(ordinary) == R6ReadableWordWriter(profile="diffusion-v5").write(ordinary)


def test_native_table_anchors_and_numeric_cells_are_preserved():
    doc = Lot1WordDocument("student", "Tableau", (WordBlock("Normal", "convention pilote"),),
                          (Lot1WordTable(0, (("Débit", "Crédit"), ("1200", "900"))),))
    projected = diffusion_v6_document(doc)
    assert projected.tables == doc.tables
    with ZipFile(BytesIO(R6ReadableWordWriter(profile="diffusion-v6").write(doc))) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    assert len(root.findall(".//"+W+"tbl")) == 1
    assert "1200" in [node.text for node in root.iter(W+"t")]
