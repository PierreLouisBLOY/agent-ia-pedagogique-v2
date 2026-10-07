"""Real local images and declared review doubles, without any provider call."""
import copy
import json
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter
from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.infrastructure.composition.factories.course_media import build_course_media
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_chapter import CourseChapter
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
from tests.unit.test_course_chapter import child_fixture
from tests.unit.test_course_media import brief_data
from tests.unit.test_p0_agentic_routing import TechnicalCritic

KINDS = {"SCENARIO_ILLUSTRATION": ("LIBRARY_SCENE", 3), "PORTRAIT_STRIP": ("CHARACTERS", 3),
         "TIMELINE": ("TIMELINE", 5), "ACTIVITY_PLAN": ("WORKSPACE", 3)}


def contextual_brief(kind, production="prod:unit"):
    data = brief_data(production)
    layout, count = KINDS[kind]
    data.update(visual_type=kind, style_policy="COURSE_LOCAL_ILLUSTRATION_V2")
    nodes = [{"id": f"S{i}", "label": f"Repère {i}", "detail": "À observer", "icon": "NONE"} for i in range(count)]
    edges = [{"source": f"S{i}", "target": f"S{i+1}", "label": ""} for i in range(count-1)] if kind == "TIMELINE" else []
    data["diagram"].update(layout=layout, nodes=nodes, edges=edges)
    if kind == "SCENARIO_ILLUSTRATION":
        data.update(section_ref="CONTEXT", preferred_position="AFTER_CONTEXT")
    return data


def render(data):
    return build_course_media(profile="contextual-v2").execute(data, production_ref=data["production_ref"],
        documents={"D1"}, concepts={"N1"}, capabilities={"unit:source"}, notions={"notion:shared"})


@pytest.mark.parametrize("kind", KINDS)
def test_contextual_drawings_repeat_with_exact_provenance_and_bounded_size(kind):
    data = contextual_brief(kind)
    left, right = render(data), render(data)
    assert left.raw == right.raw
    assert len(left.raw) < 65536 and left.data["width"] == 1200
    assert left.data["renderer_id"] == "WINDOWS_GDI_ARIAL_NO_AA_RGB_CONTEXTUAL_V2"
    assert left.data["provenance"]["source_sha256"] == VisualBrief(data).sha256
    assert left.data["provenance"]["licence"] == "LOCAL_ORIGINAL"
    with pytest.raises(ValueError, match="RENDERER_PROFILE"):
        build_course_media().execute(data, production_ref="prod:unit", documents={"D1"}, concepts={"N1"},
            capabilities={"unit:source"}, notions={"notion:shared"})


@pytest.mark.parametrize("mutation", ["anchor", "type", "profile", "count", "edge", "icon", "hidden_detail", "capability", "notion", "production"])
def test_contextual_mutations_stop_before_drawing(mutation):
    data = contextual_brief("SCENARIO_ILLUSTRATION")
    if mutation == "anchor":
        data["section_ref"] = "D1"
    elif mutation == "type":
        data["visual_type"] = "PORTRAIT_STRIP"
    elif mutation == "profile":
        data["style_policy"] = "COURSE_LOCAL_DIAGRAM_V1"
    elif mutation == "count":
        data["diagram"]["nodes"].pop()
    elif mutation == "edge":
        data["diagram"]["edges"] = [{"source": "S0", "target": "S1", "label": ""}]
    elif mutation == "icon":
        data["diagram"]["nodes"][0]["icon"] = "PERSON"
    elif mutation == "hidden_detail":
        data["source_policy"] = "USER_SUPPLIED"
    else:
        field = {"capability": "institutional_capability_ref", "notion": "notion_refs", "production": "production_ref"}[mutation]
        data[field] = ["notion:other"] if mutation == "notion" else "prod:other" if mutation == "production" else "unit:other"
    with pytest.raises(ValueError):
        build_course_media(profile="contextual-v2").execute(data, production_ref="prod:unit", documents={"D1"}, concepts={"N1"},
            capabilities={"unit:source"}, notions={"notion:shared"})


@pytest.mark.parametrize("mutation", ["order", "label", "missing"])
def test_timeline_cannot_hide_or_reorder_relationships(mutation):
    data = contextual_brief("TIMELINE")
    if mutation == "order":
        data["diagram"]["edges"].reverse()
    elif mutation == "label":
        data["diagram"]["edges"][0]["label"] = "Invisible instruction"
    else:
        data["diagram"]["edges"].pop()
    with pytest.raises(ValueError):
        VisualBrief(data)


def eight_media_chapter():
    _, record = child_fixture()
    chapter = as_plain(record.p0_bundle.data["course_chapter"])
    briefs = []
    assets = []
    for i, kind in enumerate(["FLOWCHART", "ICON_SET", "PROCESS_MAP", "ORG_CHART", *KINDS]):
        data = contextual_brief(kind, record.production_ref) if kind in KINDS else brief_data(record.production_ref, kind=kind)
        data["visual_id"] = f"V{i+1}"
        worker = build_course_media(profile="contextual-v2" if kind in KINDS else "diagram-v1")
        asset = worker.execute(data, production_ref=record.production_ref, documents={"D1"}, concepts={"N1"},
                               capabilities={"unit:source"}, notions={"notion:shared"})
        briefs.append(data)
        assets.append(as_plain(asset.data))
    chapter.update(contract_id="COURSE-CHAPTER-MEDIA-2.0", visual_briefs=briefs, media_assets=assets)
    result = CourseChapter(chapter)
    result.bind_context(record.p0_bundle.context)
    result.bind_production(record.production_ref)
    return record, result


@pytest.mark.parametrize("teacher", [False, True])
def test_eight_images_word_placement_and_teacher_separation(teacher):
    _, chapter = eight_media_chapter()
    document = WordDocument("correction" if teacher else "student", "Test", (),
        course_chapter=chapter.projection(teacher=teacher), course_media=chapter.media(teacher=teacher))
    raw = CourseOOXMLWordWriter().write(document)
    with ZipFile(BytesIO(raw)) as archive:
        assert len([p for p in archive.namelist() if p.startswith("word/media/")]) == 8
        xml = archive.read("word/document.xml").decode()
        assert ("ORACLE_PROF" in xml) == teacher
        assert "LOCAL_ORIGINAL" not in xml and "bytes_base64" not in xml
        assert xml.index('rIdMedia5') < xml.index('Votre travail')
        tree = ET.fromstring(xml)
        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        knowledge = next(p for p in tree.iter(w + "p") if "Tester ses connaissances" in "".join(p.itertext()))
        assert knowledge.find(".//" + w + "pageBreakBefore") is None
        if not teacher:
            paragraphs = list(tree.iter(w + "p"))
            for i, p in enumerate(paragraphs):
                style = p.find(".//" + w + "pStyle")
                if style is not None and style.get(w + "val") == "Response":
                    following = paragraphs[i+1].find(".//" + w + "pStyle") if i+1 < len(paragraphs) else None
                    continues = following is not None and following.get(w + "val") == "Response"
                    assert (p.find(".//" + w + "keepNext") is not None) == continues
        assert len(tree.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr")) == 8
        assert b'TargetMode="External"' not in archive.read("word/_rels/document.xml.rels")
        for i, media in enumerate(chapter.media(teacher=teacher), 1):
            assert archive.read(f"word/media/figure_{i}.png") == media.asset.raw
    assert raw == CourseOOXMLWordWriter().write(document)


def test_ag04_double_receives_all_eight_visuals_and_six_axes_without_pixels_or_authority():
    record, chapter = eight_media_chapter()
    production = record.p0_bundle.mutable_copy()
    production["course_chapter"] = as_plain(chapter.data)
    critic = TechnicalCritic()
    reviewed = P0ReviewAdapter(critic, authorize=lambda request: True).review(request={
        "production": production, "evidence_pack": {"passages": []}, "plan": {}, "validation": {},
        "bundle_sha256": record.p0_bundle.sha256})
    visuals = critic.requests[0].target_payload["visuals"]
    assert len(visuals) == 8
    assert all(len(v["axes"]) == 6 and "qualite_lecture" in v["axes"] for v in visuals)
    assert [v["asset_sha256"] for v in visuals] == [p.asset.data["png_sha256"] for p in chapter.media()]
    assert all(v["pixel_inspection"] == "SEPARATE_REQUIRED" for v in visuals)
    assert "bytes_base64" not in json.dumps(as_plain(critic.requests[0].target_payload))
    assert reviewed["promotion"] == "NOT_PERFORMED"


def test_ninth_media_and_cross_production_substitution_are_rejected():
    record, chapter = eight_media_chapter()
    data = copy.deepcopy(as_plain(chapter.data))
    data["visual_briefs"].append(data["visual_briefs"][0])
    data["media_assets"].append(data["media_assets"][0])
    with pytest.raises(ValueError):
        CourseChapter(data)
    with pytest.raises(ValueError, match="PRODUCTION_BINDING"):
        chapter.bind_production(record.production_ref + "other")
