from __future__ import annotations

from backend.modules.knowledge_reference.application.queries.inspect_institutional_catalog import (
    InspectInstitutionalCatalog,
)


class InstitutionalCatalogInbound:
    def __init__(self, query: InspectInstitutionalCatalog) -> None:
        self.query = query

    def inspect(self) -> dict[str, object]:
        return {"contract_id": "INSTITUTIONAL-CATALOG-INSPECTION-1.0",
                "tables": [{"table": row.table, "columns": list(row.columns), "rows": row.rows,
                            "definition": row.definition}
                           for row in self.query.execute()],
                "authority": "SCHEMA_ONLY_NO_OFFICIAL_MEMBERSHIP_INFERRED"}

    def read(self) -> dict[str, object]:
        return dict(self.query.read())

    def treatment(self) -> dict[str, object]:
        return self.query.treatment()

    def resolve_scope(self, *, version_ref: str, element_ref: str, notion_refs: tuple[str, ...],
                      local_year: str | None = None) -> dict[str, object]:
        return self.query.resolve_scope(version_ref=version_ref, element_ref=element_ref,
            notion_refs=notion_refs, local_year=local_year)
