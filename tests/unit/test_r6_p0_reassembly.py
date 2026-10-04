from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.pedagogical_design.application.commands.reassemble_p0_candidate import (
    DossierPartition,
    ReassembleP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from tests.unit.test_r6_p0_contract import production_data, saved_record


def source():
    data = production_data("ASSESSMENT")
    data["sections"].append({"section_id": "S_DOSSIER_1", "heading": "Dossier 1",
                             "text": "Durée donnée : 60 minutes.\n\nJustifiez votre réponse."})
    return P0Production(data)


def plan():
    return (DossierPartition("S_DOSSIER_1", (("Q01", len("Durée donnée : 60 minutes.\n\n")),)),)


def test_reassembly_preserves_parent_annexes_teacher_fields_and_exact_lineage(tmp_path):
    parent = source()
    original_sha = parent.sha256
    child = ReassembleP0Candidate().execute(parent, expected_sha256=parent.sha256,
        version_ref="ver:" + "9" * 32, partitions=plan())
    assert parent.sha256 == original_sha
    for field in ("context", "references", "corrections", "marking"):
        assert parent.data[field] == child.data[field]
    assert child.data["sections"][0] == parent.data["sections"][0]
    assert child.data["lineage"]["parent_version_ref"] == parent.version_ref
    records = {p.version_ref: saved_record(p) for p in (parent, child)}
    root = tmp_path / "saved"
    app = build_saved_application(root, create=True, source=lambda p, v: records[v])
    app.execute("save", body={"production_ref":child.production_ref,
                "version_ref":child.version_ref}, correlation="assembly.save")
    fresh = build_saved_application(root)
    writer = ExportSavedCommand(R6ReadableWordWriter())
    for p in (parent, child):
        assert fresh.execute("open", p.production_ref, p.version_ref,
            correlation="assembly.reopen")["record_sha256"] == records[p.version_ref].sha256
    for kind in ("student", "correction", "marking"):
        raw = fresh.execute("word", child.production_ref, child.version_ref,
                             kind=kind, correlation="assembly.export")
        with ZipFile(BytesIO(raw)) as archive:
            text = "\n".join(ElementTree.fromstring(archive.read("word/document.xml")).itertext())
        if kind == "student":
            assert text.count("Justifiez votre réponse.") == 1
            assert text.index("Durée donnée") < text.index("Question 1")
            assert "Q01" not in text and child.version_ref not in text
            assert "Réponse justifiée." not in text
        else:
            # Same teacher fields, only the exact version note legitimately changes.
            assert writer.preview(records[parent.version_ref], kind).blocks[2:] == \
                   writer.preview(records[child.version_ref], kind).blocks[2:]


@pytest.mark.parametrize("mutation,code", [
    ("hash", "P0_ASSEMBLY_SOURCE_IDENTITY"),
    ("section", "P0_ASSEMBLY_PARTITIONS"),
    ("offset", "P0_ASSEMBLY_OFFSETS"),
    ("question", "P0_ASSEMBLY_QUESTION_LINK"),
    ("duplicate", "P0_ASSEMBLY_OFFSETS"),
    ("same_version", "P0_LINEAGE_PARENT"),
])
def test_reassembly_refuses_mutated_identity_partition_or_lineage(mutation, code):
    parent = source()
    expected, version, parts = parent.sha256, "ver:" + "9" * 32, plan()
    if mutation == "hash":
        expected = "0" * 64
    if mutation == "section":
        parts = (DossierPartition("S_MISSING", (("Q01", 3),)),)
    if mutation == "offset":
        parts = (DossierPartition("S_DOSSIER_1", (("Q01", -1),)),)
    if mutation == "question":
        parts = (DossierPartition("S_DOSSIER_1", (("Q99", 3),)),)
    if mutation == "duplicate":
        parts = (DossierPartition("S_DOSSIER_1", (("Q01", 3), ("Q01", 3))),)
    if mutation == "same_version":
        version = parent.version_ref
    with pytest.raises(ValueError, match=code):
        ReassembleP0Candidate().execute(parent, expected_sha256=expected,
            version_ref=version, partitions=parts)


def test_export_refuses_dangling_presentation_link():
    data = production_data("ASSESSMENT")
    data["sections"][0]["section_id"] = "S_BEFORE_Q99"
    record = saved_record(P0Production(data))
    with pytest.raises(ValueError, match="P0_ASSEMBLY_QUESTION_LINK"):
        ExportSavedCommand(R6ReadableWordWriter()).preview(record, "student")
