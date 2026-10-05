"""Declared synthetic catalogue; no canonical authority or provider execution."""
import copy
import hashlib
import json
from secrets import token_hex

import pytest

from backend.adapters.inbound.application.reframe_course import ReframeCourseInbound
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment
from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_context.contracts.dto.stmg_institutional import (
    institutional_header,
)
from backend.modules.pedagogical_design.contracts.dto.course_policy import COURSE_SECTIONS
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0_PROVENANCE_LABEL
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from tests.support.p0_generation_double import P0GenerationDouble


class Catalog:
    def __init__(self):
        self.data = {key: [] for key in ("official_framework", "official_framework_version", "official_framework_element",
            "institutional_attachment", "pedagogical_context", "notion_context", "notion", "document", "document_reference", "source")}
        self.data["notion"] = [{"id": "notion:shared", "canonical_label": "Notion commune synthétique", "identity_status": "CANONICAL"}]
        for frame, spec in STMG_FRAMES.items():
            self.data["official_framework"].append({"id": "program:" + frame, "code": spec[5], "issuing_source_id": "source:" + frame})
            self.data["official_framework_version"].append({"id": "version:" + frame, "framework_id": "program:" + frame,
                "version_label": "UNIT-V1", "lifecycle_status": "PUBLISHED", "official_document_id": "document:" + frame})
            self.data["source"].append({"id": "source:" + frame, "status": "ADMITTED"})
            self.data["document"].append({"id": "document:" + frame, "sha256": hashlib.sha256(frame.encode()).hexdigest(), "document_status": "ADMITTED"})
            self.data["document_reference"].append({"id": "locator:" + frame, "document_id": "document:" + frame})
            self.data["official_framework_element"].extend([
                {"id": "question:" + frame, "framework_version_id": "version:" + frame, "parent_element_id": None,
                 "element_type": "QUESTION", "official_label": "1.1 Question " + frame, "document_reference_id": "locator:" + frame},
                {"id": "capacity:" + frame, "framework_version_id": "version:" + frame, "parent_element_id": "question:" + frame,
                 "element_type": "CAPACITY", "official_label": "Capacité spécifique " + frame, "document_reference_id": "locator:" + frame}])
            self.data["institutional_attachment"].append({"id": "attachment:" + frame, "notion_id": "notion:shared",
                "framework_element_id": "question:" + frame, "attachment_type": "EXPLICIT", "status": "ADMITTED",
                "origin_type": "OFFICIAL_DOCUMENT", "depth_level": "APPLICATION"})

    def read_institutional_catalog(self):
        return copy.deepcopy(self.data)


def context(frame="MANAGEMENT_PREMIERE"):
    spec = STMG_FRAMES[frame]
    return {"contract_id": "P0-CONTEXT-2.0", "resource_type": "COURSE", "question_mode": None,
        "level": spec[0], "discipline": spec[6], "topics": ["Notion commune synthétique"], "objectives": ["Appliquer la capacité choisie"],
        "difficulty": "STANDARD", "language": "fr", "duration_minutes": None, "total_points": None,
        "institutional": {"contract_id": "STMG-INSTITUTIONAL-CONTEXT-1.0", "frame": frame, "education_level": spec[1], "series": "STMG",
            "teaching_subject": spec[2], "program_ref": "program:" + frame, "program_version": "version:" + frame,
            "program_component": spec[3], "specific_track": spec[4], "theme_ref": "theme:1", "question_ref": "question:" + frame,
            "capacity_refs": ["capacity:" + frame], "notion_refs": ["notion:shared"], "depth": "APPLICATION"},
        "institutional_resolution": None, "local_progression": {"chapter": "Chapitre local 7", "sequence": None, "week": None}}


def app(catalog, double=None):
    excerpt = "Extrait synthétique : une notion commune ; les capacités sont distinctes."
    query = ReadSTMGAlignment(catalog)
    return P0CreationService(lambda _: {"excerpt": excerpt, "reference": {
        "evidence_id": "evidence:" + "1" * 32, "source_ref": "notion:shared", "locator": "unit:passage",
        "checksum_or_version": "UNIT-V1", "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(), "provenance_label": P0_PROVENANCE_LABEL}},
        generation=double, institutional_resolver=query.resolve, exact_stmg_required=True)


def prepare(service, data):
    return service.execute("prepare", {"command_id": token_hex(16), "context": data,
        "reference": {"notion_id": "notion:shared", "passage_ref": "unit:passage"}})


class ExplainedCourseDouble(P0GenerationDouble):
    def generate(self, *, request):
        output = dict(super().generate(request=request))
        output["sections"] = [{"section_id": "S_" + role, "heading": role, "text": "Explication synthétique de test " + role} for role in COURSE_SECTIONS]
        return output


@pytest.mark.parametrize("frame", STMG_FRAMES)
def test_seven_exact_frames_preserve_subject_version_and_header(frame):
    service = app(Catalog(), ExplainedCourseDouble())
    prepared = prepare(service, context(frame))
    confirmed = prepared["context"]
    resolution = confirmed["institutional_resolution"]
    assert resolution["status"] == "RESOLVED_ADMITTED"
    assert resolution["program_version"] == "version:" + frame
    assert resolution["capacities"][0]["capacity_ref"] == "capacity:" + frame
    assert institutional_header(confirmed).endswith(STMG_FRAMES[frame][6])
    assert prepared["agentic"]["plan"]["institutional"] == confirmed["institutional"]
    assert prepared["agentic"]["evidence_pack"]["institutional_resolution"] == resolution
    view = service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})["view"]
    record = service.saved_source(view["production_ref"], view["version_ref"])
    document = ExportSavedCommand(object()).preview(record, "student")
    assert document.blocks[0].text == institutional_header(confirmed)
    assert "UNIT-V1" == resolution["version_label"]
    assert resolution["programme_document_sha256"] == hashlib.sha256(frame.encode()).hexdigest()


@pytest.mark.parametrize("wrong", ["SGN_PREMIERE", "MSDGN_TERMINALE_COMMON", "MSDGN_TERMINALE_SPECIFIC_GF",
    "MSDGN_TERMINALE_SPECIFIC_MERCATIQUE", "MSDGN_TERMINALE_SPECIFIC_RHC", "MSDGN_TERMINALE_SPECIFIC_SIG"])
def test_common_notion_never_merges_another_programme_capacity(wrong):
    data = context()
    data["institutional"]["capacity_refs"] = ["capacity:" + wrong]
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_CAPACITY_SCOPE"):
        prepare(app(Catalog()), data)


@pytest.mark.parametrize("wrong", ["MSDGN_TERMINALE_COMMON", "MSDGN_TERMINALE_SPECIFIC_MERCATIQUE", "MSDGN_TERMINALE_SPECIFIC_RHC", "MSDGN_TERMINALE_SPECIFIC_SIG"])
def test_gf_cannot_borrow_other_terminal_subjects(wrong):
    data = context("MSDGN_TERMINALE_SPECIFIC_GF")
    data["institutional"]["question_ref"] = "question:" + wrong
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_QUESTION_THEME"):
        prepare(app(Catalog()), data)


@pytest.mark.parametrize("mutation", ["version", "theme", "subject", "track", "series"])
def test_context_substitution_is_rejected_before_dispatch(mutation):
    double = ExplainedCourseDouble()
    data = context()
    field, value = {"version": ("program_version", "unknown:v2"), "theme": ("theme_ref", "theme:7"),
        "subject": ("teaching_subject", "SCIENCES_GESTION_NUMERIQUE"), "track": ("specific_track", "GESTION_FINANCE"), "series": ("series", "BTS")}[mutation]
    data["institutional"][field] = value
    with pytest.raises(ValueError):
        prepare(app(Catalog(), double), data)
    assert double.requests == []


@pytest.mark.parametrize("mutation", ["implicit", "ai", "proposed", "wrong_locator", "missing_document", "missing_source", "wrong_depth", "empty_capacity"])
def test_provenance_gap_or_implicit_link_cannot_dispatch(mutation):
    catalog = Catalog()
    if mutation == "implicit":
        catalog.data["institutional_attachment"][0]["attachment_type"] = "INFERRED"
    if mutation == "ai":
        catalog.data["institutional_attachment"][0]["origin_type"] = "AI_INFERENCE"
    if mutation == "proposed":
        catalog.data["institutional_attachment"][0]["status"] = "PROPOSED"
    if mutation == "wrong_depth":
        catalog.data["institutional_attachment"][0]["depth_level"] = "ANALYSIS"
    if mutation == "wrong_locator":
        catalog.data["document_reference"][0]["document_id"] = "document:SGN_PREMIERE"
    if mutation == "missing_document":
        catalog.data["document"].pop(0)
    if mutation == "missing_source":
        catalog.data["source"].pop(0)
    data = context()
    if mutation == "empty_capacity":
        data["institutional"]["capacity_refs"] = []
    double = ExplainedCourseDouble()
    service = app(catalog, double)
    prepared = prepare(service, data)
    assert prepared["context"]["institutional_resolution"]["status"] == "CONTENT_GAP"
    assert prepared["agentic"]["quality"]["sources"] == "SOURCES_INSUFFISANTES"
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_CONTENT_GAP"):
        service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})
    assert double.requests == []


def test_active_stmg_rejects_legacy_context_without_management_default():
    data = context()
    for key in ("institutional", "institutional_resolution", "local_progression"):
        data.pop(key)
    data["contract_id"] = "R6-P0-CONTEXT-1.0"
    assert P0Context(data).as_dict() == data  # Saved historical contracts still reopen.
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_CONTEXT_REQUIRED"):
        prepare(app(Catalog()), data)


def test_course_policy_reaches_projection_and_is_checked_after_generation():
    service = app(Catalog(), ExplainedCourseDouble())
    prepared = prepare(service, context())
    request = service.prepared[prepared["preparation_ref"]]
    wire = build_p0_content_request(request)
    assert "aucune limite de pages" in wire.instructions
    payload = json.loads(wire.input_json)
    assert payload["course_policy"]["page_limit"] is None
    assert payload["context"]["institutional"]["teaching_subject"] == "MANAGEMENT"
    assert "S_EXPLAINED_NOTIONS" in wire.instructions
    bad = app(Catalog(), P0GenerationDouble())
    bad_prepared = prepare(bad, context())
    with pytest.raises(ValueError, match="P0_COURSE_EXPLANATION_REQUIRED"):
        bad.execute("generate", {"command_id": token_hex(16), "preparation_ref": bad_prepared["preparation_ref"], "preparation_sha256": bad_prepared["preparation_sha256"]})
    assert bad.records == {}


def test_matrix_keeps_one_notion_seven_separate_relationship_scopes():
    catalog = Catalog()
    matrix = ReadSTMGAlignment(catalog).matrix()
    assert matrix["notion_count"] == 1
    scopes = matrix["notions"][0]["scopes"]
    assert len(scopes) == 7
    assert len({s["relationships"][0]["program_version"] for s in scopes}) == 7
    assert all(s["status"] == "LINKS_REQUIRE_ADMISSION" for s in scopes)
    assert catalog.data["institutional_attachment"][0]["attachment_type"] == "EXPLICIT"


def test_review_receives_same_exact_frame_and_cannot_review_a_gap():
    class ReviewCapture:
        def __init__(self):
            self.requests = []

        def authorize(self, *, request):
            self.requests.append(request)
            return False

    service = app(Catalog(), ExplainedCourseDouble())
    prepared = prepare(service, context())
    view = service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})["view"]
    capture = ReviewCapture()
    service.review = capture
    assert service.execute("review", {"command_id": token_hex(16), "production_ref": view["production_ref"], "version_ref": view["version_ref"], "bundle_sha256": view["bundle_sha256"]})["state"] == "AUTHORIZATION_REQUIRED"
    request = capture.requests[0]
    assert request["production"]["context"]["institutional_resolution"] == request["evidence_pack"]["institutional_resolution"]
    assert request["plan"]["institutional"] == request["production"]["context"]["institutional"]


def test_local_context_successor_preserves_parent_and_does_not_inherit_review():
    catalog = Catalog()
    service = app(catalog, ExplainedCourseDouble())
    prepared = prepare(service, context())
    view = service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})["view"]
    parent = service.saved_source(view["production_ref"], view["version_ref"])
    original = parent.mutable_copy()
    catalog.data["document"][1]["document_status"] = "PROPOSED"
    inbound = ReframeCourseInbound(ReadSTMGAlignment(catalog).resolve)
    child = inbound.execute(parent, context("SGN_PREMIERE"), title="Proposition locale synthétique",
        sections=parent.p0_bundle.mutable_copy()["sections"], reference_selection={"notion_id": "notion:shared"},
        evidence=service.evidence[parent.version_ref])
    assert parent.mutable_copy() == original
    assert child.production_ref == parent.production_ref and child.version_ref != parent.version_ref
    assert child.p0_bundle.data["lineage"]["parent_version_ref"] == parent.version_ref
    assert child.data["reviews"] == ()
    assert child.data["validations"][0]["institutional_status"] == "CONTENT_GAP"
    assert child.data["validations"][0]["dispatch_permitted"] is False
    assert len(service.generation.requests) == 1  # Only the declared synthetic parent generation.
