"""Synthetic proof mechanics; no new institutional or disciplinary admission."""
import copy

import pytest

from backend.adapters.inbound.application.institutional_catalog import InstitutionalCatalogInbound
from backend.modules.knowledge_reference.application.queries.inspect_institutional_catalog import (
    InspectInstitutionalCatalog,
)
from backend.modules.knowledge_reference.application.queries.qualified_institutional_corpus import (
    QualifiedInstitutionalCorpus,
)
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment
from tests.unit.test_qualified_institutional_corpus import Catalog, qualified_catalog


def test_application_treatment_covers_exact_universe_and_traceable_relation():
    catalog = Catalog(qualified_catalog())
    result = InstitutionalCatalogInbound(InspectInstitutionalCatalog(catalog)).treatment()
    assert result["notion_count"] == 628
    assert len({n["notion_ref"] for n in result["notions"]}) == 628
    notion = result["notions"][0]
    assert notion["disposition"] == "VERIFIED_EXPLICIT"
    relation = notion["relations"][0]
    assert relation["relation_type"] == "EXPLICIT"
    assert relation["framework"]["frame"] == "1STMG_MAN"
    assert relation["element"]["page"] == 4
    assert relation["element"]["locator"]
    assert relation["document_provenance"]["sha256"]
    assert {c["id"] for c in relation["capabilities"]} == {"element:CAPACITY"}
    assert relation["qualification_sha256"] in result["qualification_sha256s"]
    assert relation["teacher_acceptance"] == "NOT_PERFORMED"
    assert notion["disciplinary_authority"] == "SEPARATE_EVIDENCE_REQUIRED"
    assert catalog.data["institutional_qualifications"][0]["notions"][0]["disposition"] == "VERIFIED_EXPLICIT"


def test_matrix_uses_verified_proof_without_propagating_management_to_sgn():
    matrix = ReadSTMGAlignment(Catalog(qualified_catalog())).matrix()
    scopes = {s["frame"]: s for s in matrix["notions"][0]["scopes"]}
    assert scopes["MANAGEMENT_PREMIERE"]["status"] == "RESOLVED_ADMITTED"
    link = scopes["MANAGEMENT_PREMIERE"]["relationships"][0]
    assert link["qualification"]["relation_type"] == "EXPLICIT"
    assert link["qualification"]["document_provenance"]["candidate_id"] == "A01"
    assert scopes["SGN_PREMIERE"]["relationships"] == []
    assert scopes["SGN_PREMIERE"]["status"] == "CONTENT_GAP"
    assert scopes["MSDGN_TERMINALE_COMMON"]["relationships"] == []


def test_implicit_remains_implicit_in_treatment_and_matrix():
    catalog = Catalog(qualified_catalog(implicit=True))
    notion = QualifiedInstitutionalCorpus(catalog.data).treatment()["notions"][0]
    assert notion["disposition"] == "VERIFIED_IMPLICIT"
    assert notion["relations"][0]["relation_type"] == "IMPLICIT"
    scopes = ReadSTMGAlignment(catalog).matrix()["notions"][0]["scopes"]
    assert scopes[0]["relationships"][0]["qualification"]["disposition"] == "VERIFIED_IMPLICIT"


def test_active_native_rows_without_owner_proof_never_gain_admission():
    data = qualified_catalog()
    data["institutional_qualifications"] = []
    result = QualifiedInstitutionalCorpus(data).treatment()
    assert result["qualification_sha256s"] == []
    assert all(n["relations"] == [] and n["disposition"] == "SOURCE_GAP"
               for n in result["notions"])
    scopes = ReadSTMGAlignment(Catalog(data)).matrix()["notions"][0]["scopes"]
    assert scopes[0]["status"] == "LINKS_REQUIRE_ADMISSION"
    assert scopes[0]["relationships"][0]["qualification"] is None


@pytest.mark.parametrize("table,key,value", [
    ("document", "sha256", "e" * 64),
    ("official_framework_element", "official_text", "changed source"),
    ("document_reference", "locator_text", "changed passage"),
    ("institutional_attachment", "status", "PROPOSED"),
])
def test_treatment_refuses_changed_proof_before_projection(table, key, value):
    data = qualified_catalog()
    data[table][0][key] = value
    with pytest.raises(ValueError, match="INSTITUTIONAL_"):
        InstitutionalCatalogInbound(InspectInstitutionalCatalog(Catalog(data))).treatment()


def test_proven_no_framework_and_missing_source_are_different_dispositions():
    data = qualified_catalog()
    proof = data["institutional_qualifications"][0]
    proof["notions"][1].update(disposition="NO_APPLICABLE_FRAMEWORK",
                             reason="Synthetic bounded proof of absence.")
    proof["notions"][2].update(disposition="HUMAN_REVIEW_REQUIRED",
                             reason="Synthetic ambiguous disciplinary equivalent.")
    result = QualifiedInstitutionalCorpus(data).treatment()["notions"]
    assert result[1]["disposition"] == "NO_APPLICABLE_FRAMEWORK"
    assert result[2]["disposition"] == "HUMAN_REVIEW_REQUIRED"
    assert result[3]["disposition"] == "SOURCE_GAP"
    assert all(result[i]["relations"] == [] for i in (1, 2, 3))


def test_bts_relations_keep_process_activity_competency_and_local_progression():
    result = QualifiedInstitutionalCorpus(qualified_catalog(bts=True)).treatment()
    relation = result["notions"][0]["relations"][0]
    assert relation["year_authority"] == "LOCAL_PROGRESSION_ONLY"
    assert {a["element_type"] for a in relation["ancestors"]} >= {"PROCESS", "ACTIVITY"}
    assert relation["capabilities"][0]["element_type"] == "COMPETENCY"
    assert "local_year" not in relation
    assert relation["official_depth"] is None


def test_historical_merged_identity_is_preserved_but_not_counted_as_canonical():
    data = qualified_catalog()
    data["notion"].append({"id": "notion:merged-alias", "canonical_label": "Alias",
                          "identity_status": "MERGED"})
    before = copy.deepcopy(data)
    result = QualifiedInstitutionalCorpus(data).treatment()
    assert result["notion_count"] == 628
    assert all(n["notion_ref"] != "notion:merged-alias" for n in result["notions"])
    assert data == before
