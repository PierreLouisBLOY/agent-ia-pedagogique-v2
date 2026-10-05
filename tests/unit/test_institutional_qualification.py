"""Synthetic qualification and SQLite copies; no private seed or official claims."""

import copy
import sqlite3

import pytest

from backend.adapters.inbound.application.institutional_qualification import (
    InstitutionalQualificationInbound,
)
from backend.adapters.outbound.resource_library.institutional_qualification_sqlite import (
    SQLiteInstitutionalQualificationAdapter,
)
from backend.modules.knowledge_reference.application.commands.admit_institutional_qualification import (
    AdmitInstitutionalQualification,
)
from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
)


def sample():
    return {
        "contract_id": "INSTITUTIONAL-QUALIFICATION-1.0",
        "owner_decision_sha256": "a" * 64,
        "documents": [
            {
                "id": "doc:test",
                "candidate_id": "A01",
                "title": "Source synthétique",
                "url": "https://example.test/programme",
                "sha256": "b" * 64,
                "publication_date": "2026-10-05",
                "source_ref": "source:test",
                "source_name": "Institution synthétique",
                "provenance": "UNIT_TEST",
                "pages": 10,
            }
        ],
        "versions": [
            {
                "id": "version:test",
                "framework_ref": "frame:test",
                "frame": "TEST_FRAME",
                "version_label": "TEST-V1",
                "publication_date": "2026-10-05",
                "document_ref": "doc:test",
            }
        ],
        "elements": [
            {
                "id": "element:test",
                "version_ref": "version:test",
                "parent_ref": None,
                "element_type": "KNOWLEDGE",
                "official_code": None,
                "official_label": "Notion synthétique 0",
                "official_text": "Prescription de test",
                "document_ref": "doc:test",
                "page": 4,
                "page_end": 4,
                "locator": "page 4, notion de test",
                "position": 1,
            }
        ],
        "attachments": [
            {
                "id": "attachment:test",
                "notion_ref": "notion:test-0",
                "element_ref": "element:test",
                "disposition": "VERIFIED_EXPLICIT",
                "justification": "Justification synthétique de test",
                "importance": None,
                "official_depth": None,
                "pedagogical_depth": "APPLICATION",
                "validated_by": "UNIT_TEST",
                "validated_at": "2026-10-05",
                "evidence_ref": "evidence:test",
            }
        ],
        "notions": [
            {
                "notion_ref": f"notion:test-{i}",
                "label": f"Notion synthétique {i}",
                "disposition": "VERIFIED_EXPLICIT" if i == 0 else "SOURCE_GAP",
                "reason": "Pièce synthétique ou preuve absente",
                "attachment_refs": ["attachment:test"] if i == 0 else [],
                "candidate_scopes": ["TEST_FRAME"],
            }
            for i in range(628)
        ],
        "regulatory_context": [],
    }


def connection():
    db = sqlite3.connect(":memory:", isolation_level=None)
    db.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE notion(id TEXT PRIMARY KEY,canonical_label TEXT,identity_status TEXT);
    CREATE TABLE source(id TEXT PRIMARY KEY,source_type TEXT,canonical_name TEXT,status TEXT);
    CREATE TABLE document(id TEXT PRIMARY KEY,document_type TEXT,title TEXT,publication_date TEXT,url TEXT,sha256 TEXT,language_code TEXT,document_status TEXT);
    CREATE TABLE source_document(source_id TEXT REFERENCES source(id),document_id TEXT REFERENCES document(id),source_role TEXT);
    CREATE TABLE official_framework(id TEXT PRIMARY KEY,code TEXT);
    CREATE TABLE official_framework_version(id TEXT PRIMARY KEY,framework_id TEXT REFERENCES official_framework(id),version_label TEXT,publication_date TEXT,valid_from TEXT,lifecycle_status TEXT,official_document_id TEXT REFERENCES document(id));
    CREATE TABLE document_reference(id TEXT PRIMARY KEY,document_id TEXT REFERENCES document(id),page_start INTEGER,page_end INTEGER,section TEXT,locator_text TEXT,original_excerpt TEXT);
    CREATE TABLE official_framework_element(id TEXT PRIMARY KEY,framework_version_id TEXT REFERENCES official_framework_version(id),parent_element_id TEXT REFERENCES official_framework_element(id),element_type TEXT,official_code TEXT,official_label TEXT,official_text TEXT,position INTEGER,document_reference_id TEXT REFERENCES document_reference(id));
    CREATE TABLE institutional_attachment(id TEXT PRIMARY KEY,notion_id TEXT REFERENCES notion(id),framework_element_id TEXT REFERENCES official_framework_element(id),attachment_type TEXT CHECK(attachment_type IN ('EXPLICIT','IMPLICIT','INFERRED')),importance_level TEXT,depth_level TEXT,origin_type TEXT CHECK(origin_type IN ('OFFICIAL','USER','AI_INFERENCE')),status TEXT);
    CREATE TABLE evidence(id TEXT PRIMARY KEY,evidence_type TEXT,content TEXT,status TEXT);
    CREATE TABLE evidence_document_reference(evidence_id TEXT REFERENCES evidence(id),document_reference_id TEXT REFERENCES document_reference(id));
    CREATE TABLE audit_event(id TEXT PRIMARY KEY,event_type TEXT,reason TEXT,payload_json TEXT);
    INSERT INTO official_framework VALUES('frame:test','TEST_FRAME');
    INSERT INTO official_framework_version VALUES('version:historic','frame:test','OLD',NULL,NULL,'PUBLISHED',NULL);
    """)
    db.executemany(
        "INSERT INTO notion VALUES(?,?,'CANONICAL')",
        [(f"notion:test-{i}", f"Notion synthétique {i}") for i in range(628)],
    )
    return db


@pytest.mark.parametrize(
    "kind",
    [
        "count",
        "owner",
        "hash",
        "cycle",
        "page",
        "wrong_version",
        "no_attachment",
        "implicit_as_explicit",
        "extra_field",
        "duplicate",
        "scope",
        "duplicate_ref",
    ],
)
def test_mutations_fail_closed_before_publish(kind):
    data = sample()
    if kind == "count":
        data["notions"].pop()
    elif kind == "owner":
        data["owner_decision_sha256"] = "c" * 64
    elif kind == "hash":
        data["documents"][0]["sha256"] = "d" * 64
    elif kind == "cycle":
        data["elements"][0]["parent_ref"] = "element:test"
    elif kind == "page":
        data["elements"][0]["page"] = 11
    elif kind == "wrong_version":
        data["elements"][0]["version_ref"] = "version:other"
    elif kind == "no_attachment":
        data["attachments"] = []
        data["notions"][0]["attachment_refs"] = []
    elif kind == "implicit_as_explicit":
        data["attachments"][0]["disposition"] = "VERIFIED_IMPLICIT"
    elif kind == "extra_field":
        data["documents"][0]["status"] = "ADMITTED"
    elif kind == "duplicate":
        data["notions"][1] = copy.deepcopy(data["notions"][0])
    elif kind == "scope":
        data["notions"][0]["candidate_scopes"] = [None]
    elif kind == "duplicate_ref":
        data["notions"][0]["attachment_refs"] *= 2

    class Port:
        def publish_qualification(self, qualified):
            pytest.fail("Invalid proof reached persistence")

    inbound = InstitutionalQualificationInbound(
        AdmitInstitutionalQualification(
            Port(), owner_decision_sha256="a" * 64, admitted_document_hashes={"A01": "b" * 64}
        )
    )
    with pytest.raises(ValueError):
        inbound.execute(data)


def test_publish_preserves_history_and_lifecycle_and_reopens_exact_proof():
    db = connection()
    adapter = SQLiteInstitutionalQualificationAdapter(db)
    command = AdmitInstitutionalQualification(
        adapter, owner_decision_sha256="a" * 64, admitted_document_hashes={"A01": "b" * 64}
    )
    data = sample()
    receipt = command.execute(data)
    assert receipt["notion_count"] == 628 and receipt["provider_calls"] == 0
    assert db.execute("SELECT count(*) FROM notion").fetchone()[0] == 628
    assert db.execute(
        "SELECT version_label,official_document_id FROM official_framework_version WHERE id='version:historic'"
    ).fetchone() == ("OLD", None)
    assert db.execute("SELECT document_status FROM document").fetchone()[0] == "ACTIVE"
    assert db.execute("SELECT origin_type,status FROM institutional_attachment").fetchone() == (
        "OFFICIAL",
        "VALIDATED",
    )
    assert db.execute("SELECT count(*) FROM evidence_document_reference").fetchone()[0] == 1
    assert command.execute(data) == receipt
    assert db.execute("SELECT count(*) FROM evidence").fetchone()[0] == 1
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    original = copy.deepcopy(data)
    frozen = InstitutionalQualification(data)
    data["notions"][0]["label"] = "Mutation externe"
    assert frozen.as_dict() == original
    db.close()


def test_corpus_keeps_generic_sensitive_value_scanner_active_per_row():
    data = sample()
    data["notions"][627]["reason"] = "sk-" + "a" * 48
    with pytest.raises(ValueError, match="CREDENTIAL_LIKE"):
        InstitutionalQualification(data)


def test_implicit_attachment_remains_implicit_with_no_official_year_assignment():
    data = sample()
    data["attachments"][0]["disposition"] = "VERIFIED_IMPLICIT"
    data["notions"][0]["disposition"] = "VERIFIED_IMPLICIT"
    db = connection()
    SQLiteInstitutionalQualificationAdapter(db).publish_qualification(InstitutionalQualification(data))
    assert db.execute("SELECT attachment_type,depth_level FROM institutional_attachment").fetchone() == ("IMPLICIT", "APPLICATION")
    assert data["attachments"][0]["official_depth"] is None
    db.close()


@pytest.mark.parametrize("kind", ["label", "framework", "source_collision", "document_collision"])
def test_store_mutation_rolls_back_without_partial_admission(kind):
    db = connection()
    if kind == "label":
        db.execute("UPDATE notion SET canonical_label='Autre' WHERE id='notion:test-0'")
    elif kind == "framework":
        db.execute("UPDATE official_framework SET code='OTHER_FRAME'")
    elif kind == "source_collision":
        db.execute("INSERT INTO source VALUES('source:test','PLATFORM','Manuel','ACTIVE')")
    else:
        db.execute("INSERT INTO document(id,title) VALUES('doc:test','Autre pièce')")
    before = list(db.iterdump())
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        SQLiteInstitutionalQualificationAdapter(db).publish_qualification(
            InstitutionalQualification(sample())
        )
    assert list(db.iterdump()) == before
    db.close()
