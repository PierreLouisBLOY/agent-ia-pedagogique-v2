"""Read-only OP-11/F2A/OP-13 bridge to the M03 local search port."""

from __future__ import annotations

import sqlite3
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import SQLiteEvidenceSearchAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.agent_runtime.agents.evidence import RetrievalChannel, RetrievalQuery
from backend.modules.resource_library.contracts.dto.search_source_status import SearchSourceStatus
from backend.modules.resource_library.domain.value_objects.search_text import SearchText
from backend.modules.resource_library.ports.outbound.local_search import (
    AdmittedLocalPassage,
    LocalSearchWindow,
)


def literal_fts(text: SearchText) -> str:
    return " AND ".join('"' + token.replace('"', '""') + '"' for token in text.tokens)


def minimized_excerpt(text: str) -> tuple[str, bool]:
    clean = "".join(
        "" if unicodedata.category(c) in {"Cf", "Cs"} else
        " " if unicodedata.category(c) == "Cc" or unicodedata.category(c).startswith("Z") else c
        for c in unicodedata.normalize("NFC", text)
    )
    clean = " ".join(part for part in clean.split(" ") if part)
    return clean[:320], len(clean) > 320


class SQLiteLocalSearchAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        # No discovery query, provisioning, configuration lookup or filesystem access.
        self._connection = connection
        self._evidence = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(connection))
        self._content = DocumentContentAccessAdapter(connection)
        self._snapshot = False

    @contextmanager
    def read_snapshot(self) -> Iterator[None]:
        if self._snapshot or self._connection.in_transaction:
            raise ValueError("SEARCH_SNAPSHOT_ALREADY_ACTIVE")
        if self._connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise ValueError("QUERY_ONLY_REQUIRED")
        self._connection.execute("BEGIN")
        self._snapshot = True
        try:
            yield
        finally:
            self._snapshot = False
            self._connection.rollback()

    def admitted_window(
        self, *, text: SearchText, result_limit: int, candidate_limit: int = 100,
    ) -> LocalSearchWindow:
        if not self._snapshot or not self._connection.in_transaction:
            raise ValueError("SEARCH_SNAPSHOT_REQUIRED")
        if (type(text) is not SearchText or type(result_limit) is not int
                or not 1 <= result_limit <= 20 or type(candidate_limit) is not int
                or candidate_limit != 100):
            raise ValueError("INVALID_SEARCH_WINDOW")
        query = RetrievalQuery(
            search_goal=literal_fts(text), scope={}, source_policy={"kinds": ("canonical",)},
            filters={"active": True}, required_authority={"basis": "canonical-registry"},
            max_items=candidate_limit,
        )
        result = self._evidence.search(query=query, channel=RetrievalChannel.LEXICAL)
        if result.channel is not RetrievalChannel.LEXICAL or result.limitations:
            raise ValueError("SEARCH_CHANNEL_FAILED")
        candidates = result.candidates
        if len(candidates) > candidate_limit or len({c.locator for c in candidates}) != len(candidates):
            raise ValueError("INVALID_SEARCH_CANDIDATES")
        admitted = []
        for candidate in candidates:
            if candidate.channel is not RetrievalChannel.LEXICAL:
                raise ValueError("INVALID_SEARCH_CHANNEL")
            if self._evidence.is_admissible(candidate=candidate, query=query):
                admitted.append(candidate)
        passages = []
        for candidate in admitted[:result_limit]:
            fragment = self._content.read_passage(candidate.locator)
            if (
                fragment is None or fragment.source_ref != candidate.source_ref
                or fragment.passage_ref != candidate.locator
                or fragment.version_or_checksum != candidate.version_or_checksum
            ):
                raise ValueError("SEARCH_PROVENANCE_MISMATCH")
            kind = candidate.provenance.get("object_kind")
            if not isinstance(kind, str) or not isinstance(candidate.source_ref, str):
                raise ValueError("INVALID_SEARCH_PROVENANCE")
            checksum = candidate.version_or_checksum
            if not isinstance(checksum, str):
                raise ValueError("INVALID_SEARCH_PROVENANCE")
            excerpt, truncated = minimized_excerpt(fragment.text)
            source_status = candidate.metadata.get("source_status")
            if source_status is not None and (fragment.source_status is None or fragment.source_status.as_dict() != source_status):
                raise ValueError("SEARCH_SOURCE_STATUS_CHANGED")
            passages.append(AdmittedLocalPassage(
                candidate.source_ref, kind, candidate.locator, checksum, excerpt, truncated,
                SearchSourceStatus.from_mapping(source_status) if source_status is not None else None,
            ))
        return LocalSearchWindow(
            tuple(passages), len(candidates) == candidate_limit, len(admitted) > result_limit,
        )
