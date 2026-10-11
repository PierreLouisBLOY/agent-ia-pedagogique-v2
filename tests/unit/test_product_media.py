"""Declared synthetic catalogue and case data, no canonical admission or provider."""
import copy
import hashlib
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.inbound.application.production_media import ProductionMediaInbound
from backend.adapters.outbound.export.local_media import WindowsLocalDiagramRenderer
from backend.adapters.outbound.export.product_word import ProductWordWriter
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.materialization_export.application.services.media_asset import MediaAssetWorker
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.prepare_production_media import (
    PrepareProductionMediaCommand,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_policy import COURSE_SECTIONS
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.contracts.dto.production_media import ProductionMediaPlan
from tests.unit.test_course_media import brief_data
from tests.unit.test_r6_p0_contract import EVIDENCE_ID, EVIDENCE_TEXT, production_data, saved_record
from tests.unit.test_stmg_institutional_alignment import Catalog, app, context, prepare

FAMILIES = [("COURSE", None), ("EXERCISE", None), ("ASSESSMENT", None),
            ("QUESTION_SET", "QCM"), ("QUESTION_SET", "QUIZ"), ("QUESTION_SET", "OPEN_QUESTIONS")]


@pytest.mark.parametrize("kind", ["student", "correction", "marking"])
def test_product_fiction_title_habillage_is_removed_without_changing_declared_case_data(kind):
    source = WordDocument(kind, "Évaluation FICTIVE — Test de marge", (
        WordBlock("Normal", "Données FICTIVES : 100 unités, 30,00 €, 1 800,00 €, 700,00 €."),
        WordBlock("Normal", "CA : 3 000,00 € ; résultat : 500,00 € ; seuil : 1 750,00 €.")))
    raw = ProductWordWriter().write(source)
    with ZipFile(BytesIO(raw)) as archive:
        xml = ET.fromstring(archive.read("word/document.xml"))
        texts = [node.text for node in xml.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")]
    assert texts[0] == "Évaluation — Test de marge"
    assert texts[1:] == [block.text for block in source.blocks]
    assert source.title == "Évaluation FICTIVE — Test de marge"


def test_product_preview_and_export_title_match_and_source_identity_is_unchanged():
    data = production_data("ASSESSMENT")
    data["title"] = "Évaluation FICTIVE — Test de marge"
    data["sections"][0]["text"] = "Données FICTIVES : 100 unités à 30,00 €."
    record = saved_record(P0Production(data))
    before = record.sha256
    exporter = ExportSavedCommand(ProductWordWriter(), product_projection=True)
    for kind in ("student", "correction", "marking"):
        preview = exporter.preview(record, kind)
        with ZipFile(BytesIO(exporter.execute(record, kind))) as archive:
            xml = ET.fromstring(archive.read("word/document.xml"))
            title = next(xml.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")).text
        assert title == preview.title and "FICTIVE" not in title
    assert record.sha256 == before and record.p0_bundle.data["title"] == data["title"]


def test_product_title_does_not_remove_a_necessary_data_description():
    source = WordDocument("student", "Données fictives pour une simulation", (WordBlock("Normal", "100,00 €"),))
    with ZipFile(BytesIO(ProductWordWriter().write(source))) as archive:
        xml = ET.fromstring(archive.read("word/document.xml"))
        assert next(xml.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")).text == source.title


def media_fixture(kind="EXERCISE", mode=None):
    data = production_data(kind, mode)
    confirmed = prepare(app(Catalog()), context())["context"]
    confirmed.update(resource_type=kind, question_mode=mode,
                     duration_minutes=60 if kind == "ASSESSMENT" else None,
                     total_points=20 if kind == "ASSESSMENT" else None)
    exact = P0Context(confirmed)
    data.update(context=exact.as_dict(), context_sha256=exact.sha256)
    data["lineage"]["context_sha256"] = exact.sha256
    if kind == "COURSE":
        data["sections"] = [{"section_id": "S_" + role, "heading": role,
                              "text": "Un document synthétique de test pour " + role} for role in COURSE_SECTIONS]
    parent = saved_record(P0Production(data))
    brief = brief_data(parent.production_ref)
    brief.update(section_ref=data["sections"][0]["section_id"],
                 institutional_capability_ref="capacity:MANAGEMENT_PREMIERE")
    proposal = {"brief": brief, "required": True, "dependency_refs": ["section:" + brief["section_ref"]],
                "materialize": True, "admitted_bytes": None, "admission": None, "omission_reason": None}
    inbound = ProductionMediaInbound(PrepareProductionMediaCommand(MediaAssetWorker(WindowsLocalDiagramRenderer())))
    return parent, proposal, inbound


def child_fixture(kind="EXERCISE", mode=None):
    parent, proposal, inbound = media_fixture(kind, mode)
    return parent, inbound.execute(parent, [proposal], evidence={EVIDENCE_ID: EVIDENCE_TEXT})


@pytest.mark.parametrize("kind,mode", FAMILIES)
def test_six_families_keep_native_media_exact_bytes_and_separate_projections(kind, mode):
    parent, child = child_fixture(kind, mode)
    assert parent.p0_bundle.data["contract_id"] == "R6-P0-PRODUCTION-1.0"
    assert child.p0_bundle.data["contract_id"] == "R6-P0-PRODUCTION-MEDIA-3.0"
    assert child.p0_bundle.data["lineage"]["parent_version_ref"] == parent.version_ref
    assert child.production_ref == parent.production_ref and child.version_ref != parent.version_ref
    assert child.data["reviews"] == () and child.data["validations"][0]["media_controls"]["pixel_review"] == "NOT_RUN"
    plan = ProductionMediaPlan(as_plain(child.p0_bundle.data["media_plan"]))
    asset = plan.media("student")[0].asset
    exporter = ExportSavedCommand(ProductWordWriter(), product_projection=True)
    for audience in ("student", "correction", "marking"):
        raw = exporter.execute(child, audience)
        with ZipFile(BytesIO(raw)) as archive:
            assert archive.read("word/media/figure_1.png") == asset.raw
            root = ET.fromstring(archive.read("word/document.xml"))
            text = "\n".join(root.itertext())
            assert "Repères pour observer la situation" in text
            assert "Version exacte" not in text and "CANDIDATE" not in text and "sha256" not in text
            assert "TargetMode=\"External\"" not in archive.read("word/_rels/document.xml.rels").decode()
            if audience == "student" and kind != "COURSE":
                assert "Les critères sont explicitement reliés" not in text
            assert hashlib.sha256(asset.raw).hexdigest() == asset.data["png_sha256"]
    assert child.p0_bundle.student_projection()["media_assets"][0]["png_sha256"] == asset.data["png_sha256"]


@pytest.mark.parametrize("kind,mode", FAMILIES)
def test_no_media_is_a_complete_justified_choice_for_all_families(kind, mode):
    parent, _, inbound = media_fixture(kind, mode)
    child = inbound.execute(parent, [], evidence={EVIDENCE_ID: EVIDENCE_TEXT},
                            no_media_reason="Les pièces et tableaux natifs suffisent au travail demandé.")
    assert child.view.data["media_assets"] == ()
    with ZipFile(BytesIO(ExportSavedCommand(ProductWordWriter()).execute(child, "student"))) as archive:
        assert not any(name.startswith("word/media/") for name in archive.namelist())
    with pytest.raises(ValueError):
        inbound.execute(parent, [], evidence={EVIDENCE_ID: EVIDENCE_TEXT})


@pytest.mark.parametrize("required", [False, True])
def test_absent_media_is_not_silently_required_or_silently_regenerated(required):
    parent, proposal, inbound = media_fixture()
    proposal.update(required=required, materialize=False, omission_reason="Pièce PNG admise encore indisponible.")
    proposal["brief"]["teacher_visibility"] = False
    child = inbound.execute(parent, [proposal], evidence={EVIDENCE_ID: EVIDENCE_TEXT})
    exporter = ExportSavedCommand(ProductWordWriter())
    if required:
        with pytest.raises(ValueError, match="PRODUCTION_MEDIA_REQUIRED_MISSING"):
            exporter.execute(child, "student")
    else:
        with ZipFile(BytesIO(exporter.execute(child, "student"))) as archive:
            assert not any(name.startswith("word/media/") for name in archive.namelist())
    assert exporter.execute(child, "correction").startswith(b"PK")
    assert child.p0_bundle.data["media_plan"]["entries"][0]["omission_reason"] == proposal["omission_reason"]


@pytest.mark.parametrize("mutation", ["content", "context_hash", "version", "anchor", "notion", "capability", "answer", "correction_dependency"])
def test_substitution_and_stale_dependencies_fail_closed(mutation):
    _, child = child_fixture()
    data = child.p0_bundle.mutable_copy()
    entry = data["media_plan"]["entries"][0]
    if mutation == "content":
        data["sections"][0]["text"] += " Donnée corrigée."
    elif mutation == "context_hash":
        data["media_plan"]["context_sha256"] = "0" * 64
    elif mutation == "version":
        data["version_ref"] = "ver:" + "9" * 32
    elif mutation == "correction_dependency":
        from backend.modules.pedagogical_design.contracts.dto.production_media import dependencies
        entry["dependencies"]["correction:Q01"] = dependencies(data)["correction:Q01"]
    else:
        key, value = {"anchor": ("section_ref", "S_MISSING"), "notion": ("notion_refs", ["notion:wrong"]),
                      "capability": ("institutional_capability_ref", "capacity:wrong"),
                      "answer": ("alt_text", data["corrections"][0]["expected_answer"])}[mutation]
        entry["brief"][key] = value
        # Keep the asset absent so the mutated brief is checked independently of asset binding.
        entry.update(asset=None, omission_reason="Pièce à préparer.")
    with pytest.raises(ValueError):
        P0Production(data)


def test_teacher_variant_is_not_in_student_snapshot_or_docx_metadata():
    parent, proposal, inbound = media_fixture()
    proposal["brief"].update(student_visibility=False, teacher_visibility=True,
                              caption="Réponse justifiée.", alt_text="Réponse justifiée.")
    child = inbound.execute(parent, [proposal], evidence={EVIDENCE_ID: EVIDENCE_TEXT})
    assert child.view.data["media_assets"] == ()
    raw = ExportSavedCommand(ProductWordWriter()).execute(child, "student")
    with ZipFile(BytesIO(raw)) as archive:
        assert not any(name.startswith("word/media/") for name in archive.namelist())
        assert all(b"ponse justifi" not in archive.read(name) for name in archive.namelist())
    assert len(ProductionMediaPlan(as_plain(child.p0_bundle.data["media_plan"])).media("correction")) == 1


def test_local_child_revision_requires_explicit_dependency_refresh():
    _, child = child_fixture()
    data = child.p0_bundle.mutable_copy()
    before = copy.deepcopy(data)
    data["sections"][0]["text"] += " Convention de l’exercice révisée."
    with pytest.raises(ValueError, match="PRODUCTION_MEDIA_DEPENDENCY_STALE"):
        P0Production(data)
    assert child.p0_bundle.mutable_copy() == before


@pytest.mark.parametrize("kind,mode", FAMILIES)
def test_canonical_application_save_reopen_and_new_composition_keep_same_asset(tmp_path, kind, mode):
    from backend.infrastructure.composition.factories.local_browser import build_saved_application

    parent, child = child_fixture(kind, mode)
    records = {(r.production_ref, r.version_ref): r for r in (parent, child)}
    application = build_saved_application(tmp_path / "library", create=True,
        source=lambda p, v: records[(p, v)], word_profile="product-v7")
    for record in (parent, child):
        saved = application.execute("save", body={"production_ref": record.production_ref, "version_ref": record.version_ref}, correlation="media.save")
        assert saved["record_sha256"] == record.sha256
    before = application.execute("word", child.production_ref, child.version_ref, kind="student", correlation="media.export")
    restarted = build_saved_application(tmp_path / "library", word_profile="product-v7")
    reopened = restarted.execute("open", child.production_ref, child.version_ref, correlation="media.reopen")
    assert reopened["record_sha256"] == child.sha256 and reopened["active_authority"] == "NONE_RESTORED"
    assert restarted.execute("word", child.production_ref, child.version_ref, kind="student", correlation="media.restart") == before
    assert restarted.execute("open", parent.production_ref, parent.version_ref, correlation="media.parent")["record_sha256"] == parent.sha256


@pytest.mark.parametrize("kind,mode", FAMILIES)
def test_product_projection_names_case_and_preserves_questions_and_answer_spaces(kind, mode):
    _, child = child_fixture(kind, mode)
    document = ExportSavedCommand(ProductWordWriter(), product_projection=True).preview(child, "student")
    assert document.title == child.p0_bundle.data["title"]
    if kind in {"EXERCISE", "ASSESSMENT"} or mode == "OPEN_QUESTIONS":
        assert any(b.text.startswith("Réponse\n") for b in document.blocks)
    elif mode in {"QCM", "QUIZ"}:
        assert not any(b.text.startswith("Réponse\n") for b in document.blocks)
    if kind == "ASSESSMENT":
        assert document.blocks[0].text == "60 minutes · 20 points"
    assert any(b.text == "Q01" for b in document.blocks) if kind != "COURSE" else not any(b.text == "Q01" for b in document.blocks)


def test_review_commitments_cover_media_without_claiming_pixel_inspection():
    _, child = child_fixture()
    commitments = child.p0_bundle.media_review_context()
    assert len(commitments) == 1
    assert commitments[0]["version_ref"] == child.version_ref
    assert commitments[0]["availability"] == "PRESENT"
    assert commitments[0]["pixel_inspection"] == "SEPARATE_REQUIRED"
    assert commitments[0]["dependencies"] == as_plain(child.p0_bundle.data["media_plan"]["entries"][0]["dependencies"])
    assert "bytes_base64" not in repr(commitments)


def test_word_preview_contains_the_same_audience_asset_as_the_snapshot():
    _, child = child_fixture()
    document = ExportSavedCommand(ProductWordWriter(), product_projection=True).preview(child, "student")
    snapshot = child.p0_bundle.student_projection()["media_assets"][0]
    preview = document.as_dict()["media_assets"][0]
    assert preview["png_sha256"] == snapshot["png_sha256"] and preview["bytes_base64"] == snapshot["bytes_base64"]


def test_legacy_writer_refuses_new_media_instead_of_discarding_it():
    from backend.adapters.outbound.export.word import OOXMLWordWriter

    _, child = child_fixture()
    with pytest.raises(ValueError, match="PRODUCTION_MEDIA_PRODUCT_WRITER_REQUIRED"):
        ExportSavedCommand(OOXMLWordWriter()).execute(child, "student")


def test_product_no_media_does_not_reintroduce_legacy_fiction_banner():
    parent, _, inbound = media_fixture()
    raw = parent.p0_bundle.mutable_copy()
    raw["title"] = "Exercice fictif pour contrôle local"
    parent = saved_record(P0Production(raw))
    child = inbound.execute(parent, [], no_media_reason="Un tableau natif suffit.")
    calls = []

    def legacy_presentation(document):
        calls.append(document)
        return document

    exporter = ExportSavedCommand(ProductWordWriter(), product_projection=True, presentation=legacy_presentation)
    preview = exporter.preview(child, "correction")
    assert not calls and not any(block.style == "Note" and block.text == "Cas fictif" for block in preview.blocks)
    assert preview.title == raw["title"] + " Corrigé"


@pytest.mark.parametrize("kind,mode", FAMILIES[1:])
def test_question_anchor_media_is_present_in_each_applicable_audience(kind, mode):
    parent, proposal, inbound = media_fixture(kind, mode)
    proposal["brief"].update(section_ref="Q01", preferred_position="AFTER_CONCEPT")
    proposal["dependency_refs"] = ["question:Q01"]
    child = inbound.execute(parent, [proposal])
    exporter = ExportSavedCommand(ProductWordWriter(), product_projection=True)
    for audience in ("student", "correction", "marking"):
        raw = exporter.execute(child, audience)
        with ZipFile(BytesIO(raw)) as archive:
            assert "word/media/figure_1.png" in archive.namelist()
            assert "Question 1" in "\n".join(ET.fromstring(archive.read("word/document.xml")).itertext())
        assert exporter.preview(child, audience).blocks[0].style == "Normal"


@pytest.mark.parametrize("no_media", [False, True])
def test_pure_version_title_rebind_keeps_exact_media_or_explicit_no_media(no_media):
    from backend.modules.pedagogical_design.contracts.dto.production_media import (
        rebind_unchanged_media,
    )

    parent, proposal, inbound = media_fixture()
    child = (inbound.execute(parent, [], no_media_reason="Les tableaux natifs suffisent.") if no_media else
             inbound.execute(parent, [proposal]))
    before = child.p0_bundle.mutable_copy()
    revised = copy.deepcopy(before)
    revised.update(version_ref="ver:" + "9" * 32, title="Un titre local révisé")
    revised["lineage"]["parent_version_ref"] = child.version_ref
    rebound = P0Production(rebind_unchanged_media(before, revised))
    assert rebound.data["media_plan"]["version_ref"] == revised["version_ref"]
    assert rebound.student_projection()["media_assets"] == child.p0_bundle.student_projection()["media_assets"]
    assert rebound.data["media_plan"]["no_media_reason"] == child.p0_bundle.data["media_plan"]["no_media_reason"]
    assert child.p0_bundle.mutable_copy() == before


@pytest.mark.parametrize("field,key", [("sections", "text"), ("questions", "prompt"), ("corrections", "expected_answer")])
def test_local_rebind_refuses_changed_dependencies_without_rewriting_parent(field, key):
    from backend.modules.pedagogical_design.contracts.dto.production_media import (
        rebind_unchanged_media,
    )

    _, child = child_fixture()
    before = child.p0_bundle.mutable_copy()
    revised = copy.deepcopy(before)
    revised["version_ref"] = "ver:" + "9" * 32
    revised[field][0][key] += " Changement local."
    with pytest.raises(ValueError, match="PRODUCTION_MEDIA_DEPENDENCY_STALE"):
        rebind_unchanged_media(before, revised)
    assert child.p0_bundle.mutable_copy() == before
