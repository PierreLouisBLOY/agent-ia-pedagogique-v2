from __future__ import annotations

import sqlite3

from backend.modules.resource_library.ports.outbound.canonical_notion_catalog import (
    CanonicalNotionIdentityRecord,
)


class SQLiteCanonicalNotionCatalogAdapter:
    """Query-only catalog projection; all schema access stays in this adapter."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        query_only = connection.execute("PRAGMA query_only").fetchone()
        if query_only is None or int(query_only[0]) != 1:
            raise ValueError("R6_READ_ONLY_REQUIRED")
        self._connection = connection

    def list_canonical_notion_identities(self) -> tuple[CanonicalNotionIdentityRecord, ...]:
        rows = self._connection.execute(
            """SELECT n.id, n.canonical_label, n.identity_status,
                      COALESCE((
                        SELECT group_concat(DISTINCT COALESCE(l.code, l.label))
                        FROM notion_context AS nc
                        JOIN pedagogical_context AS pc ON pc.id = nc.context_id
                        JOIN level AS l ON l.id = pc.level_id
                        WHERE nc.notion_id = n.id AND nc.status = 'ACTIVE'
                      ), ''),
                      COALESCE((
                        SELECT group_concat(DISTINCT mn.method_id)
                        FROM method_notion AS mn
                        WHERE mn.notion_id = n.id
                      ), '')
               FROM notion AS n
               JOIN object_registry AS registry
                 ON registry.object_id = n.id AND registry.object_type = 'NOTION'
               WHERE n.identity_status = 'CANONICAL'
               ORDER BY n.id"""
        ).fetchall()
        return tuple(
            CanonicalNotionIdentityRecord(
                str(row[0]),
                str(row[1]),
                str(row[2]),
                tuple(sorted(value for value in str(row[3]).split(",") if value)),
                tuple(sorted(value for value in str(row[4]).split(",") if value)),
            )
            for row in rows
        )

    def close(self) -> None:
        self._connection.close()
