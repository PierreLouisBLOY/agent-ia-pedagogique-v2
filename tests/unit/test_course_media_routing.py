"""Declared port doubles qualify routing; they are not pedagogical reviews."""
import json

import pytest

from backend.adapters.outbound.generation.course_visual_brief import CourseVisualBriefAdapter
from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.agents.generation import GenerationPortResult, GenerationPortResultStatus
from backend.infrastructure.composition.factories.course_media import build_course_media
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_chapter import CourseChapter
from tests.unit.test_course_chapter import child_fixture
from tests.unit.test_course_media import brief_data, media_chapter
from tests.unit.test_p0_agentic_routing import TechnicalCritic


class BriefPort:
    def __init__(self, record, mutation=None):
        self.record, self.mutation, self.requests = record, mutation, []

    def generate(self, *, request):
        self.requests.append(request)
        brief = brief_data(self.record.production_ref)
        if self.mutation:
            brief.update(self.mutation)
        return GenerationPortResult(request.source_step_id, request.operation,
            GenerationPortResultStatus.SUCCEEDED,
            structured_payload={"contract_id": "VISUAL-BRIEFS-OUTPUT-1.0", "visual_briefs": [brief]})


def test_ag03_brief_is_bounded_answer_free_and_materialized_through_application():
    _, record = child_fixture()
    port = BriefPort(record)
    with pytest.raises(ValueError, match="AUTHORIZATION_REQUIRED"):
        CourseVisualBriefAdapter(port, authorize=lambda request: False).propose(record, {})
    assert not port.requests
    brief, = CourseVisualBriefAdapter(port, authorize=lambda request: True).propose(record, {"function": "Explain links"})
    request = port.requests[0]
    assert request.operation.value == "TRANSFORM"
    payload = json.dumps(as_plain(request.resolved_inputs))
    assert "ORACLE_PROF" not in payload and "teacher_answers" not in payload
    assert "bytes_base64" not in payload
    asset = build_course_media().execute(brief.data, production_ref=record.production_ref,
        documents={"D1"}, concepts={"N1"}, capabilities={"unit:source"}, notions={"notion:shared"})
    assert asset.data["brief_sha256"] == brief.sha256


@pytest.mark.parametrize("mutation", [{"production_ref": "prod:other"}, {"section_ref": "D99"},
    {"institutional_capability_ref": "other"}, {"notion_refs": ["notion:other"]}])
def test_ag03_cannot_change_context_or_scope(mutation):
    _, record = child_fixture()
    with pytest.raises(ValueError, match="CONTEXT_BINDING"):
        CourseVisualBriefAdapter(BriefPort(record, mutation), authorize=lambda request: True).propose(record, {})


def test_ag04_receives_each_visual_semantics_and_five_axes_without_pixel_acceptance():
    record, chapter, _, asset = media_chapter()
    production = record.p0_bundle.mutable_copy()
    production["course_chapter"] = as_plain(chapter.data)
    critic = TechnicalCritic()
    adapter = P0ReviewAdapter(critic, authorize=lambda request: True)
    result = adapter.review(request={"production": production, "evidence_pack": {"passages": []},
        "plan": {}, "validation": {}, "bundle_sha256": record.p0_bundle.sha256})
    request = critic.requests[0]
    assert len(request.target_payload["visuals"]) == 1
    assert request.target_payload["visuals"][0]["asset_sha256"] == asset.data["png_sha256"]
    # Retain the historical test identity and its five axes; add readability explicitly.
    assert tuple(request.target_payload["visuals"][0]["axes"][:5]) == ("exactitude", "niveau", "utilite", "coherence", "absence_surinterpretation")
    assert tuple(request.target_payload["visuals"][0]["axes"][5:]) == ("qualite_lecture",)
    assert request.target_payload["visuals"][0]["pixel_inspection"] == "SEPARATE_REQUIRED"
    payload = json.dumps(as_plain(request.target_payload))
    assert "ORACLE_PROF" in payload  # teacher reference is allowed for review, not solving
    assert "bytes_base64" not in payload and asset.data["bytes_base64"] not in payload
    assert result["correction_required"] is True and result["promotion"] == "NOT_PERFORMED"


def test_institutional_course_accepts_twelve_topics_but_keeps_a_closed_limit():
    _, record = child_fixture()
    data = record.p0_bundle.context.as_dict()
    data["topics"] = ["Notion "+str(i) for i in range(12)]
    assert len(P0Context(data).data["topics"]) == 12
    data["topics"] += ["Extra "+str(i) for i in range(5)]
    with pytest.raises(ValueError, match="P0_CONTEXT_ITEMS"):
        P0Context(data)
    data["topics"] = data["topics"][:9]
    data["resource_type"] = "EXERCISE"
    with pytest.raises(ValueError, match="P0_CONTEXT_ITEMS"):
        P0Context(data)


@pytest.mark.parametrize("field,value", [("frame", "SGN_PREMIERE"), ("subject_label", "Sciences de gestion et numérique"),
    ("question_ref", "question:other"), ("program_version", "other")])
def test_illustrations_never_rebind_management_to_sgn(field, value):
    record, chapter, _, _ = media_chapter()
    data = as_plain(chapter.data)
    data["program_header"][field] = value
    with pytest.raises(ValueError, match="PROGRAM_BINDING"):
        CourseChapter(data).bind_context(record.p0_bundle.context)


def test_diagram_text_cannot_hide_internal_metadata():
    record, chapter, _, _ = media_chapter()
    data = as_plain(chapter.data)
    brief = data["visual_briefs"][0]
    brief["diagram"]["nodes"][0]["label"] = "SQLite"
    asset = build_course_media().execute(brief, production_ref=record.production_ref,
        documents={"D1"}, concepts={"N1"}, capabilities={"unit:source"}, notions={"notion:shared"})
    data["media_assets"] = [as_plain(asset.data)]
    with pytest.raises(ValueError, match="INTERNAL_METADATA"):
        CourseChapter(data)
