from __future__ import annotations

import sqlite3
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
        CREATE VIRTUAL TABLE search_chunk_fts USING fts5(text);
        INSERT INTO notion VALUES ('notion:absence', 'absence', 'CANONICAL');
        INSERT INTO object_registry VALUES ('notion:absence', 'NOTION');
        INSERT INTO search_chunk VALUES (
            'search-chunk:absence', 'notion:absence', 'NOTION_LABEL',
            'sha256:absence-v1', 'Absence', 'CURRENT'
        );
        INSERT INTO search_chunk_fts(rowid, text)
        SELECT rowid, text FROM search_chunk;
        """
    )
    return connection


def _query() -> RetrievalQuery:
    return RetrievalQuery(
        "absence", {"level": "terminale-stmg"}, {"kinds": ("canonical",)},
        {"active": True}, None, 3
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
