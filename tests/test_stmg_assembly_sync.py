"""Public synthetic coverage; private 321/golden media are deliberately not published."""

from copy import deepcopy
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.inbound.application.chapter_assembly import ChapterAssemblyInbound
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_context.contracts.dto.p0_context import (
    P0_COURSE_CONTEXT_CONTRACT,
    P0Context,
)
from backend.modules.pedagogical_design.application.commands.assemble_chapter import AssembleChapter
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
)
from backend.modules.pedagogical_design.application.services.codesign_media import (
    require_codesign_media_parent,
)
from tests.synthetic_chapter_sync import blueprint, prepare


def test_assembly_draft_does_not_acquire_institutional_or_media_authority():
    value = blueprint()
    value["context"].update(contract_id=P0_COURSE_CONTEXT_CONTRACT, course_format="CHAPTER")
    value["context"]["local_progression"] = {"chapter": "1", "sequence": None, "week": None}
    value["identity"]["lineage"]["context_sha256"] = P0Context(value["context"]).sha256
    from backend.adapters.outbound.export.local_media import WindowsLocalDiagramRenderer
    from backend.modules.materialization_export.application.services.media_asset import (
        MediaAssetWorker,
    )
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
    from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
    from tests.unit.test_course_media import brief_data

    brief = VisualBrief(brief_data(value["identity"]["production_ref"]))
    asset = MediaAssetWorker(WindowsLocalDiagramRenderer()).execute(brief)
    value["chapter"].update(visual_briefs=[as_plain(brief.data)], media_assets=[as_plain(asset.data)])
    bundle = ChapterAssemblyInbound(AssembleChapter()).prepare(value, {}).p0_bundle
    assert bundle.context.data["institutional_resolution"]["status"] == "CONTENT_GAP"
    with pytest.raises(ValueError, match="INSTITUTIONAL_CONTENT_GAP"):
        CreateP0Candidate.validate_content(bundle)
    with pytest.raises(ValueError, match="CHAPTER_MEDIA_REBIND_REQUIRED"):
        require_codesign_media_parent(bundle)


def test_synthetic_assembly_save_reopen_edit_two_words(tmp_path):
    parent = prepare()
    assert not parent.data["reviews"] and not parent.data["validations"]
    saved = build_saved_application(tmp_path / "synthetic-library", create=True, source=lambda *_: parent, word_profile="product-v7")
    refs = {"production_ref": parent.production_ref, "version_ref": parent.version_ref}
    saved.execute("save", body=refs, correlation="synthetic-sync")
    reopened = build_saved_application(tmp_path / "synthetic-library", word_profile="product-v7")
    assert reopened.read_local_p0(**refs).sha256 == parent.sha256
    texts = {}
    for kind in ("student", "correction"):
        raw = reopened.execute("word", **refs, kind=kind, correlation="synthetic-sync")
        with ZipFile(BytesIO(raw)) as archive:
            texts[kind] = " ".join(ET.fromstring(archive.read("word/document.xml")).itertext())
    assert "ORACLE_PROF_1" not in texts["student"] and "ORACLE_PROF_1" in texts["correction"]
    assert "Sources et choix pédagogiques" not in texts["student"]
    assert "Un indice synthétique justifié" in texts["correction"]
    child = saved.execute("edit", parent.production_ref, parent.version_ref,
        body={"action_id": "action:" + "a" * 32, "record_sha256": parent.sha256, "question_id": "Q1",
              "prompt": "Relevez deux indices synthétiques.", "expected_answer": "Deux indices du document fictif.",
              "rationale": "Explication locale indépendante."}, correlation="synthetic-sync")
    assert child["parent_version_ref"] == parent.version_ref
    assert reopened.read_local_p0(parent.production_ref, parent.version_ref).sha256 == parent.sha256


@pytest.mark.parametrize("mutation,code", [("question", "QUESTION"), ("source", "PROVENANCE"), ("format", "FORMAT_IDENTITY")])
def test_synthetic_assembly_refuses_broken_graph_or_unadopted_format(mutation, code):
    value = deepcopy(blueprint())
    if mutation == "question":
        value["chapter"]["parts"][0]["analysis"] = ["Q99"]
    elif mutation == "source":
        value["chapter"]["documents"][0]["provenance"]["source_ref"] = "not-selected"
    else:
        value["chapter"]["assembly"]["format_reference"]["version_ref"] = "unadopted"
    with pytest.raises(ValueError, match=code):
        ChapterAssemblyInbound(AssembleChapter()).prepare(value, {})
