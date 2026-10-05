"""Synthetic native catalog uses pinned identity strings, not actual public bytes."""
import copy

import pytest

from backend.adapters.outbound.resource_library.institutional_qualification_sqlite import (
    SQLiteInstitutionalQualificationAdapter,
)
from backend.modules.knowledge_reference.application.queries.qualified_institutional_corpus import (
    QualifiedInstitutionalCorpus,
)
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment
from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    OWNER_ADMISSION_SHA256,
)
from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
)
from backend.modules.pedagogical_design.contracts.dto.program_authority import (
    alignment_axes,
    authority_layers,
    require_supported_claims,
)
from tests.unit.test_institutional_qualification import connection, sample


def qualified_catalog(*, implicit=False, bts=False):
    data = sample()
    data["owner_decision_sha256"] = OWNER_ADMISSION_SHA256
    data["documents"][0]["sha256"] = ADMITTED_DOCUMENTS["A01"]
    data["versions"][0]["frame"] = "1STMG_MAN"
    if bts:
        data["versions"][0]["frame"] = "BTS CG - Annexe I"
        data["documents"][0].update(candidate_id="A04B", sha256=ADMITTED_DOCUMENTS["A04B"])
    for i, kind in enumerate(("THEME", "QUESTION", "CAPACITY")):
        row = copy.deepcopy(data["elements"][0])
        row.update(id="element:" + kind, element_type=kind, official_label="1.1 Synthétique" if kind == "QUESTION" else kind,
                   parent_ref="element:THEME" if kind in {"QUESTION", "CAPACITY"} else None, position=i + 2)
        data["elements"].append(row)
    data["elements"][0]["parent_ref"] = "element:QUESTION"
    if bts:
        for row in data["elements"][1:]:
            row["element_type"] = {"THEME": "PROCESS", "QUESTION": "ACTIVITY", "CAPACITY": "COMPETENCY"}[row["element_type"]]
            if row["id"] == "element:CAPACITY":
                row["parent_ref"] = "element:QUESTION"
    if implicit:
        data["attachments"][0]["disposition"] = data["notions"][0]["disposition"] = "VERIFIED_IMPLICIT"
    db = connection()
    db.execute("UPDATE official_framework SET code='1STMG_MAN'")
    if bts:
        db.execute("UPDATE official_framework SET code='BTS CG - Annexe I'")
    SQLiteInstitutionalQualificationAdapter(db).publish_qualification(InstitutionalQualification(data))
    catalog = {}
    for table in ("notion", "source", "document", "source_document", "official_framework", "official_framework_version",
                  "document_reference", "official_framework_element", "institutional_attachment"):
        cursor = db.execute("SELECT * FROM " + table)
        catalog[table] = [dict(zip([c[0] for c in cursor.description], row, strict=True)) for row in cursor.fetchall()]
    for frame in catalog["official_framework"]:
        frame["issuing_source_id"] = None  # Historical framework is preserved.
    catalog["institutional_qualifications"] = [data]
    db.close()
    return catalog


class Catalog:
    def __init__(self, data): self.data = data
    def read_institutional_catalog(self): return self.data
    def read_reference_contexts(self, ref): return ()


def resolution(data):
    selected = {"frame": "MANAGEMENT_PREMIERE", "education_level": "PREMIERE", "series": "STMG", "teaching_subject": "MANAGEMENT",
                "program_component": "SPECIALITE", "specific_track": None, "program_ref": "frame:test", "program_version": "version:test",
                "theme_ref": "element:THEME", "question_ref": "element:QUESTION", "capacity_refs": ["element:CAPACITY"],
                "notion_refs": ["notion:test-0"], "depth": "ANALYSIS"}
    reference = {"notion_id": "notion:test-0", "object_ref": "notion:test-0", "object_kind": "NOTION",
                 "passage_ref": "synthetic-passage", "version_or_checksum": "synthetic-version"}
    return ReadSTMGAlignment(Catalog(data)).resolve(selected, reference)


def test_native_proof_preferred_with_history_and_theme_capacity_scope():
    data = qualified_catalog()
    read = ReadSTMGAlignment(Catalog(data)).snapshot()
    assert len(read["frames"]) == len(read["historical_frames"]) == 1
    assert read["frames"][0]["authority"] == "OWNER_ADMITTED_VERSIONED_PROOF"
    result = resolution(data)
    assert result["status"] == "RESOLVED_ADMITTED"
    assert result["depth_authority"] == "LOCAL_PEDAGOGICAL_PROPOSAL" and result["official_depth"] is None
    assert result["capacities"][0]["capacity_ref"] == "element:CAPACITY"
    assert alignment_axes(result)["institutional_alignment"] == "VERIFIED_EXPLICIT"
    require_supported_claims("Conforme au programme", result)


@pytest.mark.parametrize("table,key,value", [
    ("document", "sha256", "c" * 64), ("document", "url", "https://example.test/other"),
    ("source", "status", "INACTIVE"), ("source_document", "source_role", "DISTRIBUTOR"),
    ("official_framework_version", "version_label", "OTHER"), ("official_framework", "code", "1STMG_SGN"),
    ("official_framework_element", "official_text", "substitution"), ("document_reference", "page_end", 7),
    ("institutional_attachment", "attachment_type", "INFERRED"), ("institutional_attachment", "status", "PROPOSED"),
    ("notion", "canonical_label", "homonyme"),
])
def test_mutated_native_proof_refused(table, key, value):
    data = qualified_catalog()
    row = data[table][-1] if table == "official_framework_version" else data[table][0]
    row[key] = value
    with pytest.raises(ValueError, match="INSTITUTIONAL_"):
        QualifiedInstitutionalCorpus(data)


def test_implicit_authority_layers_do_not_turn_local_passage_into_a_or_b():
    result = resolution(qualified_catalog(implicit=True))
    assert alignment_axes(result)["institutional_alignment"] == "VERIFIED_IMPLICIT"
    layers = authority_layers(result, [{"text": "Manuel synthétique"}], {"chapter": "local"})
    assert layers["institutional_evidence"] == [result]
    assert layers["disciplinary_evidence"] == layers["pedagogical_evidence"] == []
    with pytest.raises(ValueError, match="IMPLICIT"):
        require_supported_claims("Notion officiellement citée", result)
    with pytest.raises(ValueError, match="BTS_YEAR"):
        require_supported_claims("BTS CG2 officiellement prescrit", result)


@pytest.mark.parametrize("reference", [None, {"status": "ACTIVE"}, {"status": "RESOLVED_ADMITTED", "version_label": "UNKNOWN"}])
def test_manual_or_disciplinary_or_unknown_version_cannot_create_official_claim(reference):
    with pytest.raises(ValueError, match="UNVERIFIED"):
        require_supported_claims("Capacité officielle au programme officiel", reference)
    require_supported_claims("Proposition locale à relire", reference)


def test_owner_proof_removed_does_not_promote_active_rows():
    data = qualified_catalog()
    data["institutional_qualifications"] = []
    with pytest.raises(ValueError, match="P0_INSTITUTIONAL_QUESTION_THEME"):
        resolution(data)


def test_wrong_question_capacity_and_notion_are_not_inherited():
    data = qualified_catalog()
    data["institutional_qualifications"][0]["attachments"][0]["element_ref"] = "element:CAPACITY"
    data["institutional_attachment"][0]["framework_element_id"] = "element:CAPACITY"
    assert resolution(data)["status"] == "CONTENT_GAP"  # The theme capacity is not a question attachment.


def test_generic_scope_preserves_native_terms_and_refuses_official_bts_year():
    corpus = QualifiedInstitutionalCorpus(qualified_catalog())
    result = corpus.resolve_scope(version_ref="version:test", element_ref="element:QUESTION", notion_refs=("notion:test-0",))
    assert result["status"] == "RESOLVED_ADMITTED" and result["official_depth"] is None
    with pytest.raises(ValueError, match="LOCAL_YEAR"):
        corpus.resolve_scope(version_ref="version:test", element_ref="element:QUESTION", notion_refs=("notion:test-0",), local_year="BTS_CG_YEAR_2")
    with pytest.raises(ValueError, match="SCOPE_ELEMENT"):
        corpus.resolve_scope(version_ref="version:test", element_ref="other-program", notion_refs=("notion:test-0",))


def test_actual_create_command_refuses_unfounded_claim_after_transport_double():
    from secrets import token_hex

    from tests.unit.test_stmg_institutional_alignment import Catalog as Legacy
    from tests.unit.test_stmg_institutional_alignment import (
        ExplainedCourseDouble,
        app,
        context,
        prepare,
    )

    class ClaimDouble(ExplainedCourseDouble):
        def generate(self, *, request):
            output = super().generate(request=request)
            output["sections"][0]["text"] += " Cette capacité officielle est au programme officiel."
            return output

    service = app(Legacy(), ClaimDouble())
    prepared = prepare(service, context())
    assert set(("institutional_evidence", "disciplinary_evidence", "pedagogical_evidence", "generated_or_local_context")) <= set(prepared["agentic"]["evidence_pack"])
    assert prepared["agentic"]["plan"]["review_axes"]["institutional_alignment"] == "UNVERIFIED"
    with pytest.raises(ValueError, match="PROGRAM_ALIGNMENT_UNVERIFIED"):
        service.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})
    assert service.records == {}


def test_bts_scope_retains_process_activity_competency_and_local_year():
    corpus = QualifiedInstitutionalCorpus(qualified_catalog(bts=True))
    result = corpus.resolve_scope(version_ref="version:test", element_ref="element:QUESTION", notion_refs=("notion:test-0",), local_year="BTS_CG_YEAR_2")
    assert result["status"] == "RESOLVED_ADMITTED"
    assert result["element"]["element_type"] == "ACTIVITY"
    assert result["competencies"][0]["element_type"] == "COMPETENCY"
    assert result["year_authority"] == "LOCAL_PROGRESSION_ONLY"
    assert result["official_depth"] is None


@pytest.mark.parametrize("field", ["source_ref", "locator", "checksum_or_version"])
def test_course_reference_successor_rejects_identity_substitution(field):
    from backend.adapters.inbound.application.reframe_course import ReframeCourseInbound
    from tests.unit.test_course_chapter import child_fixture
    from tests.unit.test_stmg_institutional_alignment import context

    parent, _ = child_fixture()
    evidence = {}  # Binding rejection occurs before content validation.
    descriptor = dict(parent.p0_bundle.mutable_copy()["references"][0])
    descriptor.update(source_ref="notion:shared", locator="canonical:test", checksum_or_version="unit:canonical")
    selection = {"notion_id": "notion:shared", "object_ref": "notion:shared", "object_kind": "NOTION", "passage_ref": "canonical:test", "version_or_checksum": "unit:canonical"}
    descriptor[field] = "swapped"
    with pytest.raises(ValueError, match="COURSE_REFERENCE_SUCCESSOR_BINDING"):
        ReframeCourseInbound(ReadSTMGAlignment(CatalogLegacy()).resolve).execute(parent, context(), title=parent.p0_bundle.data["title"],
            sections=parent.p0_bundle.mutable_copy()["sections"], reference_selection=selection, reference_override=descriptor, evidence=evidence)


def CatalogLegacy():
    from tests.unit.test_stmg_institutional_alignment import Catalog as Legacy
    return Legacy()
