"""Local descendant of an existing synthetic real-organization course."""
from secrets import token_hex

from backend.adapters.inbound.application.reframe_course import ReframeCourseInbound
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
    COURSE_NOTION_PRODUCTION_CONTRACT,
)
from tests.test_real_course_thread import REAL_CHAPTER, real_configuration


def test_real_course_reframing_preserves_parent_without_another_generation(tmp_path):
    _, service, prepared, _, resolver, transport = real_configuration(tmp_path)
    view = service.execute("generate", {
        "command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"],
    })["view"]
    parent = service.saved_source(view["production_ref"], view["version_ref"])
    original = parent.p0_bundle
    before = parent.sha256
    context = original.context.as_dict()
    child = ReframeCourseInbound(lambda *_: context["institutional_resolution"]).execute(
        parent, context, title=original.data["title"], sections=[],
        reference_selection={"notion_id": "notion:shared"},
        evidence=service.evidence[parent.version_ref],
        course_chapter=as_plain(original.data["course_chapter"]),
    )
    assert parent.sha256 == before
    assert child.version_ref != parent.version_ref
    assert child.p0_bundle.data["contract_id"] == COURSE_NOTION_PRODUCTION_CONTRACT
    assert child.p0_bundle.data["course_chapter"]["contract_id"] == REAL_CHAPTER
    assert child.p0_bundle.data["references"] == original.data["references"]
    assert child.p0_bundle.data["lineage"]["parent_version_ref"] == original.version_ref
    assert child.data["validations"][0]["status"] == "PASS"
    assert not child.data["reviews"]
    assert transport.calls == resolver.calls == 1
