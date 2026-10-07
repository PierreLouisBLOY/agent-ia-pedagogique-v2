"""Read explicit native status columns only; never infer a resource version."""

import sqlite3

from backend.modules.resource_library.contracts.dto.search_source_status import SearchSourceStatus

TABLES = {
    "NOTION": "notion",
    "QUESTION": "question",
    "PEDAGOGICAL_CONTENT": "pedagogical_content",
    "METHOD": "method",
    "RESOURCE": "resource",
}
FIELDS = ("identity_status", "lifecycle_status", "validation_status")


def source_status(
    connection: sqlite3.Connection, object_ref: str, object_kind: str
) -> SearchSourceStatus:
    table = TABLES.get(object_kind)
    if table is None:
        return SearchSourceStatus("CURRENT")
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(" + table + ")")}
    selected = [
        field
        for field in FIELDS
        if field in columns and (object_kind != "RESOURCE" or field == "identity_status")
    ]
    if "id" not in columns or not selected:
        return SearchSourceStatus(
            "CURRENT",
            status_basis="EXACT_VERSION_REQUIRED"
            if object_kind == "RESOURCE"
            else "STATUS_UNAVAILABLE",
        )
    row = connection.execute(
        "SELECT " + ", ".join(selected) + " FROM " + table + " WHERE id = ?", (object_ref,)
    ).fetchone()
    if row is None:
        return SearchSourceStatus("CURRENT")
    values = {
        field: "UNKNOWN" if value is None else str(value)
        for field, value in zip(selected, row, strict=True)
    }
    return SearchSourceStatus(
        "CURRENT",
        **values,
        status_basis="EXACT_VERSION_REQUIRED" if object_kind == "RESOURCE" else "OBJECT_ROW",
    )


def passage_source_status(
    connection: sqlite3.Connection, passage_ref: str
) -> SearchSourceStatus | None:
    if not connection.execute("PRAGMA table_info(object_registry)").fetchone():
        return None  # Historical document-only schema has no registered object status.
    row = connection.execute(
        """SELECT sc.object_id, registry.object_type FROM search_chunk AS sc
        JOIN object_registry AS registry ON registry.object_id = sc.object_id
        WHERE sc.id = ? AND sc.status = 'CURRENT'""",
        (passage_ref,),
    ).fetchone()
    return None if row is None else source_status(connection, str(row[0]), str(row[1]))
