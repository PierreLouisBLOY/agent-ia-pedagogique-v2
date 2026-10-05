from __future__ import annotations

from backend.adapters.inbound.application.institutional_catalog import InstitutionalCatalogInbound
from backend.adapters.inbound.application.stmg_alignment import STMGAlignmentInbound
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.institutional_sqlite import (
    SQLiteInstitutionalCatalogAdapter,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.modules.knowledge_reference.application.queries.inspect_institutional_catalog import (
    InspectInstitutionalCatalog,
)
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment


def inspect_institutional_catalog(target: Read15RuntimeTarget, *, read: bool = False) -> dict[str, object]:
    target.validate()
    connection = connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
    try:
        inbound = InstitutionalCatalogInbound(InspectInstitutionalCatalog(
            SQLiteInstitutionalCatalogAdapter(connection)))
        result = inbound.read() if read else inbound.inspect()
    finally:
        connection.close()
    target.validate()
    return result


def stmg_alignment(target: Read15RuntimeTarget, *, selection: dict[str, object] | None = None,
                   reference: dict[str, object] | None = None, matrix: bool = False) -> dict[str, object]:
    target.validate()
    connection = connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
    try:
        inbound = STMGAlignmentInbound(ReadSTMGAlignment(SQLiteInstitutionalCatalogAdapter(connection)))
        if selection is not None:
            if reference is None:
                raise ValueError("P0_INSTITUTIONAL_REFERENCE_REQUIRED")
            result = inbound.resolve(selection, reference)
        else:
            result = inbound.matrix() if matrix else inbound.catalog()
    finally:
        connection.close()
    target.validate()
    return result
