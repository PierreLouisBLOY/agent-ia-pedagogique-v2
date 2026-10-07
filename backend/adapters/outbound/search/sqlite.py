"""SQLite FTS5 implementation of Phase 7 OP-11."""

from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass

from backend.adapters.outbound.search.source_status import passage_source_status, source_status
from backend.modules.resource_library.contracts.dto.search_source_status import SearchSourceStatus


@dataclass(frozen=True, slots=True)
class SearchHit:
    entity_ref: str
    entity_kind: str
    passage_ref: str
    version_or_checksum: str
    snippet: str
    rank: float
    registry_object_type: str
    source_status: SearchSourceStatus | None = None


@dataclass(frozen=True, slots=True)
class CanonicalSearchPassage:
    canonical_object_ref: str
    passage_ref: str
    version_or_checksum: str
    object_type: str
    chunk_type: str
    text: str
    semantic_aliases: tuple[str, ...] = ()
    semantic_context: str | None = None
    semantic_rollup_refs: tuple[str, ...] = ()


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
                str(row[4]), float(row[5]), str(row[6]), source_status(self._connection, str(row[0]), str(row[6]))
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
                str(row[4]), float(index), str(row[5]), source_status(self._connection, str(row[0]), str(row[5]))
            )
            for index, row in enumerate(rows, start=1)
        )

    def passage_source_status(self, passage_ref: str) -> SearchSourceStatus | None:
        return passage_source_status(self._connection, passage_ref)

    def canonical_search_passages(self) -> tuple[CanonicalSearchPassage, ...]:
        """Enumerate the deterministic CURRENT canonical search universe."""
        notion_aliases = self._notion_semantic_aliases()
        notion_contexts = self._notion_semantic_contexts()
        rollups = self._semantic_rollups()
        rows = self._connection.execute(
            """SELECT sc.object_id, sc.id, sc.chunk_hash,
                      registry.object_type, sc.chunk_type, sc.text
               FROM search_chunk AS sc
               JOIN object_registry AS registry ON registry.object_id = sc.object_id
               LEFT JOIN notion AS n
                 ON registry.object_type = 'NOTION' AND n.id = sc.object_id
               WHERE sc.status = 'CURRENT'
                 AND (registry.object_type != 'NOTION'
                      OR n.identity_status = 'CANONICAL')
               ORDER BY sc.id"""
        ).fetchall()
        return tuple(
            CanonicalSearchPassage(
                canonical_object_ref=str(row[0]),
                passage_ref=str(row[1]),
                version_or_checksum=str(row[2]),
                object_type=str(row[3]),
                chunk_type=str(row[4]),
                text=str(row[5]),
                semantic_aliases=(
                    notion_aliases.get(str(row[0]), ())
                    if str(row[4]) == "NOTION_LABEL"
                    else ()
                ),
                semantic_context=(
                    notion_contexts.get(str(row[0]))
                    if str(row[4]) == "NOTION_LABEL"
                    else None
                ),
                semantic_rollup_refs=rollups.get(str(row[0]), ()),
            )
            for row in rows
        )

    def semantic_query_text(self, text: str) -> str:
        """Expand an exact active alias with its canonical notion label."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("semantic query text must be a non-empty string")
        normalized = _normalized_scope_value(text)
        rows = self._connection.execute(
            """SELECT DISTINCT n.id, n.canonical_label
               FROM notion_alias AS alias
               JOIN notion AS n
                 ON n.id = alias.notion_id
                AND n.identity_status = 'CANONICAL'
               WHERE alias.status = 'ACTIVE'
                 AND alias.alias_normalized = ?
               ORDER BY n.id""",
            (normalized,),
        ).fetchall()
        if len(rows) != 1:
            return text
        return (
            f"original_query: {text}\n"
            f"resolved_canonical_alias: {rows[0][1]}"
        )

    def _notion_semantic_aliases(self) -> dict[str, tuple[str, ...]]:
        rows = self._connection.execute(
            """SELECT alias.notion_id, alias.alias_text
               FROM notion_alias AS alias
               JOIN notion AS n
                 ON n.id = alias.notion_id
                AND n.identity_status = 'CANONICAL'
               WHERE alias.status = 'ACTIVE'
               ORDER BY alias.notion_id, alias.alias_normalized, alias.id"""
        ).fetchall()
        grouped: dict[str, list[str]] = {}
        for notion_id, alias_text in rows:
            values = grouped.setdefault(str(notion_id), [])
            value = str(alias_text)
            if value not in values:
                values.append(value)
        return {
            notion_id: tuple(values)
            for notion_id, values in grouped.items()
        }

    def _notion_semantic_contexts(self) -> dict[str, str]:
        """Project linked CURRENT canonical content without changing identity."""

        rows = self._connection.execute(
            """SELECT DISTINCT cn.notion_id, pc.id, pc.content_type, sc.text
               FROM content_notion AS cn
               JOIN notion AS n
                 ON n.id = cn.notion_id AND n.identity_status = 'CANONICAL'
               JOIN pedagogical_content AS pc ON pc.id = cn.content_id
               JOIN object_registry AS registry
                 ON registry.object_id = pc.id
                AND registry.object_type = 'PEDAGOGICAL_CONTENT'
               JOIN search_chunk AS sc
                 ON sc.object_id = pc.id AND sc.status = 'CURRENT'
               ORDER BY cn.notion_id,
                 CASE pc.content_type
                   WHEN 'DEFINITION_STUDENT' THEN 0
                   WHEN 'DEFINITION_TEACHER' THEN 1
                   WHEN 'LEGACY_DISTINCTIONS_TEXT' THEN 2
                   WHEN 'WHY_IMPORTANT' THEN 3
                   WHEN 'EXAMPLE' THEN 4
                   WHEN 'COUNTEREXAMPLE' THEN 5
                   WHEN 'FREQUENT_CONFUSION' THEN 6
                   WHEN 'VALIDITY_CONDITIONS' THEN 7
                   ELSE 8
                 END,
                 pc.content_type, pc.id, sc.id"""
        ).fetchall()
        grouped: dict[str, list[str]] = {}
        for notion_id, _content_id, content_type, text in rows:
            grouped.setdefault(str(notion_id), []).append(
                f"{content_type}: {text}"
            )
        return {
            notion_id: "\n".join(values)
            for notion_id, values in grouped.items()
        }

    def _semantic_rollups(self) -> dict[str, tuple[str, ...]]:
        rows = self._connection.execute(
            """SELECT link.object_id, link.notion_id
               FROM (
                 SELECT content_id AS object_id, notion_id FROM content_notion
                 UNION ALL
                 SELECT method_id AS object_id, notion_id FROM method_notion
                 UNION ALL
                 SELECT resource_id AS object_id, notion_id FROM resource_notion
               ) AS link
               JOIN notion AS n
                 ON n.id = link.notion_id AND n.identity_status = 'CANONICAL'
               JOIN object_registry AS registry
                 ON registry.object_id = link.object_id
               JOIN search_chunk AS sc
                 ON sc.object_id = link.object_id AND sc.status = 'CURRENT'
               GROUP BY link.object_id, link.notion_id
               ORDER BY link.object_id, link.notion_id"""
        ).fetchall()
        grouped: dict[str, list[str]] = {}
        for object_id, notion_id in rows:
            grouped.setdefault(str(object_id), []).append(str(notion_id))
        return {
            object_id: tuple(notion_ids)
            for object_id, notion_ids in grouped.items()
        }

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
