"""Selected OP-13 passages and private metadata; never follow file paths or URLs."""
from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Mapping

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import SQLiteEvidenceSearchAdapter, _candidate
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter, SearchHit
from backend.agent_runtime.agents.evidence import (
    RetrievalChannel,
    RetrievalQuery,
    RetrievalSearchResult,
)


class LocalReferenceRejected(ValueError):
    """Closed public error: never include source text, identifiers or SQL details."""

    def __init__(self, code: str = "REFERENCE_PREPARATION_REJECTED") -> None:
        super().__init__(code)


class LocalReferenceContentAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def materialize(self, item: Mapping[str, object], *, evidence_id: str) -> dict[str, object]:
        if (not self.connection.in_transaction
                or self.connection.execute("PRAGMA query_only").fetchone()[0] != 1):
            raise LocalReferenceRejected()
        source, passage, version = (item.get(key) for key in (
            "object_ref", "passage_ref", "version_or_checksum"))
        if not all(isinstance(value, str) and value for value in (source, passage, version)):
            raise LocalReferenceRejected()
        assert isinstance(source, str) and isinstance(passage, str) and isinstance(version, str)
        if not BusinessSearchAdapter(self.connection).is_current_canonical_passage(
                entity_ref=source, passage_ref=passage, version_or_checksum=version):
            raise LocalReferenceRejected("REFERENCE_STALE_OR_MISSING")
        fragment = DocumentContentAccessAdapter(self.connection).read_passage(passage)
        if (fragment is None or fragment.source_ref != source
                or fragment.version_or_checksum != version or not fragment.text.strip()):
            raise LocalReferenceRejected("REFERENCE_STALE_OR_MISSING")
        if len(fragment.text) > 1000:
            raise LocalReferenceRejected("REFERENCE_TOO_LARGE")
        registry = self.connection.execute(
            "SELECT object_type FROM object_registry WHERE object_id = ?", (source,),
        ).fetchone()
        if registry is None or registry[0] != item.get("object_kind"):
            raise LocalReferenceRejected()
        kind = str(registry[0])
        title = None
        if kind == "RESOURCE":
            row = self.connection.execute(
                "SELECT canonical_title FROM resource WHERE id = ?", (source,),
            ).fetchone()
            title = None if row is None else row[0]
        elif kind == "NOTION":
            row = self.connection.execute(
                "SELECT canonical_label FROM notion WHERE id = ?", (source,),
            ).fetchone()
            title = None if row is None else row[0]
        documents = []
        if kind == "OFFICIAL_OCCURRENCE":
            rows = self.connection.execute(
                """SELECT d.id, d.document_type, d.title, d.publication_date,
                          dr.id, dr.page_start, dr.page_end, dr.section, dr.paragraph,
                          dr.locator_text, length(coalesce(dr.original_excerpt, '')) > 0
                   FROM official_occurrence AS o
                   JOIN document_reference AS dr ON dr.id = o.document_reference_id
                   JOIN document AS d ON d.id = dr.document_id WHERE o.id = ?""", (source,),
            ).fetchall()
            keys = ("document_ref", "document_type", "title", "publication_date",
                    "document_reference", "page_start", "page_end", "section", "paragraph",
                    "locator_text", "stored_original_excerpt_present")
            documents = [dict(zip(keys, tuple(row), strict=True)) for row in rows]
        metadata: dict[str, object] = {
            "evidence_id": evidence_id, "object_kind": kind, "source_ref": source,
            "locator": passage, "version_or_checksum": version, "title": title,
            "excerpt": fragment.text,
            "excerpt_sha256": hashlib.sha256(fragment.text.encode("utf-8")).hexdigest(),
            "documents": documents, "source_classification": kind,
            "document_link_status": "LINKED_NOT_FULL_DOCUMENT" if documents else "NOT_ESTABLISHED",
            "external_file_opened": False, "official_authority_attested": False,
        }
        return metadata


class SelectedLocalEvidenceSearch(SQLiteEvidenceSearchAdapter):
    """Exact M03 selection, re-admitted in the snapshot before AG02 can materialize."""
    def __init__(self, connection: sqlite3.Connection, selections: tuple[Mapping[str, object], ...]) -> None:
        super().__init__(BusinessSearchAdapter(connection))
        if not 1 <= len(selections) <= 3:
            raise LocalReferenceRejected()
        self.connection, self.selections = connection, selections

    def search(self, *, query: RetrievalQuery, channel: RetrievalChannel) -> RetrievalSearchResult:
        if channel not in (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL):
            raise LocalReferenceRejected()
        if not self.connection.in_transaction or query.max_items is None or len(self.selections) > query.max_items:
            raise LocalReferenceRejected()
        candidates = []
        for rank, selected in enumerate(self.selections, 1):
            row = self.connection.execute(
                """SELECT sc.object_id, sc.chunk_type, sc.id, sc.chunk_hash, sc.text, r.object_type
                   FROM search_chunk AS sc JOIN object_registry AS r ON r.object_id = sc.object_id
                   WHERE sc.id = ? AND sc.status = 'CURRENT'""", (selected["passage_ref"],),
            ).fetchone()
            if row is None or row[0] != selected["object_ref"] or row[3] != selected["version_or_checksum"]:
                raise LocalReferenceRejected("REFERENCE_STALE_OR_MISSING")
            candidate = _candidate(SearchHit(str(row[0]), str(row[1]), str(row[2]), str(row[3]),
                                            str(row[4]), float(rank), str(row[5])), channel, rank)
            if not self.is_admissible(candidate=candidate, query=query):
                raise LocalReferenceRejected("REFERENCE_NOT_ADMISSIBLE")
            candidates.append(candidate)
        return RetrievalSearchResult(channel, tuple(candidates))
