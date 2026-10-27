"""Synthetic-only Application admission of an exact passage; no real corpus."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.inbound.application.exact_passage_context import ExactPassageContextInbound
from backend.adapters.inbound.application.stmg_alignment import STMGAlignmentInbound
from backend.adapters.outbound.resource_library.exact_passage_context_sqlite import (
    SQLiteExactPassageContextWriter,
)
from backend.adapters.outbound.resource_library.institutional_sqlite import (
    SQLiteInstitutionalCatalogAdapter,
)
from backend.modules.knowledge_reference.application.commands.admit_exact_passage_context import (
    AdmitExactPassageContext,
)
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment
from backend.modules.knowledge_reference.contracts.dto.exact_passage_context import (
    CONTROL_SCHEMA,
    DECISION_SCHEMA,
    REQUEST_SCHEMA,
    selection_sha256,
)
from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.knowledge_reference.ports.outbound.exact_passage_context import PassageEvidence
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint

EXCERPT_A = "Extrait synthétique A : acteurs et valeurs."
EXCERPT_B = "Extrait synthétique B : une autre organisation."
PROVENANCE = "b" * 64
CHANNEL = "c" * 64
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
FRAME = "SGN_PREMIERE"
SPEC = STMG_FRAMES[FRAME]


def _catalog() -> dict[str, object]:
    return {
        "official_framework": [{"id": "program:synthetic", "code": SPEC[5],
                                "issuing_source_id": "source:synthetic"}],
        "official_framework_version": [{"id": "version:synthetic", "framework_id": "program:synthetic",
                                        "version_label": "SYNTHETIC-V1", "lifecycle_status": "PUBLISHED",
                                        "official_document_id": "document:synthetic"}],
        "official_framework_element": [
            {"id": "question:synthetic", "framework_version_id": "version:synthetic",
             "parent_element_id": None, "element_type": "QUESTION", "official_label": "1.1 Question synthétique",
             "document_reference_id": "locator:synthetic"},
            {"id": "capacity:synthetic", "framework_version_id": "version:synthetic",
             "parent_element_id": "question:synthetic", "element_type": "CAPACITY",
             "official_label": "Capacité synthétique", "document_reference_id": "locator:synthetic"},
        ],
        "institutional_attachment": [{"id": "attachment:synthetic", "notion_id": "notion:synthetic",
            "framework_element_id": "question:synthetic", "attachment_type": "EXPLICIT",
            "status": "ADMITTED", "origin_type": "OFFICIAL_DOCUMENT", "depth_level": "APPLICATION"}],
        "pedagogical_context": [], "notion_context": [],
        "notion": [{"id": "notion:synthetic", "canonical_label": "Notion synthétique",
                    "identity_status": "CANONICAL"}],
        "document": [{"id": "document:synthetic", "sha256": "d" * 64,
                      "document_status": "ADMITTED"}],
        "document_reference": [{"id": "locator:synthetic", "document_id": "document:synthetic"}],
        "source": [{"id": "source:synthetic", "status": "ADMITTED"}],
    }


def _selection() -> dict[str, object]:
    return {"contract_id": "STMG-INSTITUTIONAL-CONTEXT-1.0", "frame": FRAME,
            "education_level": SPEC[1], "series": "STMG", "teaching_subject": SPEC[2],
            "program_ref": "program:synthetic", "program_version": "version:synthetic",
            "program_component": SPEC[3], "specific_track": SPEC[4], "theme_ref": "theme:1",
            "question_ref": "question:synthetic", "capacity_refs": ["capacity:synthetic"],
            "notion_refs": ["notion:synthetic"], "depth": "APPLICATION"}


def _db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE official_framework_version(id TEXT,framework_id TEXT);
            CREATE TABLE official_framework_element(id TEXT,framework_version_id TEXT,parent_element_id TEXT,element_type TEXT);
            CREATE TABLE pedagogical_context(id TEXT,framework_version_id TEXT,framework_element_id TEXT,difficulty_level TEXT);
            CREATE TABLE notion(id TEXT,identity_status TEXT);
            CREATE TABLE resource_context(resource_id TEXT,context_id TEXT,role TEXT,status TEXT);
            CREATE TABLE b32_synthetic_fixture_marker(scope TEXT NOT NULL);
            INSERT INTO official_framework_version VALUES ('version:synthetic','program:synthetic');
            INSERT INTO official_framework_element VALUES ('question:synthetic','version:synthetic',NULL,'QUESTION');
            INSERT INTO official_framework_element VALUES ('capacity:synthetic','version:synthetic','question:synthetic','CAPACITY');
            INSERT INTO pedagogical_context VALUES ('context:synthetic','version:synthetic','question:synthetic','APPLICATION');
            INSERT INTO notion VALUES ('notion:synthetic','CANONICAL');
            INSERT INTO resource_context VALUES ('content:synthetic','context:synthetic','MAIN','ADMITTED');
            INSERT INTO b32_synthetic_fixture_marker VALUES ('LOCAL_B_ONLY');
        """)
        connection.commit()
    finally:
        connection.close()


class Evidence:
    def __init__(self, text: str = EXCERPT_A, *, version: str = "SYNTHETIC-V1",
                 allowed: bool = True, sensitive: bool = False) -> None:
        self.text = text
        self.version = version
        self.allowed = allowed
        self.sensitive = sensitive

    def read_passage(self, object_ref: str, passage_ref: str) -> PassageEvidence | None:
        if object_ref != "content:synthetic" or passage_ref != "passage:A":
            return None
        return PassageEvidence(self.version, self.text.encode("utf-8"), PROVENANCE,
                               self.allowed, self.sensitive, "UNKNOWN")


class Catalog:
    def __init__(self, reader: SQLiteInstitutionalCatalogAdapter) -> None:
        self.reader = reader
        self.data = _catalog()

    def read_institutional_catalog(self) -> dict[str, object]:
        return copy.deepcopy(self.data)

    def read_reference_contexts(self, object_ref: str) -> tuple[dict[str, object], ...]:
        return self.reader.read_reference_contexts(object_ref)

    def read_exact_passage_contexts(self, object_kind: str, object_ref: str,
                                    passage_ref: str, version_or_checksum: str,
                                    excerpt_sha256: str, context_ref: str,
                                    selection_sha256: str) -> tuple[dict[str, object], ...]:
        return self.reader.read_exact_passage_contexts(
            object_kind, object_ref, passage_ref, version_or_checksum,
            excerpt_sha256, context_ref, selection_sha256,
        )


def _request(destination: Path, source_sha: str) -> dict[str, object]:
    return {"schema": REQUEST_SCHEMA, "source_candidate_sha256": source_sha,
            "fresh_destination": str(destination), "object_kind": "PEDAGOGICAL_CONTENT",
            "object_ref": "content:synthetic", "passage_ref": "passage:A",
            "version_or_checksum": "SYNTHETIC-V1",
            "excerpt_sha256": hashlib.sha256(EXCERPT_A.encode()).hexdigest(),
            "program_ref": "program:synthetic", "program_version_ref": "version:synthetic",
            "question_ref": "question:synthetic", "notion_ref": "notion:synthetic",
            "depth": "APPLICATION", "capacity_refs": ["capacity:synthetic"],
            "context_ref": "context:synthetic", "role": "MAIN",
            "relation_status": "ADMITTED", "available_authority": "UNKNOWN",
            "provenance_sha256": PROVENANCE,
            "issued_at_utc": "2026-10-19T11:00:00Z", "expires_at_utc": "2026-10-19T13:00:00Z",
            "source_native_identity_sha256": "e" * 64,
            "destination_parent_native_identity_sha256": "f" * 64}


def _decision(request: dict[str, object]) -> dict[str, object]:
    return {"schema": DECISION_SCHEMA, "request_sha256": fingerprint(request),
            "source_candidate_sha256": request["source_candidate_sha256"],
            "fresh_destination": request["fresh_destination"],
            "object_ref": request["object_ref"], "passage_ref": request["passage_ref"],
            "version_or_checksum": request["version_or_checksum"],
            "excerpt_sha256": request["excerpt_sha256"],
            "selection_sha256": selection_sha256(request),
            "context_ref": request["context_ref"],
            "scope": "ONE_LOCAL_EXACT_PASSAGE_RELATION",
            "issued_at_utc": request["issued_at_utc"],
            "expires_at_utc": request["expires_at_utc"]}


def _control(request: dict[str, object], decision: dict[str, object]) -> dict[str, object]:
    owner_sha = fingerprint(decision)
    return {"schema": CONTROL_SCHEMA, "request_sha256": fingerprint(request),
            "owner_decision_sha256": owner_sha, "expected_owner_decision_sha256": owner_sha,
            "decision_channel_sha256": CHANNEL}


@pytest.fixture
def scenario(tmp_path: Path):
    source = tmp_path / "source-synthetic.sqlite"
    candidate = tmp_path / "candidate-synthetic.sqlite"
    _db(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    shutil.copyfile(source, candidate)
    writer_connection = sqlite3.connect(candidate, isolation_level=None)
    writer = SQLiteExactPassageContextWriter(writer_connection, synthetic_root=tmp_path)
    request = _request(candidate, source_sha)
    decision = _decision(request)
    control = _control(request, decision)
    evidence = Evidence()
    command = AdmitExactPassageContext(
        writer, evidence, expected_owner_sha256=fingerprint(decision),
        expected_channel_sha256=CHANNEL, expected_source_sha256=source_sha,
        expected_destination=str(candidate),
        expected_source_native_identity_sha256="e" * 64,
        expected_destination_parent_native_identity_sha256="f" * 64,
    )
    try:
        yield source, candidate, source_sha, writer_connection, writer, request, decision, control, evidence, command
    finally:
        writer_connection.close()


def _reference(passage: str = "passage:A") -> dict[str, object]:
    return {"notion_id": "notion:synthetic", "object_kind": "PEDAGOGICAL_CONTENT",
            "object_ref": "content:synthetic", "passage_ref": passage,
            "version_or_checksum": "SYNTHETIC-V1",
            "excerpt_sha256": hashlib.sha256(EXCERPT_A.encode()).hexdigest(),
            "provenance_sha256": PROVENANCE, "context_ref": "context:synthetic"}


def test_one_approved_passage_is_read_back_without_admitting_sibling(scenario):
    source, candidate, source_sha, _, _, request, decision, control, _, command = scenario
    receipt = ExactPassageContextInbound(command).execute(request, decision, control, now=NOW)
    assert receipt["relations_added"] == 1
    assert receipt["available_authority"] == "UNKNOWN"
    assert receipt["provider_calls"] == 0
    assert receipt["readback_verified"] is True
    assert receipt["decision_control_sha256"] == fingerprint(control)
    assert receipt["source_candidate_sha256"] == source_sha
    assert receipt["fresh_destination_sha256"] == fingerprint(str(candidate))
    assert EXCERPT_A not in json.dumps(receipt)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
    reader_connection = sqlite3.connect(candidate)
    try:
        reader_connection.execute("PRAGMA query_only=ON")
        inbound = STMGAlignmentInbound(ReadSTMGAlignment(Catalog(SQLiteInstitutionalCatalogAdapter(reader_connection))))
        a = inbound.resolve(_selection(), _reference(), mode="PASSAGE_EXACT_V2")
        b = inbound.resolve(_selection(), _reference("passage:B"), mode="PASSAGE_EXACT_V2")
        assert a["status"] == "RESOLVED_ADMITTED"
        assert a["reference_scope"]["relationships"][0]["owner_decision_sha256"] == fingerprint(decision)
        assert a["reference_scope"]["relationships"][0]["row_sha256"] == receipt["relation_sha256"]
        assert b["status"] == "CONTENT_GAP"
        assert b["reference_scope"]["relationships"] == []
    finally:
        reader_connection.close()


@pytest.mark.parametrize("changed", ["version_or_checksum", "excerpt_sha256", "context_ref", "depth"])
def test_exact_reader_refuses_substitution_after_admission(scenario, changed):
    _, candidate, _, _, _, request, decision, control, _, command = scenario
    command.execute(request, decision, control, now=NOW)
    connection = sqlite3.connect(candidate)
    try:
        connection.execute("PRAGMA query_only=ON")
        inbound = STMGAlignmentInbound(ReadSTMGAlignment(Catalog(SQLiteInstitutionalCatalogAdapter(connection))))
        reference = _reference()
        selection = _selection()
        if changed == "depth":
            selection["depth"] = "ANALYSIS"
        else:
            reference[changed] = {"version_or_checksum": "SYNTHETIC-V2",
                                  "excerpt_sha256": "a" * 64,
                                  "context_ref": "context:other"}[changed]
        result = inbound.resolve(selection, reference, mode="PASSAGE_EXACT_V2")
        assert result["status"] == "CONTENT_GAP"
        assert result["reference_scope"]["relationships"] == []
    finally:
        connection.close()


@pytest.mark.parametrize("changed", ["version_or_checksum", "excerpt_sha256", "context_ref", "depth"])
def test_divergent_request_is_rejected_before_relation(scenario, changed):
    _, _, _, connection, _, request, _, _, _, command = scenario
    altered = dict(request)
    altered[changed] = {"version_or_checksum": "SYNTHETIC-V2", "excerpt_sha256": "a" * 64,
                        "context_ref": "context:other", "depth": "ANALYSIS"}[changed]
    decision = _decision(altered)
    control = _control(altered, decision)
    command.expected_owner_sha256 = fingerprint(decision)
    with pytest.raises(ValueError):
        ExactPassageContextInbound(command).execute(altered, decision, control, now=NOW)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='resource_passage_context_v2'").fetchone() is None


def test_approval_is_bound_to_request_and_external_expected_hash(scenario):
    _, _, _, connection, _, request, decision, control, _, command = scenario
    wrong = dict(control)
    wrong["expected_owner_decision_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="EXACT_PASSAGE_ADOPTION_REQUIRED"):
        ExactPassageContextInbound(command).execute(request, decision, wrong, now=NOW)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='resource_passage_context_v2'").fetchone() is None


def test_ineligible_independent_source_and_repeat_are_refused(scenario):
    _, _, _, connection, _, request, decision, control, evidence, command = scenario
    evidence.text = EXCERPT_B
    with pytest.raises(ValueError, match="EXACT_PASSAGE_SOURCE_INELIGIBLE"):
        command.execute(request, decision, control, now=NOW)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='resource_passage_context_v2'").fetchone() is None
    evidence.text = EXCERPT_A
    command.execute(request, decision, control, now=NOW)
    with pytest.raises(ValueError, match="EXACT_PASSAGE_FRESH_COPY_REQUIRED"):
        command.execute(request, decision, control, now=NOW)
    assert connection.execute("SELECT count(*) FROM resource_passage_context_v2").fetchone()[0] == 1


def test_postcommit_read_failure_reports_committed_unverified_without_leak(scenario):
    _, _, _, connection, writer, request, decision, control, _, command = scenario

    class FailingReadback:
        def validate_scope(self, data):
            writer.validate_scope(data)

        def add_one(self, data, *, selection_sha256, owner_decision_sha256):
            return writer.add_one(data, selection_sha256=selection_sha256,
                                  owner_decision_sha256=owner_decision_sha256)

        def read_exact(self, data, *, selection_sha256):
            raise RuntimeError("private synthetic diagnostic marker")

    command.port = FailingReadback()
    receipt = command.execute(request, decision, control, now=NOW)
    assert receipt["relations_added"] == 1
    assert receipt["readback_verified"] is False
    assert receipt["status"] == "SYNTHETIC_COMMITTED_READBACK_UNVERIFIED_STOP"
    assert "private synthetic diagnostic marker" not in json.dumps(receipt)
    assert connection.execute("SELECT count(*) FROM resource_passage_context_v2").fetchone()[0] == 1


def test_legacy_object_relation_is_not_exact_admission(scenario):
    _, candidate, _, _, _, _, _, _, _, _ = scenario
    reader_connection = sqlite3.connect(candidate)
    try:
        reader_connection.execute("PRAGMA query_only=ON")
        inbound = STMGAlignmentInbound(ReadSTMGAlignment(Catalog(SQLiteInstitutionalCatalogAdapter(reader_connection))))
        exact = inbound.resolve(_selection(), _reference(), mode="PASSAGE_EXACT_V2")
        legacy = inbound.resolve(_selection(), _reference(), mode="LEGACY")
        assert exact["status"] == "CONTENT_GAP"
        assert legacy["reference_scope"]["status"] == "EXACT_CONTEXT_ADMITTED"
        with pytest.raises(ValueError, match="EXACT_PASSAGE_MODE"):
            inbound.resolve(_selection(), _reference(), mode="UNKNOWN_MODE")
    finally:
        reader_connection.close()


def test_writer_refuses_unmarked_or_read_only_synthetic_database(tmp_path: Path):
    candidate = tmp_path / "candidate-synthetic.sqlite"
    _db(candidate)
    connection = sqlite3.connect(candidate, isolation_level=None)
    try:
        connection.execute("DELETE FROM b32_synthetic_fixture_marker")
        with pytest.raises(ValueError, match="EXACT_PASSAGE_SYNTHETIC_TARGET_REQUIRED"):
            SQLiteExactPassageContextWriter(connection, synthetic_root=tmp_path)
        connection.execute("INSERT INTO b32_synthetic_fixture_marker VALUES ('LOCAL_B_ONLY')")
        connection.execute("PRAGMA query_only=ON")
        with pytest.raises(ValueError, match="EXACT_PASSAGE_WRITER_REQUIRED"):
            SQLiteExactPassageContextWriter(connection, synthetic_root=tmp_path)
    finally:
        connection.close()


def test_writer_refuses_approved_y_when_connected_to_synthetic_x(scenario, tmp_path: Path):
    source, actual_x, source_sha, connection, _, _, _, _, _, command = scenario
    approved_y = tmp_path / "approved-y-synthetic.sqlite"
    _db(approved_y)
    actual_before = hashlib.sha256(actual_x.read_bytes()).hexdigest()
    approved_before = hashlib.sha256(approved_y.read_bytes()).hexdigest()
    request = _request(approved_y, source_sha)
    decision = _decision(request)
    control = _control(request, decision)
    command.expected_destination = str(approved_y)
    command.expected_owner_sha256 = fingerprint(decision)

    with pytest.raises(ValueError, match="EXACT_PASSAGE_DESTINATION_MISMATCH"):
        command.execute(request, decision, control, now=NOW)

    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name='resource_passage_context_v2'"
    ).fetchone() is None
    with sqlite3.connect(approved_y) as approved_connection:
        assert approved_connection.execute(
            "SELECT name FROM sqlite_master WHERE name='resource_passage_context_v2'"
        ).fetchone() is None
    assert hashlib.sha256(actual_x.read_bytes()).hexdigest() == actual_before
    assert hashlib.sha256(approved_y.read_bytes()).hexdigest() == approved_before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
