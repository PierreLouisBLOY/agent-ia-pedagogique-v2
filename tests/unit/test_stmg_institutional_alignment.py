"""Declared synthetic catalogue; no canonical authority or provider execution."""
import copy
import hashlib
import json
import sqlite3
from secrets import token_hex

import pytest

from backend.adapters.inbound.application.reframe_course import ReframeCourseInbound
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.resource_library.institutional_sqlite import (
    SQLiteInstitutionalCatalogAdapter,
)
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

    def read_reference_contexts(self, object_ref):
        return tuple(copy.deepcopy(link) for link in self.data.get("reference_contexts", []) if link["object_ref"] == object_ref)


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
        generation=double, institutional_resolver=lambda selection, reference: query.resolve(selection, {
            **reference, "object_ref": "notion:shared", "object_kind": "NOTION", "version_or_checksum": "UNIT-V1"}),
        exact_stmg_required=True)


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


def scoped_reference():
    return {"notion_id": "notion:shared", "object_ref": "content:synthetic", "object_kind": "PEDAGOGICAL_CONTENT",
            "passage_ref": "unit:passage", "version_or_checksum": "UNIT-V1"}


def admitted_content_catalog():
    catalog = Catalog()
    catalog.data["reference_contexts"] = [{"object_ref": "content:synthetic", "context_ref": "context:synthetic",
        "role": "MAIN", "status": "ADMITTED", "program_version": "version:MANAGEMENT_PREMIERE",
        "element_ref": "question:MANAGEMENT_PREMIERE", "depth": "APPLICATION"}]
    return catalog


def test_contextual_passage_requires_an_exact_admitted_relation():
    result = ReadSTMGAlignment(admitted_content_catalog()).resolve(context()["institutional"], scoped_reference())
    assert result["status"] == "RESOLVED_ADMITTED"
    assert result["reference_scope"]["status"] == "EXACT_CONTEXT_ADMITTED"
    assert result["reference_scope"]["relationships"][0]["program_version"] == "version:MANAGEMENT_PREMIERE"


@pytest.mark.parametrize("mutation", ["programme", "question", "depth", "proposed", "object", "missing", "unverified", "method"])
def test_common_notion_never_admits_another_programme_passage(mutation):
    catalog = admitted_content_catalog()
    link = catalog.data["reference_contexts"][0]
    reference = scoped_reference()
    if mutation == "programme":
        link["program_version"] = "version:SGN_PREMIERE"
    if mutation == "question":
        link["element_ref"] = "question:SGN_PREMIERE"
    if mutation == "depth":
        link["depth"] = "ANALYSIS"
    if mutation == "proposed":
        link["status"] = "PROPOSED"
    if mutation == "object":
        reference["object_ref"] = "content:another"
    if mutation == "missing":
        catalog.data["reference_contexts"] = []
    if mutation == "unverified":
        reference.pop("version_or_checksum")
    if mutation == "method":
        reference["object_kind"] = "METHOD"
        link["program_version"] = "version:SGN_PREMIERE"
    result = ReadSTMGAlignment(catalog).resolve(context()["institutional"], reference)
    assert result["status"] == "CONTENT_GAP"
    assert result["reference_scope"]["status"] == "CONTENT_GAP"
    assert "SELECTED_PASSAGE_CONTEXT_NOT_ADMITTED" in result["gaps"]


def test_passage_substitution_after_resolution_is_rejected_before_dispatch():
    service = app(Catalog(), ExplainedCourseDouble())
    original = service.reference
    service.reference = lambda selection: {**original(selection), "reference": {
        **original(selection)["reference"], "source_ref": "content:swapped"}}
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_REFERENCE_CHANGED"):
        prepare(service, context())
    assert service.generation.requests == []


def test_unscoped_contextual_content_does_not_enter_agent_evidence_pack():
    service = app(Catalog(), ExplainedCourseDouble())
    service.institutional_resolver = lambda selection, reference: ReadSTMGAlignment(Catalog()).resolve(selection, scoped_reference())
    def forbidden_reference(_):
        raise AssertionError("Unscoped content must not enter AG-02")
    service.reference = forbidden_reference
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_SOURCE_CONTEXT_GAP"):
        prepare(service, context())
    assert service.prepared == service.packs == service.plans == {}
    assert service.generation.requests == []


def test_sqlite_reference_projection_is_query_only_exact_and_bounded():
    # Declared in-memory fixture; no business database or Application seed access.
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE pedagogical_context(id TEXT, framework_version_id TEXT, framework_element_id TEXT, difficulty_level TEXT);
        CREATE TABLE resource_context(resource_id TEXT, context_id TEXT, role TEXT, status TEXT);
        INSERT INTO pedagogical_context VALUES ('context:unit', 'version:unit', 'question:unit', 'APPLICATION');
        INSERT INTO resource_context VALUES ('content:unit', 'context:unit', 'MAIN', 'ADMITTED');
    """)
    with pytest.raises(ValueError, match="INSTITUTIONAL_READ_ONLY_REQUIRED"):
        SQLiteInstitutionalCatalogAdapter(connection)
    connection.execute("PRAGMA query_only=ON")
    adapter = SQLiteInstitutionalCatalogAdapter(connection)
    assert adapter.read_reference_contexts("content:unit")[0]["program_version"] == "version:unit"
    assert adapter.read_reference_contexts("content:unit' OR 1=1 --") == ()
    connection.execute("PRAGMA query_only=OFF")
    connection.executemany("INSERT INTO resource_context VALUES (?, 'context:unit', 'MAIN', 'ADMITTED')", [("content:overflow",)] * 257)
    connection.execute("PRAGMA query_only=ON")
    with pytest.raises(ValueError, match="P0_REFERENCE_CONTEXT_BOUND"):
        adapter.read_reference_contexts("content:overflow")
    connection.close()


def unnumbered_question_catalog():
    catalog = Catalog()
    question = next(row for row in catalog.data["official_framework_element"] if row["id"] == "question:SGN_PREMIERE")
    question["official_label"] = "Comment organiser les activités ?"
    return catalog


def test_unnumbered_question_is_selectable_but_missing_theme_blocks_authorisation():
    catalog = unnumbered_question_catalog()
    query = ReadSTMGAlignment(catalog)
    frame = next(frame for frame in query.snapshot()["frames"] if frame["frame"] == "SGN_PREMIERE")
    assert frame["questions"][0] == {"question_ref": "question:SGN_PREMIERE", "label": "Comment organiser les activités ?", "theme_ref": None}
    data = context("SGN_PREMIERE")
    data["institutional"]["theme_ref"] = None
    double = ExplainedCourseDouble()
    authorisations = []
    double.authorize = lambda **kwargs: authorisations.append(kwargs) or True
    service = app(catalog, double)
    prepared = prepare(service, data)
    resolved = prepared["context"]["institutional_resolution"]
    assert resolved["question"]["id"] == "question:SGN_PREMIERE"
    assert resolved["theme_ref"] is None
    assert resolved["status"] == "CONTENT_GAP"
    assert resolved["gaps"] == ["THEME_RELATIONSHIP_UNRESOLVED"]
    assert prepared["agentic"]["evidence_pack"]["institutional_resolution"] == resolved
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_CONTENT_GAP"):
        service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})
    assert authorisations == double.requests == []


@pytest.mark.parametrize("unnumbered,theme", [(True, "theme:1"), (False, None)])
def test_missing_theme_cannot_be_replaced_or_used_for_a_numbered_question(unnumbered, theme):
    catalog = unnumbered_question_catalog() if unnumbered else Catalog()
    data = context("SGN_PREMIERE")
    data["institutional"]["theme_ref"] = theme
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_QUESTION_THEME"):
        prepare(app(catalog), data)


def test_unnumbered_question_does_not_bypass_programme_identity():
    catalog = unnumbered_question_catalog()
    data = context()
    data["institutional"].update(theme_ref=None, question_ref="question:SGN_PREMIERE")
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_QUESTION_THEME"):
        prepare(app(catalog), data)


@pytest.mark.parametrize("theme", ["", False, 1])
def test_unresolved_theme_is_null_not_an_empty_or_invalid_identifier(theme):
    data = context("SGN_PREMIERE")
    data["institutional"]["theme_ref"] = theme
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_ID"):
        P0Context(data)


def test_unnumbered_successor_export_and_review_keep_the_missing_theme_visible():
    catalog = Catalog()
    service = app(catalog, ExplainedCourseDouble())
    prepared = prepare(service, context())
    view = service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})["view"]
    parent = service.saved_source(view["production_ref"], view["version_ref"])
    catalog = unnumbered_question_catalog()
    requested = context("SGN_PREMIERE")
    requested["institutional"]["theme_ref"] = None
    child = ReframeCourseInbound(ReadSTMGAlignment(catalog).resolve).execute(parent, requested,
        title="Cours synthétique sans thème renseigné", sections=parent.p0_bundle.mutable_copy()["sections"],
        reference_selection={"notion_id": "notion:shared"}, evidence=service.evidence[parent.version_ref])
    blocks = ExportSavedCommand(None).preview(child, "student").blocks
    assert any(block.text == "Thème non renseigné · Comment organiser les activités ?" for block in blocks)
    assert not any("Thème None" in block.text for block in blocks)
    calls = []
    class ReviewCapture:
        def authorize(self, *, request):
            calls.append(request)
            return True
    service.review = ReviewCapture()
    service.records[child.version_ref] = child.p0_bundle
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_CONTENT_GAP"):
        service.execute("review", {"command_id": token_hex(16), "production_ref": child.production_ref,
                                  "version_ref": child.version_ref, "bundle_sha256": child.p0_bundle.sha256})
    assert calls == []
