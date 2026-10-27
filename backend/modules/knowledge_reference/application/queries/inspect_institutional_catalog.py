from __future__ import annotations

from collections.abc import Mapping

from backend.modules.knowledge_reference.ports.outbound.institutional_catalog import (
    InstitutionalSchemaPort,
    InstitutionalTableSchema,
)


class InspectInstitutionalCatalog:
    def __init__(self, catalog: InstitutionalSchemaPort) -> None:
        self.catalog = catalog

    def execute(self) -> tuple[InstitutionalTableSchema, ...]:
        result = self.catalog.inspect_institutional_schema()
        if len(result) > 100 or any(len(row.columns) > 100 or row.rows < 0 or
                                 (row.definition is not None and len(row.definition) > 16000) for row in result):
            raise ValueError("INSTITUTIONAL_CATALOG_BOUNDS")
        return result

    def read(self) -> Mapping[str, object]:
        data = self.catalog.read_institutional_catalog()
        if len(data) > 20 or any(not isinstance(rows, (list, tuple)) or len(rows) > 10000
                                for rows in data.values()):
            raise ValueError("INSTITUTIONAL_CATALOG_BOUNDS")
        return data

    def resolve_scope(self, *, version_ref: str, element_ref: str, notion_refs: tuple[str, ...],
                      local_year: str | None = None) -> dict[str, object]:
        from backend.modules.knowledge_reference.application.queries.qualified_institutional_corpus import (
            QualifiedInstitutionalCorpus,
        )

        return QualifiedInstitutionalCorpus(self.read()).resolve_scope(version_ref=version_ref,
            element_ref=element_ref, notion_refs=notion_refs, local_year=local_year)

    def treatment(self) -> dict[str, object]:
        from backend.modules.knowledge_reference.application.queries.qualified_institutional_corpus import (
            QualifiedInstitutionalCorpus,
        )

        return QualifiedInstitutionalCorpus(self.read()).treatment()
