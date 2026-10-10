"""Trusted synthetic process-stop harness; not a product CLI or credential runner."""

import json
import os
import sys
from pathlib import Path

from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.sql_rollback import build_sql_rollback_inbound
from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeFileMetadata,
    RuntimeIndexMetadata,
    RuntimeSchemaObject,
    RuntimeSchemaSnapshot,
    RuntimeTableMetadata,
)
from backend.modules.local_provisioning.application.sql_rollback import (
    RollbackFileIdentity,
    SQLRollbackBinding,
    SQLRollbackRequest,
)
from backend.modules.local_provisioning.application.sql_successor import SQLSuccessorBinding


def decode_binding(raw):
    value = dict(raw)
    successor = dict(value.pop("successor"))
    snap = dict(successor.pop("snapshot"))
    snap["objects"] = tuple(RuntimeSchemaObject(**r) for r in snap["objects"])
    snap["tables"] = tuple(
        RuntimeTableMetadata(
            r["name"],
            *(tuple(tuple(v) for v in r[key]) for key in ("columns", "foreign_keys", "indexes")),
        )
        for r in snap["tables"]
    )
    snap["indexes"] = tuple(
        RuntimeIndexMetadata(r["name"], tuple(tuple(v) for v in r["columns"]))
        for r in snap["indexes"]
    )
    for key in ("integrity", "quick_check", "absent_sidecars"):
        snap[key] = tuple(snap[key])
    snap["connection_flags"] = tuple(tuple(v) for v in snap["connection_flags"])
    snap["file_set"] = tuple(RuntimeFileMetadata(**r) for r in snap["file_set"])
    value["successor"] = SQLSuccessorBinding(**successor, snapshot=RuntimeSchemaSnapshot(**snap))
    value["published"] = RollbackFileIdentity(**value["published"])
    value["backup"] = RollbackFileIdentity(**value["backup"])
    return SQLRollbackBinding(**value)


def main():
    import backend.adapters.outbound.persistence.sql_rollback as adapter

    raw = json.loads(Path(sys.argv[1]).read_bytes())
    bound = decode_binding(raw["binding"])
    path = Path(raw["source"])
    inbound = build_sql_rollback_inbound(
        Read15RuntimeTarget(path, path.parent, bound.successor.snapshot.source_sha256),
        Path(raw["root"]),
        bound,
    )
    request = SQLRollbackRequest(
        bound.plan_sha256, bound.decision_sha256, bound.review_sha256, bound.operation_sha256
    )
    point = sys.argv[2]
    if point != "NONE":

        def stop(stage):
            if stage == point:
                os._exit(23)

        adapter._checkpoint = stop
    if point == "PREPARED_BEFORE_HASH_RETURN":
        inbound.prepare(request)
    else:
        result = inbound.execute(request, raw["intention_sha256"])
        print(json.dumps({"state": result.state, "intention_sha256": result.intention_sha256}))


if __name__ == "__main__":
    main()
