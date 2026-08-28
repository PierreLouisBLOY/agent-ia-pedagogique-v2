from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.adapters.outbound.document_content.sqlite import (
    DocumentContentAccessAdapter,
)
from backend.adapters.outbound.evidence.sqlite import (
    SQLiteEvidenceDocumentContentAdapter,
    SQLiteEvidenceSearchAdapter,
)
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.agent_runtime.agents.evidence import (
    DocumentContentRequest,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalIdentity,
    RetrievalQuery,
)
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 28, 8, 0, tzinfo=UTC))


class _Clock:
    def now(self) -> Instant:
        return NOW


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.executescript(
        """
        CREATE TABLE notion(
            id TEXT PRIMARY KEY,
            canonical_label TEXT NOT NULL,
            identity_status TEXT NOT NULL
        );
        CREATE TABLE object_registry(
            object_id TEXT PRIMARY KEY,
            object_type TEXT NOT NULL
        );
        CREATE TABLE search_chunk(
            id TEXT PRIMARY KEY,
            object_id TEXT NOT NULL,
            chunk_type TEXT NOT NULL,
            chunk_hash TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE level(
            id TEXT PRIMARY KEY,
            code TEXT,
            label TEXT NOT NULL
        );
        CREATE TABLE pedagogical_context(
            id TEXT PRIMARY KEY,
            level_id TEXT
        );
        CREATE TABLE notion_context(
            notion_id TEXT NOT NULL,
            context_id TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE search_chunk_fts USING fts5(text);
        INSERT INTO notion VALUES ('notion:absence', 'absence', 'CANONICAL');
        INSERT INTO notion VALUES ('notion:deprecated', 'deprecated', 'MERGED');
        INSERT INTO object_registry VALUES ('notion:absence', 'NOTION');
        INSERT INTO object_registry VALUES ('notion:deprecated', 'NOTION');
        INSERT INTO search_chunk VALUES (
            'search-chunk:absence', 'notion:absence', 'NOTION_LABEL',
            'sha256:absence-v1', 'Absence', 'CURRENT'
        );
        INSERT INTO search_chunk VALUES (
            'search-chunk:absence-stale', 'notion:absence', 'NOTION_ALIAS',
            'sha256:absence-stale', 'Archived absence', 'STALE'
        );
        INSERT INTO search_chunk VALUES (
            'search-chunk:deprecated', 'notion:deprecated', 'NOTION_LABEL',
            'sha256:deprecated', 'Deprecated', 'CURRENT'
        );
        INSERT INTO level VALUES ('level:terminale-stmg', 'terminale-stmg', 'Terminale STMG');
        INSERT INTO pedagogical_context VALUES (
            'context:terminale-stmg', 'level:terminale-stmg'
        );
        INSERT INTO notion_context VALUES (
            'notion:absence', 'context:terminale-stmg', 'RELEVANT', 'ACTIVE'
        );
        INSERT INTO search_chunk_fts(rowid, text)
        SELECT rowid, text FROM search_chunk;
        """
    )
    return connection


def _query(
    *,
    level: str = "terminale-stmg",
    topic: str | None = None,
    source_policy: dict[str, object] | None = None,
    filters: dict[str, object] | None = None,
) -> RetrievalQuery:
    scope = {"level": level}
    if topic is not None:
        scope["topic"] = topic
    return RetrievalQuery(
        "absence",
        scope,
        source_policy or {"kinds": ("canonical",)},
        filters or {"active": True},
        None,
        3,
    )


def test_structured_and_lexical_channels_share_one_canonical_identity() -> None:
    connection = _connection()
    adapter = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(connection))

    structured = adapter.search(query=_query(), channel=RetrievalChannel.STRUCTURED)
    lexical = adapter.search(query=_query(), channel=RetrievalChannel.LEXICAL)

    assert len(structured.candidates) == len(lexical.candidates) == 1
    structured_candidate = structured.candidates[0]
    lexical_candidate = lexical.candidates[0]
    assert RetrievalIdentity.from_candidate(
        structured_candidate
    ) == RetrievalIdentity.from_candidate(lexical_candidate)
    assert structured_candidate.signals.structured_rank == 1
    assert isinstance(lexical_candidate.signals.lexical_score, Decimal)
    assert structured_candidate.source_ref == "notion:absence"
    assert structured_candidate.locator == "search-chunk:absence"
    assert structured_candidate.version_or_checksum == "sha256:absence-v1"
    assert structured_candidate.authority["absolute"] is False


def test_sqlite_admission_requires_current_canonical_link_and_matching_scope() -> None:
    adapter = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(_connection()))
    lexical = adapter.search(query=_query(), channel=RetrievalChannel.LEXICAL)
    candidate = lexical.candidates[0]

    assert adapter.is_admissible(candidate=candidate, query=_query()) is True
    assert (
        adapter.is_admissible(
            candidate=candidate,
            query=_query(level="premiere-stmg"),
        )
        is False
    )
    assert adapter.is_admissible(
        candidate=candidate,
        query=_query(topic="Absence"),
    )
    assert not adapter.is_admissible(
        candidate=candidate,
        query=_query(topic="TVA"),
    )
    stale = replace(
        candidate,
        locator="search-chunk:absence-stale",
        version_or_checksum="sha256:absence-stale",
    )
    assert adapter.is_admissible(candidate=stale, query=_query()) is False
    noncanonical = replace(
        candidate,
        source_ref="notion:deprecated",
        canonical_object_ref="notion:deprecated",
        locator="search-chunk:deprecated",
        version_or_checksum="sha256:deprecated",
    )
    assert adapter.is_admissible(candidate=noncanonical, query=_query()) is False


def test_sqlite_admission_fails_closed_on_widened_query_constraints() -> None:
    adapter = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(_connection()))
    candidate = adapter.search(
        query=_query(), channel=RetrievalChannel.LEXICAL
    ).candidates[0]

    assert (
        adapter.is_admissible(
            candidate=candidate,
            query=_query(source_policy={"kinds": ("canonical", "external")}),
        )
        is False
    )
    assert (
        adapter.is_admissible(
            candidate=candidate,
            query=_query(filters={"active": False}),
        )
        is False
    )


def test_lexical_search_rejects_stale_and_noncanonical_rows_before_admission() -> None:
    search = BusinessSearchAdapter(_connection())
    assert search.search("Archived", limit=3) == ()
    assert search.search("Deprecated", limit=3) == ()


@pytest.mark.parametrize(
    ("channel", "reason"),
    (
        (RetrievalChannel.RELATIONAL, "RELATIONAL_NOT_CONFIGURED_C1"),
        (RetrievalChannel.SEMANTIC, "SEMANTIC_PROVIDER_NOT_CONFIGURED_C1"),
    ),
)
def test_optional_channels_close_with_explicit_reasons(
    channel: RetrievalChannel, reason: str
) -> None:
    adapter = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(_connection()))

    with pytest.raises(RetrievalChannelUnavailable) as raised:
        adapter.search(query=_query(), channel=channel)

    assert raised.value.channel is channel
    assert raised.value.reason_code == reason


def test_op13_content_mapping_is_logical_versioned_and_untrusted() -> None:
    connection = _connection()
    adapter = SQLiteEvidenceDocumentContentAdapter(
        DocumentContentAccessAdapter(connection), _Clock()
    )
    request = DocumentContentRequest(
        candidate_id="structured:search-chunk:absence",
        source_ref="notion:absence",
        locator="search-chunk:absence",
        source_policy={"kinds": ("canonical",)},
    )

    result = adapter.fetch(request=request)

    assert result.candidate_id == request.candidate_id
    assert result.source_ref == request.source_ref
    assert result.locator == request.locator
    assert result.content == "Absence"
    assert result.retrieved_at == NOW
    assert result.version_or_checksum == "sha256:absence-v1"
    assert result.metadata["trust"] == "UNTRUSTED_CONTENT"
    assert "path" not in result.provenance
    assert "url" not in result.provenance
