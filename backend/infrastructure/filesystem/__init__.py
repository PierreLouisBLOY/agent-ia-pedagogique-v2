"""Local filesystem security primitives owned by infrastructure."""

from backend.infrastructure.filesystem.security import (
    LocalFileSecurityCode,
    LocalFileSecurityError,
    PathSnapshot,
    PermissionStatus,
    assert_distinct_paths,
    assert_local_data_root,
    atomic_publish_fresh,
    atomic_replace_checked,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    hash_file_nofollow,
    inspect_permission_status,
    private_temporary_file,
    read_file_nofollow,
    resolve_secure_path,
)

__all__ = [
    "LocalFileSecurityCode",
    "LocalFileSecurityError",
    "PathSnapshot",
    "PermissionStatus",
    "assert_distinct_paths",
    "assert_local_data_root",
    "atomic_publish_fresh",
    "atomic_replace_checked",
    "capture_secure_path",
    "ensure_private_directory",
    "harden_private_file",
    "hash_file_nofollow",
    "inspect_permission_status",
    "private_temporary_file",
    "read_file_nofollow",
    "resolve_secure_path",
]
