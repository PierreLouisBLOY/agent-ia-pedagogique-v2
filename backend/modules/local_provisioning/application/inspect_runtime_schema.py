"""Preparatory inspection only; the migration path is a separate reviewed contract."""
import re
from dataclasses import dataclass

from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeFileMetadata,
    RuntimeSchemaSnapshot,
    require_immutable_schema_file_set,
)
from backend.modules.local_provisioning.ports.runtime_schema_inspection import (
    RuntimeSchemaInspectionPort,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class InspectRuntimeSchema:
    gateway: RuntimeSchemaInspectionPort
    expected_sha256: str

    def execute(self) -> RuntimeSchemaSnapshot:
        if not _SHA256.fullmatch(self.expected_sha256):
            raise ValueError("RUNTIME_SCHEMA_EXPECTATION_REQUIRED")
        result = self.gateway.inspect_schema()
        if result.source_sha256 != self.expected_sha256:
            raise ValueError("RUNTIME_SCHEMA_SOURCE_MISMATCH")
        if (not _SHA256.fullmatch(result.schema_sha256)
                or not 0 < result.source_size
                or not 0 < len(result.objects) <= 2048
                or len(result.tables) > 256 or len(result.indexes) > 1024):
            raise ValueError("RUNTIME_SCHEMA_BOUNDS")
        require_immutable_schema_file_set(result.file_set)
        if (dict(result.connection_flags).get("query_only") != 1
                or dict(result.connection_flags).get("foreign_keys") != 1
                or result.absent_sidecars != tuple(
                    row.suffix for row in result.file_set[1:] if not row.exists)):
            raise ValueError("RUNTIME_SCHEMA_READ_ONLY_REQUIRED")
        keys = [(obj.kind, obj.name) for obj in result.objects]
        if len(keys) != len(set(keys)) or any(
            obj.kind not in ("table", "view", "trigger", "index")
            or (obj.definition is not None and len(obj.definition) > 65536)
            for obj in result.objects
        ):
            raise ValueError("RUNTIME_SCHEMA_OBJECTS")
        if any(len(table.columns) > 256 or len(table.foreign_keys) > 256
               or len(table.indexes) > 256 for table in result.tables):
            raise ValueError("RUNTIME_SCHEMA_BOUNDS")
        return result

    def inspect_files(self) -> tuple[RuntimeFileMetadata, ...]:
        if not _SHA256.fullmatch(self.expected_sha256):
            raise ValueError("RUNTIME_SCHEMA_EXPECTATION_REQUIRED")
        result = self.gateway.inspect_files()
        if tuple(row.suffix for row in result) != ("", "-wal", "-shm", "-journal"):
            raise ValueError("RUNTIME_SCHEMA_FILE_SET_REQUIRED")
        if not result[0].exists or result[0].sha256 != self.expected_sha256:
            raise ValueError("RUNTIME_SCHEMA_SOURCE_MISMATCH")
        return result
