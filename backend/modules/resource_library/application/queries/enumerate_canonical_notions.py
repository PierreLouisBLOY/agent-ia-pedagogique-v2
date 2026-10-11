from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.application.dto.output.canonical_notion import (
    CanonicalNotionIdentity,
)
from backend.modules.resource_library.ports.outbound.canonical_notion_catalog import (
    CanonicalNotionCatalogPort,
)


@dataclass(frozen=True, slots=True)
class EnumerateCanonicalNotionsQuery:
    catalog: CanonicalNotionCatalogPort

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, CanonicalNotionCatalogPort):
            raise TypeError("CanonicalNotionCatalogPort required")

    def execute(self) -> tuple[CanonicalNotionIdentity, ...]:
        records = self.catalog.list_canonical_notion_identities()
        if type(records) is not tuple:
            raise ValueError("R6_NOTION_CATALOG_SHAPE_INVALID")
        identities = tuple(CanonicalNotionIdentity.from_record(record) for record in records)
        ids = tuple(item.notion_id for item in identities)
        if len(ids) != len(set(ids)) or any(
            not item.notion_id
            or not item.canonical_label.strip()
            or item.identity_status != "CANONICAL"
            for item in identities
        ):
            raise ValueError("R6_NOTION_CATALOG_IDENTITY_INVALID")
        return identities
