from backend.modules.local_provisioning.application.inspect_runtime_schema import (
    InspectRuntimeSchema,
)
from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeFileMetadata,
    RuntimeSchemaSnapshot,
)


class RuntimeSchemaInspectionInbound:
    """Trusted preparatory reader; not registered as an agent tool or HTTP route."""

    def __init__(self, query: InspectRuntimeSchema) -> None:
        self._query = query

    def inspect(self) -> RuntimeSchemaSnapshot:
        return self._query.execute()

    def inspect_files(self) -> tuple[RuntimeFileMetadata, ...]:
        return self._query.inspect_files()
