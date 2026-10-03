from __future__ import annotations

import sqlite3

import pytest

from backend.adapters.outbound.resource_library.canonical_notion_sqlite import (
    SQLiteCanonicalNotionCatalogAdapter,
)
from backend.modules.resource_library.application.queries.enumerate_canonical_notions import (
    EnumerateCanonicalNotionsQuery,
)
from backend.modules.resource_library.ports.outbound.canonical_notion_catalog import (
    CanonicalNotionIdentityRecord,
)


class _Catalog:
    def __init__(self, rows: tuple[CanonicalNotionIdentityRecord, ...]) -> None:
        self.rows = rows

    def list_canonical_notion_identities(self) -> tuple[CanonicalNotionIdentityRecord, ...]:
        return self.rows


def test_application_query_preserves_canonical_identity_and_applicability() -> None:
    rows = (
        CanonicalNotionIdentityRecord(
            "notion:a", "Alpha", "CANONICAL", ("BTS_CG_YEAR_2",), ("method:a",)
        ),
        CanonicalNotionIdentityRecord("notion:b", "Bêta", "CANONICAL"),
    )
    actual = EnumerateCanonicalNotionsQuery(_Catalog(rows)).execute()
    assert [(item.notion_id, item.canonical_label) for item in actual] == [
        ("notion:a", "Alpha"),
        ("notion:b", "Bêta"),
    ]
    assert actual[0].level_applicability == ("BTS_CG_YEAR_2",)
    assert actual[0].method_refs == ("method:a",)


@pytest.mark.parametrize(
    "rows",
    [
        (
            CanonicalNotionIdentityRecord("notion:a", "Alpha", "CANONICAL"),
            CanonicalNotionIdentityRecord("notion:a", "Alpha bis", "CANONICAL"),
        ),
        (CanonicalNotionIdentityRecord("notion:m", "Merged", "MERGED"),),
        (CanonicalNotionIdentityRecord("notion:x", "   ", "CANONICAL"),),
    ],
)
def test_application_query_rejects_ambiguous_or_noncanonical_inventory(rows) -> None:
    with pytest.raises(ValueError, match="R6_NOTION_CATALOG_IDENTITY_INVALID"):
        EnumerateCanonicalNotionsQuery(_Catalog(rows)).execute()


def test_sqlite_adapter_is_query_only_and_excludes_merged_rows() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE notion(id TEXT, canonical_label TEXT, identity_status TEXT);
        CREATE TABLE object_registry(object_id TEXT, object_type TEXT);
        CREATE TABLE level(id TEXT, code TEXT, label TEXT);
        CREATE TABLE pedagogical_context(id TEXT, level_id TEXT);
        CREATE TABLE notion_context(notion_id TEXT, context_id TEXT, status TEXT);
        CREATE TABLE method_notion(method_id TEXT, notion_id TEXT);
        INSERT INTO notion VALUES ('notion:a', 'Alpha', 'CANONICAL');
        INSERT INTO notion VALUES ('notion:m', 'Merged', 'MERGED');
        INSERT INTO object_registry VALUES ('notion:a', 'NOTION');
        INSERT INTO object_registry VALUES ('notion:m', 'NOTION');
        INSERT INTO level VALUES ('level:bts2', 'BTS_CG_YEAR_2', 'BTS CG 2e année');
        INSERT INTO pedagogical_context VALUES ('context:bts2', 'level:bts2');
        INSERT INTO notion_context VALUES ('notion:a', 'context:bts2', 'ACTIVE');
        INSERT INTO method_notion VALUES ('method:a', 'notion:a');
        """
    )
    connection.execute("PRAGMA query_only=ON")
    adapter = SQLiteCanonicalNotionCatalogAdapter(connection)
    try:
        assert adapter.list_canonical_notion_identities() == (
            CanonicalNotionIdentityRecord(
                "notion:a", "Alpha", "CANONICAL", ("BTS_CG_YEAR_2",), ("method:a",)
            ),
        )
    finally:
        adapter.close()


def test_sqlite_adapter_refuses_writable_connection() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        with pytest.raises(ValueError, match="R6_READ_ONLY_REQUIRED"):
            SQLiteCanonicalNotionCatalogAdapter(connection)
    finally:
        connection.close()
