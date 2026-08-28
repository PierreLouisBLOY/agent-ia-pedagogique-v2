"""Derived SQLite implementation of Phase 7 OP-12."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceCatalogView:
    resource_ref: str
    title: str
    identity_status: str
    projection_freshness: str = "seed-derived"


class ReadModelAdapter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def resource_catalog(self, *, limit: int = 5) -> tuple[ResourceCatalogView, ...]:
        rows = self._connection.execute(
            """SELECT id, canonical_title, identity_status
               FROM resource ORDER BY id LIMIT ?""",
            (limit,),
        ).fetchall()
        return tuple(ResourceCatalogView(str(r[0]), str(r[1]), str(r[2])) for r in rows)

    def close(self) -> None:
        self._connection.close()
