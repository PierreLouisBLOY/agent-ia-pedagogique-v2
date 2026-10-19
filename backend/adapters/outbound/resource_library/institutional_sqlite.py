from __future__ import annotations

import json
import re
import sqlite3

from backend.modules.knowledge_reference.ports.outbound.institutional_catalog import (
    InstitutionalTableSchema,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint


class SQLiteInstitutionalCatalogAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        query_only = connection.execute("PRAGMA query_only").fetchone()
        if query_only is None or int(query_only[0]) != 1:
            raise ValueError("INSTITUTIONAL_READ_ONLY_REQUIRED")
        self.connection = connection

    def inspect_institutional_schema(self) -> tuple[InstitutionalTableSchema, ...]:
        names = [str(row[0]) for row in self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        result = []
        for name in names:
            if not any(word in name for word in (
                "program", "framework", "referential", "curriculum", "institution", "context", "level", "discipline", "notion", "document", "source", "formation", "resource", "pedagogical_content", "method", "object_registry", "evidence", "validation", "audit")):
                continue
            if re.fullmatch(r"[A-Za-z0-9_]+", name) is None:
                raise ValueError("INSTITUTIONAL_SCHEMA_IDENTIFIER")
            columns = tuple(str(row[1]) for row in self.connection.execute(f'PRAGMA table_info("{name}")'))
            count = int(self.connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0])
            definition = self.connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            result.append(InstitutionalTableSchema(name, columns, count, str(definition[0]) if definition else None))
        return tuple(result)

    def read_institutional_catalog(self) -> dict[str, object]:
        tables = ("official_framework", "official_framework_version", "official_framework_element",
                  "institutional_attachment", "pedagogical_context", "notion_context",
                  "discipline", "level", "formation", "notion", "source", "document", "document_reference",
                  "source_document", "formula_v1_official_source", "formula_v1_seed_framework")
        schemas = {row.table: row for row in self.inspect_institutional_schema()}
        result: dict[str, object] = {}
        for table in tables:
            if table not in schemas:
                result[table] = []
                continue
            if schemas[table].rows > 10000:
                raise ValueError("INSTITUTIONAL_CATALOG_ROW_BOUND")
            columns = schemas[table].columns
            selected = ",".join(f'"{name}"' for name in columns)
            result[table] = [dict(zip(columns, tuple(row), strict=True)) for row in
                             self.connection.execute(f'SELECT {selected} FROM "{table}"')]
        result["institutional_qualifications"] = []
        if "evidence" in schemas:
            proofs = self.connection.execute("SELECT content FROM evidence WHERE evidence_type='INSTITUTIONAL_QUALIFICATION' ORDER BY created_at,id LIMIT 17").fetchall()
            if len(proofs)>16 or any(len(str(r[0]))>12*1024*1024 for r in proofs):
                raise ValueError("INSTITUTIONAL_QUALIFICATION_BOUND")
            result["institutional_qualifications"] = [json.loads(str(r[0])) for r in proofs]
        return result

    def read_reference_contexts(self, object_ref: str) -> tuple[dict[str, object], ...]:
        # An exact identity only: no content->notion->programme inference or text search.
        schemas = {row.table: row for row in self.inspect_institutional_schema()}
        if "resource_context" not in schemas or "pedagogical_context" not in schemas:
            return ()
        rows = self.connection.execute(
            "SELECT rc.context_id, rc.role, rc.status, pc.framework_version_id, "
            "pc.framework_element_id, pc.difficulty_level FROM resource_context rc "
            "JOIN pedagogical_context pc ON pc.id=rc.context_id "
            "WHERE rc.resource_id=? ORDER BY rc.context_id LIMIT 257", (object_ref,)
        ).fetchall()
        if len(rows) > 256:
            raise ValueError("P0_REFERENCE_CONTEXT_BOUND")
        columns = ("context_ref", "role", "status", "program_version", "element_ref", "depth")
        return tuple(dict(zip(columns, tuple(row), strict=True)) for row in rows)

    def read_exact_passage_contexts(self, object_kind: str, object_ref: str,
                                    passage_ref: str, version_or_checksum: str,
                                    excerpt_sha256: str, context_ref: str,
                                    selection_sha256: str) -> tuple[dict[str, object], ...]:
        """Read only the versioned passage relation; never fall back to object scope."""
        schemas = {row.table: row for row in self.inspect_institutional_schema()}
        schema = schemas.get("resource_passage_context_v2")
        if schema is None:
            return ()
        required = {"relation_schema", "object_kind", "object_ref", "passage_ref", "version_or_checksum",
                    "excerpt_sha256", "context_ref", "selection_sha256", "program_ref",
                    "program_version_ref", "question_ref", "notion_ref", "depth",
                    "capacity_refs_canonical_json", "provenance_sha256", "owner_decision_sha256",
                    "role", "status", "available_authority"}
        if set(schema.columns) != required:
            raise ValueError("EXACT_PASSAGE_SCHEMA")
        cursor = self.connection.execute(
            "SELECT rc.*,pc.framework_version_id AS context_program_version,"
            "pc.framework_element_id AS element_ref,pc.difficulty_level AS context_depth "
            "FROM resource_passage_context_v2 rc "
            "JOIN pedagogical_context pc ON pc.id=rc.context_ref "
            "WHERE rc.object_kind=? AND rc.object_ref=? AND rc.passage_ref=? "
            "AND rc.version_or_checksum=? AND rc.excerpt_sha256=? "
            "AND rc.context_ref=? AND rc.selection_sha256=? LIMIT 2",
            (object_kind, object_ref, passage_ref, version_or_checksum,
             excerpt_sha256, context_ref, selection_sha256),
        )
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise ValueError("EXACT_PASSAGE_NOT_UNIQUE")
        columns = tuple(item[0] for item in cursor.description)
        result = []
        for row in rows:
            data = dict(zip(columns, tuple(row), strict=True))
            relation = {key: data[key] for key in required}
            result.append({**data, "program_version": data["program_version_ref"],
                           "row_sha256": fingerprint(relation)})
        return tuple(result)
