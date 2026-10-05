from __future__ import annotations

import re
import sqlite3

from backend.modules.knowledge_reference.ports.outbound.institutional_catalog import (
    InstitutionalTableSchema,
)


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
                "program", "framework", "referential", "curriculum", "institution", "context", "level", "discipline", "notion", "document", "source", "formation")):
                continue
            if re.fullmatch(r"[A-Za-z0-9_]+", name) is None:
                raise ValueError("INSTITUTIONAL_SCHEMA_IDENTIFIER")
            columns = tuple(str(row[1]) for row in self.connection.execute(f'PRAGMA table_info("{name}")'))
            count = int(self.connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0])
            result.append(InstitutionalTableSchema(name, columns, count))
        return tuple(result)

    def read_institutional_catalog(self) -> dict[str, object]:
        tables = ("official_framework", "official_framework_version", "official_framework_element",
                  "institutional_attachment", "pedagogical_context", "notion_context",
                  "discipline", "level", "formation", "notion", "source", "document", "document_reference")
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
        return result
