from __future__ import annotations

from backend.adapters.inbound.application.bts_alignment import BTSAlignmentInbound
from backend.adapters.inbound.application.institutional_catalog import InstitutionalCatalogInbound
from backend.adapters.inbound.application.stmg_alignment import STMGAlignmentInbound
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.institutional_sqlite import (
    SQLiteInstitutionalCatalogAdapter,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.modules.knowledge_reference.application.queries.bts_alignment import ReadBTSAlignment
from backend.modules.knowledge_reference.application.queries.inspect_institutional_catalog import (
    InspectInstitutionalCatalog,
)
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment


def inspect_institutional_catalog(target: Read15RuntimeTarget, *, read: bool = False,
                                 treatment: bool = False,
                                 scope: tuple[str, str, tuple[str, ...], str | None] | None = None) -> dict[str, object]:
    target.validate()
    connection = connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
    try:
        inbound = InstitutionalCatalogInbound(InspectInstitutionalCatalog(
            SQLiteInstitutionalCatalogAdapter(connection)))
        result = inbound.resolve_scope(version_ref=scope[0], element_ref=scope[1], notion_refs=scope[2], local_year=scope[3]) if scope else inbound.treatment() if treatment else inbound.read() if read else inbound.inspect()
    finally:
        connection.close()
    target.validate()
    return result


def bts_alignment(target: Read15RuntimeTarget, *, selection: dict[str, object] | None = None,
                  reference: dict[str, object] | None = None) -> dict[str, object]:
    target.validate()
    connection = connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
    try:
        inbound = BTSAlignmentInbound(ReadBTSAlignment(SQLiteInstitutionalCatalogAdapter(connection)))
        if selection is not None:
            if reference is None:
                raise ValueError("P0_INSTITUTIONAL_REFERENCE_REQUIRED")
            result = inbound.resolve(selection, reference)
        else:
            result = {"bts_frameworks": inbound.catalog()}
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
