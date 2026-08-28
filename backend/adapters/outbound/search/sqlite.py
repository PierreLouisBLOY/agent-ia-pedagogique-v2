"""SQLite FTS5 implementation of Phase 7 OP-11."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchHit:
    entity_ref: str
    entity_kind: str
    passage_ref: str
    snippet: str
    rank: float


class BusinessSearchAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def search(self, text: str, *, limit: int = 5) -> tuple[SearchHit, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("search limit must be between 1 and 100")
        rows = self._connection.execute(
            """SELECT sc.object_id, sc.chunk_type, sc.id, sc.text, bm25(search_chunk_fts)
               FROM search_chunk_fts AS f
               JOIN search_chunk AS sc ON sc.rowid = f.rowid
               WHERE search_chunk_fts MATCH ?
               ORDER BY bm25(search_chunk_fts), sc.id
               LIMIT ?""",
            (text, limit),
        ).fetchall()
        return tuple(
            SearchHit(str(row[0]), str(row[1]), str(row[2]), str(row[3]), float(row[4]))
            for row in rows
        )

    def close(self) -> None:
        self._connection.close()
