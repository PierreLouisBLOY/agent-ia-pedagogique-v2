from __future__ import annotations

import sqlite3

from backend.adapters.outbound.persistence.sqlite import ResourceStore
from backend.modules.resource_library.ports.outbound import ResourceRecord
from backend.shared_kernel._strings import require_non_empty


class SQLiteResourceStoreAdapter:
    """OP-03 mapper from the existing C0 ResourceStore to M03 logical records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        self._connection = connection
        self._store = ResourceStore(connection)

    def load_resource(self, resource_ref: str) -> ResourceRecord | None:
        require_non_empty(resource_ref, "resource_ref")
        record = self._store.load_resource(resource_ref)
        if record is None:
            return None
        return ResourceRecord(
            resource_ref=_text(record, "id"),
            resource_type=_text(record, "resource_type"),
            canonical_title=_text(record, "canonical_title"),
            identity_status=_text(record, "identity_status"),
        )

    def close(self) -> None:
        self._connection.close()


def _text(record: dict[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if type(value) is not str or not value:
        raise ValueError(f"resource record has invalid {field_name}")
    return value
