"""Explicit synthetic content exercises images, rights, variants and OOXML."""

import copy
import hashlib
import json
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter
from backend.adapters.outbound.export.local_media import WindowsLocalDiagramRenderer
from backend.infrastructure.composition.factories.course_media import build_course_media
from backend.modules.materialization_export.application.services.media_asset import MediaAssetWorker
from backend.modules.materialization_export.contracts.dto.media_asset import (
    MediaAsset,
    validate_png,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
    COURSE_MEDIA_CONTRACT,
    CourseChapter,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
from tests.unit.test_course_chapter import child_fixture


def brief_data(production="prod:unit", *, kind="FLOWCHART", teacher_only=False):
    layout = {
        "FLOWCHART": "FLOW",
        "ICON_SET": "RESOURCES",
        "PROCESS_MAP": "CYCLE",
        "ORG_CHART": "RESPONSIBILITIES",
    }[kind]
    count = 5 if kind == "ICON_SET" else 4
    return {
        "contract_id": "VISUAL-BRIEF-1.0",
        "visual_id": "V1",
        "production_ref": production,
        "section_ref": "D1",
        "learning_objective": "Relier les contributions au projet commun",
        "institutional_capability_ref": "unit:source",
        "notion_refs": ["notion:shared"],
        "visual_type": kind,
        "pedagogical_function": "Comparer les étapes",
        "content_description": "Quatre étapes du cas synthétique",
        "must_show": ["Des liens explicites"],
        "must_not_show": ["Des réponses réservées au professeur"],
        "caption": "TEACHER_ONLY_MARKER" if teacher_only else "Repères pour observer la situation",
        "alt_text": "Les étapes relient les contributions individuelles à une organisation durable.",
        "student_visibility": not teacher_only,
        "teacher_visibility": True,
        "preferred_position": "AFTER_DOCUMENT",
        "source_policy": "LOCAL_DETERMINISTIC",
        "style_policy": "COURSE_LOCAL_DIAGRAM_V1",
        "diagram": {
            "layout": layout,
            "nodes": [
                {
                    "id": "N" + str(i),
                    "label": "Étape " + str(i),
                    "detail": "Un fait concret à expliquer",
                    "icon": ["PERSON", "COINS", "BOX", "IDEA", "SCREEN"][i]
                    if kind == "ICON_SET"
                    else "NONE",
                }
                for i in range(count)
            ],
            "edges": []
            if kind == "ICON_SET"
            else [
                {"source": "N" + str(i), "target": "N" + str(i + 1), "label": ""}
                for i in range(count - 1)
            ],
            "note": "Situation construite pour observer les relations.",
        },
    }


def media_chapter(*, teacher_only=False):
    _, record = child_fixture()
    data = as_plain(record.p0_bundle.data["course_chapter"])
    brief = VisualBrief(brief_data(record.production_ref, teacher_only=teacher_only))
    asset = MediaAssetWorker(WindowsLocalDiagramRenderer()).execute(brief)
    data.update(
        contract_id=COURSE_MEDIA_CONTRACT,
        visual_briefs=[as_plain(brief.data)],
        media_assets=[as_plain(asset.data)],
    )
    chapter = CourseChapter(data)
    chapter.bind_context(record.p0_bundle.context)
    chapter.bind_production(record.production_ref)
    return record, chapter, brief, asset


@pytest.mark.parametrize("kind", ["FLOWCHART", "ICON_SET", "PROCESS_MAP", "ORG_CHART"])
def test_local_drawing_is_repeatable_bounded_and_png(kind):
    brief = VisualBrief(brief_data(kind=kind))
    worker = MediaAssetWorker(WindowsLocalDiagramRenderer())
    left, right = worker.execute(brief), worker.execute(brief)
    assert left.raw == right.raw and left.sha256 == right.sha256
    assert validate_png(left.raw)[0] == 1200
    assert left.data["png_sha256"] == hashlib.sha256(left.raw).hexdigest()
    assert len(left.raw) < 65536


@pytest.mark.parametrize(
    "field,value",
    [
        ("alt_text", ""),
        ("caption", ""),
        ("learning_objective", ""),
        ("student_visibility", 1),
        ("preferred_position", "ARBITRARY_PATH"),
        ("source_policy", "WEB_SEARCH"),
        ("visual_id", "../asset"),
        ("style_policy", "REMOTE_TEMPLATE"),
    ],
)
def test_invalid_brief_fails_closed(field, value):
    data = brief_data()
    data[field] = value
    with pytest.raises(ValueError):
        VisualBrief(data)


@pytest.mark.parametrize(
    "mutation", ["production", "section", "capability", "notion", "graph", "invisible"]
)
def test_context_and_graph_substitutions_stop_before_renderer(mutation):
    data = brief_data()
    changes = {
        "production": ("production_ref", "prod:other"),
        "section": ("section_ref", "D99"),
        "capability": ("institutional_capability_ref", "unit:other"),
        "notion": ("notion_refs", ["notion:other"]),
    }
    if mutation in changes:
        key, value = changes[mutation]
        data[key] = value
    elif mutation == "graph":
        data["diagram"]["edges"][0]["target"] = "MISSING"
    else:
        data["student_visibility"] = data["teacher_visibility"] = False
    with pytest.raises(ValueError):
        build_course_media().execute(
            data,
            production_ref="prod:unit",
            documents={"D1"},
            concepts=set(),
            capabilities={"unit:source"},
            notions={"notion:shared"},
        )


@pytest.mark.parametrize(
    "mutation", ["hash", "width", "licence", "provenance", "brief", "trailing_bytes"]
)
def test_media_mutations_cannot_be_exported(mutation):
    _, _, brief, asset = media_chapter()
    data = as_plain(asset.data)
    if mutation == "hash":
        data["png_sha256"] = "0" * 64
    elif mutation == "width":
        data["width"] = 1
    elif mutation == "licence":
        data["provenance"]["licence"] = "UNKNOWN"
    elif mutation == "provenance":
        data["provenance"]["admission_ref"] = ""
    elif mutation == "brief":
        data["visual_id"] = "V2"
    else:
        with pytest.raises(ValueError):
            validate_png(asset.raw + b"trailing")
        return
    with pytest.raises(ValueError):
        MediaAsset(data).bind(brief)


@pytest.mark.parametrize("policy", ["USER_SUPPLIED", "LICENSED_EXTERNAL", "GENERATED_ADMITTED"])
def test_import_requires_exact_admitted_bytes_and_never_fetches(policy):
    _, _, _, original = media_chapter()
    data = brief_data()
    data.update(source_policy=policy, visual_type="DIAGRAM", diagram=None)
    brief = VisualBrief(data)
    worker = MediaAssetWorker(WindowsLocalDiagramRenderer())
    with pytest.raises(ValueError, match="ADMITTED_BYTES_REQUIRED_NO_FETCH"):
        worker.execute(brief)
    admission = {
        "source_kind": policy,
        "source_ref": "unit:supplied",
        "source_sha256": hashlib.sha256(original.raw).hexdigest(),
        "licence": "USER_PERMISSION",
        "rights_basis": "Synthetic owner permission",
        "admission_ref": "unit:admission",
    }
    imported = worker.execute(brief, admitted_bytes=original.raw, admission=admission)
    assert imported.raw == original.raw and imported.data["renderer_id"] == "ADMITTED_PNG_BYTES_1"
    admission["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SOURCE_HASH"):
        worker.execute(brief, admitted_bytes=original.raw, admission=admission)


def test_student_variant_has_no_teacher_only_asset_or_answer():
    _, chapter, _, asset = media_chapter(teacher_only=True)
    assert not chapter.media()
    text = json.dumps(chapter.projection())
    assert "TEACHER_ONLY_MARKER" not in text and "ORACLE_PROF" not in text
    assert asset.data["bytes_base64"] not in text
    assert chapter.media(teacher=True)
    assert "TEACHER_ONLY_MARKER" in json.dumps(chapter.projection(teacher=True))


@pytest.mark.parametrize("teacher", [False, True])
def test_export_embeds_the_verified_png_caption_and_alt_text(teacher):
    _, chapter, brief, asset = media_chapter()
    document = WordDocument(
        "correction" if teacher else "student",
        "Synthetic",
        (),
        course_chapter=chapter.projection(teacher=teacher),
        course_media=chapter.media(teacher=teacher),
    )
    writer = CourseOOXMLWordWriter()
    raw = writer.write(document)
    assert writer.write(document) == raw
    with ZipFile(BytesIO(raw)) as archive:
        assert archive.testzip() is None
        assert archive.read("word/media/figure_1.png") == asset.raw
        root = ET.fromstring(archive.read("word/document.xml"))
        props = root.find(
            ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"
        )
        assert props.attrib["descr"] == brief.data["alt_text"]
        xml = archive.read("word/document.xml").decode()
        assert brief.data["caption"] in xml
        assert ("ORACLE_PROF" in xml) == teacher
        assert "LOCAL_ORIGINAL" not in xml and "_sha256" not in xml
        assert b'TargetMode="External"' not in archive.read("word/_rels/document.xml.rels")
    forged = WordDocument(
        document.kind, "Synthetic", (), course_chapter=chapter.projection(teacher=teacher)
    )
    with pytest.raises(ValueError, match="MEDIA_PROVENANCE_BINDING"):
        writer.write(forged)


def test_missing_or_substituted_assets_and_wrong_production_are_rejected():
    record, chapter, _, _ = media_chapter()
    with pytest.raises(ValueError, match="PRODUCTION_BINDING"):
        chapter.bind_production("prod:other")
    data = as_plain(chapter.data)
    data["media_assets"] = []
    with pytest.raises(ValueError, match="MEDIA_COVERAGE"):
        CourseChapter(data)
    data = copy.deepcopy(as_plain(chapter.data))
    data["visual_briefs"][0]["alt_text"] = "Substitution"
    with pytest.raises(ValueError, match="BRIEF_BINDING"):
        CourseChapter(data)
    assert record.p0_bundle.data["course_chapter"]["contract_id"] == "COURSE-CHAPTER-1.0"
