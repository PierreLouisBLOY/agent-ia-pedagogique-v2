"""Explicit maintenance composition only; no default/runtime/HTTP registration."""

from pathlib import Path

from backend.adapters.inbound.application.sql_successor import SQLSuccessorInbound
from backend.adapters.outbound.persistence.sql_successor import SQLiteSQLSuccessorAdapter
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.filesystem import assert_local_data_root, resolve_secure_path
from backend.modules.local_provisioning.application.sql_successor import (
    ApplySQLSuccessor,
    ResolveSuccessorCurrentVersion,
    SQLSuccessorBinding,
)


def build_sql_successor_inbound(
    source: Read15RuntimeTarget,
    successor_root: Path,
    binding: SQLSuccessorBinding,
) -> SQLSuccessorInbound:
    binding.validate()
    source.validate()
    root = assert_local_data_root(successor_root)
    repository = Path(__file__).resolve().parents[4]
    if root == repository or root.is_relative_to(repository):
        raise ValueError("SQL_SUCCESSOR_OUTSIDE_REPOSITORY_REQUIRED")
    if source.expected_sha256 != binding.snapshot.source_sha256:
        raise ValueError("SQL_SUCCESSOR_SOURCE_BINDING")
    if root == source.data_root or root.is_relative_to(source.data_root):
        raise ValueError("SQL_SUCCESSOR_DISTINCT_ROOT_REQUIRED")
    resolve_secure_path(root, allowed_root=root.parent)
    gateway = SQLiteSQLSuccessorAdapter(source.runtime_path, source.data_root, root, binding)
    return SQLSuccessorInbound(
        ApplySQLSuccessor(gateway, binding), ResolveSuccessorCurrentVersion(gateway)
    )
