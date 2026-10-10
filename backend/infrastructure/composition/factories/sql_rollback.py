"""Explicit owner maintenance only; never a default or normal launcher composition."""

from pathlib import Path

from backend.adapters.inbound.application.sql_rollback import SQLRollbackInbound
from backend.adapters.outbound.persistence.sql_rollback import SQLiteSQLRollbackAdapter
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.filesystem import assert_local_data_root, resolve_secure_path
from backend.modules.local_provisioning.application.sql_rollback import (
    RollbackSQLSuccessor,
    SQLRollbackBinding,
)


def build_sql_rollback_inbound(
    source: Read15RuntimeTarget, successor_root: Path, binding: SQLRollbackBinding
) -> SQLRollbackInbound:
    binding.validate()
    source.validate()
    root = assert_local_data_root(successor_root)
    repository = Path(__file__).resolve().parents[4]
    if root == repository or root.is_relative_to(repository):
        raise ValueError("SQL_ROLLBACK_OUTSIDE_REPOSITORY_REQUIRED")
    if root == source.data_root or root.is_relative_to(source.data_root):
        raise ValueError("SQL_ROLLBACK_DISTINCT_ROOT_REQUIRED")
    if source.expected_sha256 != binding.successor.snapshot.source_sha256:
        raise ValueError("SQL_ROLLBACK_SOURCE_BINDING")
    resolve_secure_path(root, allowed_root=root.parent)
    gateway = SQLiteSQLRollbackAdapter(source.runtime_path, source.data_root, root, binding)
    return SQLRollbackInbound(RollbackSQLSuccessor(gateway, binding))
