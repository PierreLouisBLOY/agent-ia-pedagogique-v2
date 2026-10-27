"""Closed writer for a new, synthetic passage/context candidate database."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint

_COLUMNS = (
    "relation_schema", "object_kind", "object_ref", "passage_ref",
    "version_or_checksum", "excerpt_sha256", "context_ref", "program_ref",
    "program_version_ref", "question_ref", "notion_ref", "depth",
    "capacity_refs_canonical_json", "selection_sha256", "provenance_sha256",
    "owner_decision_sha256", "role", "status", "available_authority",
)


def _row(data: Mapping[str, object], selection_sha256: str,
         owner_decision_sha256: str) -> dict[str, object]:
    capacities = data["capacity_refs"]
    assert isinstance(capacities, list)
    return {
        "relation_schema": "1.0", "object_kind": data["object_kind"],
        "object_ref": data["object_ref"], "passage_ref": data["passage_ref"],
        "version_or_checksum": data["version_or_checksum"],
        "excerpt_sha256": data["excerpt_sha256"], "context_ref": data["context_ref"],
        "program_ref": data["program_ref"], "program_version_ref": data["program_version_ref"],
        "question_ref": data["question_ref"], "notion_ref": data["notion_ref"],
        "depth": data["depth"],
        "capacity_refs_canonical_json": json.dumps(sorted(capacities), ensure_ascii=False,
                                                    separators=(",", ":")),
        "selection_sha256": selection_sha256,
        "provenance_sha256": data["provenance_sha256"],
        "owner_decision_sha256": owner_decision_sha256,
        "role": data["role"], "status": data["relation_status"],
        "available_authority": data["available_authority"],
    }


class SQLiteExactPassageContextWriter:
    """Not composed into live runtime; caller owns a new synthetic connection."""

    def __init__(self, connection: sqlite3.Connection, *, synthetic_root: Path) -> None:
        flag = connection.execute("PRAGMA query_only").fetchone()
        if flag is None or int(flag[0]) != 0:
            raise ValueError("EXACT_PASSAGE_WRITER_REQUIRED")
        databases = connection.execute("PRAGMA database_list").fetchall()
        main = [row for row in databases if row[1] == "main"]
        if len(main) != 1 or not main[0][2]:
            raise ValueError("EXACT_PASSAGE_SYNTHETIC_TARGET_REQUIRED")
        root = synthetic_root.resolve(strict=True)
        raw_target = Path(str(main[0][2]))
        target = raw_target.resolve(strict=True)
        if not target.is_relative_to(root) or target == root or raw_target.is_symlink():
            raise ValueError("EXACT_PASSAGE_SYNTHETIC_TARGET_REQUIRED")
        try:
            marker = connection.execute(
                "SELECT scope FROM b32_synthetic_fixture_marker LIMIT 2"
            ).fetchall()
        except sqlite3.Error as error:
            raise ValueError("EXACT_PASSAGE_SYNTHETIC_TARGET_REQUIRED") from error
        if len(marker) != 1 or marker[0][0] != "LOCAL_B_ONLY":
            raise ValueError("EXACT_PASSAGE_SYNTHETIC_TARGET_REQUIRED")
        self.connection = connection
        self.target = target
        target_stat = target.stat()
        self.target_identity = (target_stat.st_dev, target_stat.st_ino)

    def _validate_destination(self, request: Mapping[str, object]) -> None:
        destination = request.get("fresh_destination")
        if not isinstance(destination, str):
            raise ValueError("EXACT_PASSAGE_DESTINATION_MISMATCH")
        approved = Path(destination)
        if not approved.is_absolute() or approved.is_symlink():
            raise ValueError("EXACT_PASSAGE_DESTINATION_MISMATCH")
        try:
            resolved = approved.resolve(strict=True)
            destination_stat = approved.stat()
        except OSError:
            raise ValueError("EXACT_PASSAGE_DESTINATION_MISMATCH") from None
        if (resolved != self.target or
                (destination_stat.st_dev, destination_stat.st_ino) != self.target_identity):
            raise ValueError("EXACT_PASSAGE_DESTINATION_MISMATCH")

    def validate_scope(self, request: Mapping[str, object]) -> None:
        self._validate_destination(request)
        conn = self.connection
        context = conn.execute(
            "SELECT framework_version_id,framework_element_id,difficulty_level "
            "FROM pedagogical_context WHERE id=? LIMIT 2", (request["context_ref"],)
        ).fetchall()
        if len(context) != 1 or context[0][0] != request["program_version_ref"] or context[0][2] != request["depth"]:
            raise ValueError("EXACT_PASSAGE_CONTEXT_SCOPE")
        version = conn.execute(
            "SELECT framework_id FROM official_framework_version WHERE id=? LIMIT 2",
            (request["program_version_ref"],)
        ).fetchall()
        if len(version) != 1 or version[0][0] != request["program_ref"]:
            raise ValueError("EXACT_PASSAGE_PROGRAM_SCOPE")
        question = conn.execute(
            "SELECT framework_version_id,parent_element_id,element_type FROM official_framework_element "
            "WHERE id=? LIMIT 2", (request["question_ref"],)
        ).fetchall()
        if (len(question) != 1 or question[0][0] != request["program_version_ref"]
                or question[0][2] != "QUESTION"):
            raise ValueError("EXACT_PASSAGE_QUESTION_SCOPE")
        element = conn.execute(
            "SELECT framework_version_id,parent_element_id FROM official_framework_element "
            "WHERE id=? LIMIT 2", (context[0][1],)
        ).fetchall()
        if (len(element) != 1 or element[0][0] != request["program_version_ref"]
                or (context[0][1] != request["question_ref"]
                    and element[0][1] != request["question_ref"])):
            raise ValueError("EXACT_PASSAGE_CONTEXT_SCOPE")
        notion = conn.execute(
            "SELECT identity_status FROM notion WHERE id=? LIMIT 2", (request["notion_ref"],)
        ).fetchall()
        if len(notion) != 1 or notion[0][0] != "CANONICAL":
            raise ValueError("EXACT_PASSAGE_NOTION_SCOPE")
        capacities = request["capacity_refs"]
        assert isinstance(capacities, list)
        for ref in capacities:
            rows = conn.execute(
                "SELECT framework_version_id,parent_element_id,element_type FROM official_framework_element "
                "WHERE id=? LIMIT 2", (ref,)
            ).fetchall()
            if (len(rows) != 1 or rows[0][0] != request["program_version_ref"]
                    or rows[0][2] != "CAPACITY"
                    or rows[0][1] not in {request["question_ref"], question[0][1]}):
                raise ValueError("EXACT_PASSAGE_CAPACITY_SCOPE")

    def add_one(self, request: Mapping[str, object], *, selection_sha256: str,
                owner_decision_sha256: str) -> str:
        conn = self.connection
        row = _row(request, selection_sha256, owner_decision_sha256)
        if conn.in_transaction:
            raise ValueError("EXACT_PASSAGE_TRANSACTION_REQUIRED")
        self._validate_destination(request)
        conn.execute("BEGIN IMMEDIATE")
        try:
            self.validate_scope(request)
            existing = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='resource_passage_context_v2'"
            ).fetchone()
            if existing is not None:
                raise ValueError("EXACT_PASSAGE_FRESH_COPY_REQUIRED")
            conn.execute("""
                CREATE TABLE resource_passage_context_v2 (
                    relation_schema TEXT NOT NULL CHECK(relation_schema='1.0'),
                    object_kind TEXT NOT NULL, object_ref TEXT NOT NULL,
                    passage_ref TEXT NOT NULL, version_or_checksum TEXT NOT NULL,
                    excerpt_sha256 TEXT NOT NULL, context_ref TEXT NOT NULL,
                    program_ref TEXT NOT NULL, program_version_ref TEXT NOT NULL,
                    question_ref TEXT NOT NULL, notion_ref TEXT NOT NULL,
                    depth TEXT NOT NULL, capacity_refs_canonical_json TEXT NOT NULL,
                    selection_sha256 TEXT NOT NULL, provenance_sha256 TEXT NOT NULL,
                    owner_decision_sha256 TEXT NOT NULL, role TEXT NOT NULL CHECK(role='MAIN'),
                    status TEXT NOT NULL CHECK(status='ADMITTED'),
                    available_authority TEXT NOT NULL CHECK(available_authority='UNKNOWN'),
                    UNIQUE(object_kind,object_ref,passage_ref,version_or_checksum,context_ref,selection_sha256)
                )
            """)
            placeholders = ",".join("?" for _ in _COLUMNS)
            columns = ",".join(_COLUMNS)
            conn.execute(f"INSERT INTO resource_passage_context_v2 ({columns}) VALUES ({placeholders})",
                         tuple(row[key] for key in _COLUMNS))
            observed = self.read_exact(request, selection_sha256=selection_sha256)
            if observed is None or observed.get("row_sha256") != fingerprint(row):
                raise ValueError("EXACT_PASSAGE_READBACK_FAILED")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return fingerprint(row)

    def read_exact(self, request: Mapping[str, object], *, selection_sha256: str) -> dict[str, object] | None:
        conn = self.connection
        rows = conn.execute(
            "SELECT " + ",".join(_COLUMNS) + " FROM resource_passage_context_v2 "
            "WHERE object_kind=? AND object_ref=? AND passage_ref=? AND version_or_checksum=? "
            "AND excerpt_sha256=? AND context_ref=? AND selection_sha256=? LIMIT 2",
            (request["object_kind"], request["object_ref"], request["passage_ref"],
             request["version_or_checksum"], request["excerpt_sha256"],
             request["context_ref"], selection_sha256),
        ).fetchall()
        if len(rows) > 1:
            raise ValueError("EXACT_PASSAGE_NOT_UNIQUE")
        if not rows:
            return None
        row = dict(zip(_COLUMNS, tuple(rows[0]), strict=True))
        return {**row, "row_sha256": fingerprint(row)}
