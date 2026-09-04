"""Derived SQLite implementation of Phase 7 OP-12."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from backend.adapters.outbound.persistence.vocabulary import decode_resource


@dataclass(frozen=True, slots=True)
class ResourceCatalogView:
    resource_ref: str
    title: str
    availability_status: str
    projection_freshness: str = "seed-derived"


class ReadModelAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def resource_catalog(self, *, limit: int = 5) -> tuple[ResourceCatalogView, ...]:
        rows = self._connection.execute(
            """SELECT id, resource_type, canonical_title, identity_status
               FROM resource ORDER BY id LIMIT ?""",
            (limit,),
        ).fetchall()
        return tuple(
            ResourceCatalogView(
                str(row[0]),
                str(row[2]),
                decode_resource(row[1], row[3]).semantic_state.availability_status.value,
            )
            for row in rows
        )

    def close(self) -> None:
        self._connection.close()
