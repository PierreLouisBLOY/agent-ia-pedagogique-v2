from backend.adapters.inbound.application.runtime_schema_inspection import (
    RuntimeSchemaInspectionInbound,
)
from backend.adapters.outbound.persistence.runtime_schema_inspection import (
    SQLiteRuntimeSchemaInspectionAdapter,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.modules.local_provisioning.application.inspect_runtime_schema import (
    InspectRuntimeSchema,
)


def build_runtime_schema_inspection_inbound(
    target: Read15RuntimeTarget,
) -> RuntimeSchemaInspectionInbound:
    target.validate()
    return RuntimeSchemaInspectionInbound(InspectRuntimeSchema(
        SQLiteRuntimeSchemaInspectionAdapter(target.runtime_path, target.data_root,
                                             target.expected_sha256),
        target.expected_sha256,
    ))
