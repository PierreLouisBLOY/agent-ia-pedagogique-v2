"""Logical-only SQLite implementation of Phase 7 OP-13."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContentFragment:
    source_ref: str
    document_ref: str | None
    passage_ref: str
    text: str
    evidence_ref: str


class DocumentContentAccessAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def read_document(self, document_ref: str) -> tuple[ContentFragment, ...]:
        rows = self._connection.execute(
            """SELECT dr.id, coalesce(dr.original_excerpt, dr.locator_text, d.title)
               FROM document AS d
               JOIN document_reference AS dr ON dr.document_id = d.id
               WHERE d.id = ? ORDER BY dr.id""",
            (document_ref,),
        ).fetchall()
        return tuple(
            ContentFragment(
                document_ref, document_ref, str(row[0]), str(row[1]), f"evidence:{row[0]}"
            )
            for row in rows
        )

    def read_passage(self, passage_ref: str) -> ContentFragment | None:
        row = self._connection.execute(
            "SELECT object_id, text FROM search_chunk WHERE id = ? AND status = ?",
            (passage_ref, "CURRENT"),
        ).fetchone()
        if row is None:
            return None
        return ContentFragment(
            str(row[0]), None, passage_ref, str(row[1]), f"evidence:{passage_ref}"
        )

    def close(self) -> None:
        self._connection.close()
