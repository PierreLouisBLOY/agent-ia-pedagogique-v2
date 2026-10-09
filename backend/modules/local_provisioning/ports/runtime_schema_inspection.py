from typing import Protocol

from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeFileMetadata,
    RuntimeSchemaSnapshot,
)


class RuntimeSchemaInspectionPort(Protocol):
    def inspect_schema(self) -> RuntimeSchemaSnapshot: ...

    def inspect_files(self) -> tuple[RuntimeFileMetadata, ...]: ...
