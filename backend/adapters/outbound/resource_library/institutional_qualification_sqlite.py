"""Materialize a qualified corpus using existing tables, in an isolated candidate."""

import json
import sqlite3

from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items


class SQLiteInstitutionalQualificationAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def publish_qualification(self, qualification: InstitutionalQualification) -> None:
        conn = self.connection
        data = qualification.as_dict()
        canonical = {
            str(r[0]): str(r[1])
            for r in conn.execute(
                "SELECT id,canonical_label FROM notion WHERE identity_status='CANONICAL'"
            )
        }
        if canonical != {
            str(r["notion_ref"]): str(r["label"]) for r in items(data["notions"], 628)
        }:
            raise ValueError("INSTITUTIONAL_CANONICAL_UNIVERSE_CHANGED")
        for version in items(data["versions"]):
            frame = conn.execute(
                "SELECT code FROM official_framework WHERE id=?", (version["framework_ref"],)
            ).fetchone()
            if frame is None or frame[0] != version["frame"]:
                raise ValueError("INSTITUTIONAL_FRAMEWORK_ID_CHANGED")
        proof_ref = "evidence:institutional-qualification-" + qualification.sha256[:24]
        prior = conn.execute("SELECT content FROM evidence WHERE id=?", (proof_ref,)).fetchone()
        serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if prior is not None:
            if prior[0] != serialized:
                raise ValueError("INSTITUTIONAL_REPLAY_CONFLICT")
            return
        baseline_violations = {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}
        conn.execute("BEGIN IMMEDIATE")
        try:
            for doc in items(data["documents"]):
                source = conn.execute(
                    "SELECT source_type,canonical_name,status FROM source WHERE id=?",
                    (doc["source_ref"],),
                ).fetchone()
                if source is not None and tuple(source) != (
                    "INSTITUTION",
                    doc["source_name"],
                    "ACTIVE",
                ):
                    raise ValueError("INSTITUTIONAL_SOURCE_ID_CONFLICT")
                conn.execute(
                    "INSERT OR IGNORE INTO source (id,source_type,canonical_name,status) VALUES (?,'INSTITUTION',?,'ACTIVE')",
                    (doc["source_ref"], doc["source_name"]),
                )
                conn.execute(
                    "INSERT INTO document (id,document_type,title,publication_date,url,sha256,language_code,document_status) VALUES (?,'OTHER',?,?,?,?,'fr','ACTIVE')",
                    (doc["id"], doc["title"], doc["publication_date"], doc["url"], doc["sha256"]),
                )
                conn.execute(
                    "INSERT INTO source_document (source_id,document_id,source_role) VALUES (?,?,'PRODUCER')",
                    (doc["source_ref"], doc["id"]),
                )
            for version in items(data["versions"]):
                conn.execute(
                    "INSERT INTO official_framework_version (id,framework_id,version_label,publication_date,valid_from,lifecycle_status,official_document_id) VALUES (?,?,?,?,?,'PUBLISHED',?)",
                    (
                        version["id"],
                        version["framework_ref"],
                        version["version_label"],
                        version["publication_date"],
                        version["publication_date"],
                        version["document_ref"],
                    ),
                )
            pending = list(items(data["elements"], 3000))
            inserted: set[str] = set()
            while pending:
                ready = [
                    row
                    for row in pending
                    if row["parent_ref"] is None or row["parent_ref"] in inserted
                ]
                if not ready:
                    raise ValueError("INSTITUTIONAL_PARENT_CYCLE")
                for row in ready:
                    locator_ref = "docref:institutional-" + str(row["id"]).split(":")[-1]
                    conn.execute(
                        "INSERT INTO document_reference (id,document_id,page_start,page_end,section,locator_text,original_excerpt) VALUES (?,?,?,?,?,?,?)",
                        (
                            locator_ref,
                            row["document_ref"],
                            row["page"],
                            row["page"],
                            row["official_code"],
                            row["locator"],
                            row["official_text"],
                        ),
                    )
                    conn.execute(
                        "INSERT INTO official_framework_element (id,framework_version_id,parent_element_id,element_type,official_code,official_label,official_text,position,document_reference_id) VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            row["id"],
                            row["version_ref"],
                            row["parent_ref"],
                            row["element_type"],
                            row["official_code"],
                            row["official_label"],
                            row["official_text"],
                            row["position"],
                            locator_ref,
                        ),
                    )
                    inserted.add(str(row["id"]))
                    pending.remove(row)
            for row in items(data["attachments"], 6000):
                kind = "EXPLICIT" if row["disposition"] == "VERIFIED_EXPLICIT" else "IMPLICIT"
                conn.execute(
                    "INSERT INTO institutional_attachment (id,notion_id,framework_element_id,attachment_type,importance_level,depth_level,origin_type,status) VALUES (?,?,?,?,?,?,'OFFICIAL','VALIDATED')",
                    (
                        row["id"],
                        row["notion_ref"],
                        row["element_ref"],
                        kind,
                        row["importance"],
                        row["pedagogical_depth"],
                    ),
                )
            conn.execute(
                "INSERT INTO evidence (id,evidence_type,content,status) VALUES (?,'INSTITUTIONAL_QUALIFICATION',?,'ACTIVE')",
                (proof_ref, serialized),
            )
            for row in items(data["elements"], 3000):
                locator_ref = "docref:institutional-" + str(row["id"]).split(":")[-1]
                conn.execute(
                    "INSERT INTO evidence_document_reference (evidence_id,document_reference_id) VALUES (?,?)",
                    (proof_ref, locator_ref),
                )
            conn.execute(
                "INSERT INTO audit_event (id,event_type,reason,payload_json) VALUES (?,'INSTITUTIONAL_QUALIFICATION_ADMITTED',?,?)",
                (
                    "audit:" + qualification.sha256[:24],
                    "OWNER_GROUPED_ADMISSION; NOT_PEDAGOGICAL_ACCEPTANCE",
                    json.dumps(
                        {
                            "owner_decision_sha256": data["owner_decision_sha256"],
                            "qualification_sha256": qualification.sha256,
                        }
                    ),
                ),
            )
            if {
                tuple(row) for row in conn.execute("PRAGMA foreign_key_check")
            } - baseline_violations:
                raise ValueError("INSTITUTIONAL_FOREIGN_KEY_CHECK")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
