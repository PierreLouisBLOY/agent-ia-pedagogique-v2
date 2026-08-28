"""SQLite FTS5 implementation of Phase 7 OP-11."""

from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchHit:
    entity_ref: str
    entity_kind: str
    passage_ref: str
    version_or_checksum: str
    snippet: str
    rank: float
    registry_object_type: str


class BusinessSearchAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def search(self, text: str, *, limit: int = 5) -> tuple[SearchHit, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("search limit must be between 1 and 100")
        rows = self._connection.execute(
            """SELECT sc.object_id, sc.chunk_type, sc.id, sc.chunk_hash,
                      sc.text, bm25(search_chunk_fts), registry.object_type
               FROM search_chunk_fts AS f
               JOIN search_chunk AS sc ON sc.rowid = f.rowid
               JOIN object_registry AS registry ON registry.object_id = sc.object_id
               LEFT JOIN notion AS n
                 ON registry.object_type = 'NOTION' AND n.id = sc.object_id
               WHERE search_chunk_fts MATCH ?
                 AND sc.status = 'CURRENT'
                 AND (registry.object_type != 'NOTION'
                      OR n.identity_status = 'CANONICAL')
               ORDER BY bm25(search_chunk_fts), sc.id
               LIMIT ?""",
            (text, limit),
        ).fetchall()
        return tuple(
            SearchHit(
                str(row[0]), str(row[1]), str(row[2]), str(row[3]),
                str(row[4]), float(row[5]), str(row[6])
            )
            for row in rows
        )

    def structured_search(self, text: str, *, limit: int = 5) -> tuple[SearchHit, ...]:
        """Return exact canonical-label signals independently from FTS ranking."""
        if not 1 <= limit <= 100:
            raise ValueError("search limit must be between 1 and 100")
        rows = self._connection.execute(
            """SELECT sc.object_id, sc.chunk_type, sc.id, sc.chunk_hash, sc.text,
                      registry.object_type
               FROM notion AS n
               JOIN object_registry AS registry
                 ON registry.object_id = n.id AND registry.object_type = 'NOTION'
               JOIN search_chunk AS sc
                 ON sc.object_id = n.id AND sc.status = 'CURRENT'
               WHERE n.identity_status = 'CANONICAL'
                 AND lower(n.canonical_label) = lower(?)
               ORDER BY sc.id LIMIT ?""",
            (text, limit),
        ).fetchall()
        return tuple(
            SearchHit(
                str(row[0]), str(row[1]), str(row[2]), str(row[3]),
                str(row[4]), float(index), str(row[5])
            )
            for index, row in enumerate(rows, start=1)
        )

    def is_current_canonical_passage(
        self,
        *,
        entity_ref: str,
        passage_ref: str,
        version_or_checksum: str,
    ) -> bool:
        row = self._connection.execute(
            """SELECT 1
               FROM search_chunk AS sc
               JOIN object_registry AS registry ON registry.object_id = sc.object_id
               LEFT JOIN notion AS n
                 ON registry.object_type = 'NOTION' AND n.id = sc.object_id
               WHERE sc.id = ?
                 AND sc.object_id = ?
                 AND sc.chunk_hash = ?
                 AND sc.status = 'CURRENT'
                 AND (registry.object_type != 'NOTION'
                      OR n.identity_status = 'CANONICAL')
               LIMIT 1""",
            (passage_ref, entity_ref, version_or_checksum),
        ).fetchone()
        return row is not None

    def canonical_object_matches_level(self, entity_ref: str, level: str) -> bool:
        rows = self._connection.execute(
            """SELECT l.id, l.code, l.label
               FROM notion_context AS nc
               JOIN pedagogical_context AS pc ON pc.id = nc.context_id
               JOIN level AS l ON l.id = pc.level_id
               WHERE nc.notion_id = ?
                 AND nc.status = 'ACTIVE'
                 AND pc.level_id IS NOT NULL
               ORDER BY l.id""",
            (entity_ref,),
        ).fetchall()
        if not rows:
            return True
        expected = _normalized_scope_value(level)
        return any(
            expected == _normalized_scope_value(str(value))
            for row in rows
            for value in row
            if value is not None
        )

    def canonical_object_matches_topic(self, entity_ref: str, topic: str) -> bool:
        row = self._connection.execute(
            """SELECT n.canonical_label
               FROM notion AS n
               JOIN object_registry AS registry
                 ON registry.object_id = n.id AND registry.object_type = 'NOTION'
               WHERE n.id = ?
                 AND n.identity_status = 'CANONICAL'
               LIMIT 1""",
            (entity_ref,),
        ).fetchone()
        return row is not None and _normalized_scope_value(str(row[0])) == (
            _normalized_scope_value(topic)
        )

    def close(self) -> None:
        self._connection.close()


def _normalized_scope_value(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(character for character in decomposed if character.isalnum()).casefold()
