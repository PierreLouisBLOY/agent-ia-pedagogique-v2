from __future__ import annotations

from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.canonical_notion_sqlite import (
    SQLiteCanonicalNotionCatalogAdapter,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.modules.resource_library.application.dto.output.canonical_notion import (
    CanonicalNotionIdentity,
)
from backend.modules.resource_library.application.queries.enumerate_canonical_notions import (
    EnumerateCanonicalNotionsQuery,
)


def enumerate_canonical_notions(
    target: Read15RuntimeTarget,
) -> tuple[CanonicalNotionIdentity, ...]:
    """Read the actual canonical universe through Application and a query-only adapter."""
    target.validate()
    connection = connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
    catalog = SQLiteCanonicalNotionCatalogAdapter(connection)
    try:
        result = EnumerateCanonicalNotionsQuery(catalog).execute()
    finally:
        catalog.close()
    target.validate()
    return result
