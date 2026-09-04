from __future__ import annotations

import sqlite3

from backend.adapters.outbound.persistence.sqlite import ResourceStore
from backend.adapters.outbound.persistence.vocabulary import decode_resource
from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.ports.outbound import ResourceRecord


class SQLiteResourceStoreAdapter:
    """OP-03 mapper from the existing C0 ResourceStore to M03 logical records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        self._connection = connection
        self._store = ResourceStore(connection)

    def load_resource(self, resource_ref: ResourceRef) -> ResourceRecord | None:
        if type(resource_ref) is not ResourceRef:
            raise TypeError("resource_ref must be a ResourceRef")
        record = self._store.load_resource(resource_ref.value)
        if record is None:
            return None
        values = decode_resource(record.get("resource_type"), record.get("identity_status"))
        return ResourceRecord(
            resource_ref=ResourceRef(_text(record, "id")),
            resource_type=values.resource_type,
            canonical_title=_text(record, "canonical_title"),
            semantic_state=values.semantic_state,
        )

    def close(self) -> None:
        self._connection.close()


def _text(record: dict[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if type(value) is not str or not value:
        raise ValueError(f"resource record has invalid {field_name}")
    return value
