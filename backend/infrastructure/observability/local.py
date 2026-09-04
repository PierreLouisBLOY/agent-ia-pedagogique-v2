"""Private local rotating NDJSON writer for owner-approved OBS-A."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Final

from backend.infrastructure.filesystem import (
    LocalFileSecurityCode,
    LocalFileSecurityError,
    assert_local_data_root,
    atomic_publish_fresh,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    private_temporary_file,
    resolve_secure_path,
)

LOCAL_OBSERVABILITY_OPTION: Final = "OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S"
OBSERVABILITY_LOG_RELATIVE_PATH: Final = Path("logs") / "observability.ndjson"
ROTATION_SIZE_BYTES: Final = 5 * 1_024 * 1_024
MAX_LOG_FILE_COUNT: Final = 5
RETENTION_DAYS: Final = 14
MAX_SHUTDOWN_FLUSH_SECONDS: Final = 2
_ROTATED_FILE_COUNT: Final = MAX_LOG_FILE_COUNT - 1


class LocalRotatingNdjsonWriter:
    """Append complete records to a private local-only five-file set."""

    def __init__(
        self,
        data_root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._root = assert_local_data_root(data_root)
        _assert_outside_repository(self._root)
        self._path = resolve_secure_path(
            self._root / OBSERVABILITY_LOG_RELATIVE_PATH,
            allowed_root=self._root,
        )
        self._clock = clock or _utc_now
        self._lock = Lock()
        self._closed = False
        ensure_private_directory(self._root, allowed_root=self._root)
        ensure_private_directory(self._path.parent, allowed_root=self._root)
        self.purge_expired()
        self._ensure_active()

    @property
    def path_class(self) -> str:
        return "V2_DATA_ROOT_LOCAL_PRIVATE_LOG"

    def write(self, record: str) -> int:
        if type(record) is not str or not record.endswith("\n") or record.count("\n") != 1:
            raise ValueError("record must be exactly one NDJSON line")
        payload = record.encode("utf-8")
        if not payload or len(payload) > ROTATION_SIZE_BYTES:
            raise ValueError("record size is outside the local sink bound")
        with self._lock:
            if self._closed:
                raise ValueError("writer is closed")
            self._purge_expired_unlocked()
            self._ensure_active()
            active = capture_secure_path(self._path, allowed_root=self._root)
            if active.size_bytes and active.size_bytes + len(payload) > ROTATION_SIZE_BYTES:
                self._rotate()
                active = capture_secure_path(self._path, allowed_root=self._root)
            flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(active.path, flags)
            try:
                opened = os.fstat(descriptor)
                if (opened.st_dev, opened.st_ino) != (active.device, active.inode):
                    raise LocalFileSecurityError(LocalFileSecurityCode.PATH_CHANGED)
                offset = 0
                while offset < len(payload):
                    written = os.write(descriptor, payload[offset:])
                    if written <= 0:
                        raise OSError("local observability write failed")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            after = capture_secure_path(self._path, allowed_root=self._root)
            if not active.same_identity(after):
                raise LocalFileSecurityError(LocalFileSecurityCode.PATH_CHANGED)
            return len(record)

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_expired_unlocked()

    def _purge_expired_unlocked(self) -> int:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        threshold = now.astimezone(UTC) - timedelta(days=RETENTION_DAYS)
        removed = 0
        for index in range(1, _ROTATED_FILE_COUNT + 1):
            path = self._rotated(index)
            snapshot = capture_secure_path(path, allowed_root=self._root)
            if not snapshot.exists:
                continue
            if not snapshot.is_file or snapshot.modified_ns is None:
                raise LocalFileSecurityError(LocalFileSecurityCode.FILE_REQUIRED)
            modified = datetime.fromtimestamp(
                snapshot.modified_ns / 1_000_000_000,
                tz=UTC,
            )
            if modified < threshold:
                snapshot.path.unlink()
                removed += 1
        return removed

    def flush(self) -> None:
        return

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _ensure_active(self) -> None:
        snapshot = capture_secure_path(self._path, allowed_root=self._root)
        if snapshot.exists:
            if not snapshot.is_file:
                raise LocalFileSecurityError(LocalFileSecurityCode.FILE_REQUIRED)
            harden_private_file(self._path, allowed_root=self._root)
            return
        temporary = private_temporary_file(
            self._path.parent,
            allowed_root=self._root,
            prefix=".observability-",
            suffix=".ndjson.tmp",
        )
        try:
            atomic_publish_fresh(temporary, self._path, allowed_root=self._root)
        finally:
            temporary.unlink(missing_ok=True)

    def _rotate(self) -> None:
        oldest = self._rotated(_ROTATED_FILE_COUNT)
        oldest_snapshot = capture_secure_path(oldest, allowed_root=self._root)
        if oldest_snapshot.exists:
            if not oldest_snapshot.is_file:
                raise LocalFileSecurityError(LocalFileSecurityCode.FILE_REQUIRED)
            oldest_snapshot.path.unlink()
        for index in range(_ROTATED_FILE_COUNT - 1, 0, -1):
            source = self._rotated(index)
            source_snapshot = capture_secure_path(source, allowed_root=self._root)
            if source_snapshot.exists:
                if not source_snapshot.is_file:
                    raise LocalFileSecurityError(LocalFileSecurityCode.FILE_REQUIRED)
                os.replace(source_snapshot.path, self._rotated(index + 1))
        active = capture_secure_path(self._path, allowed_root=self._root)
        if not active.is_file:
            raise LocalFileSecurityError(LocalFileSecurityCode.FILE_REQUIRED)
        os.replace(active.path, self._rotated(1))
        harden_private_file(self._rotated(1), allowed_root=self._root)
        self._ensure_active()

    def _rotated(self, index: int) -> Path:
        return self._path.with_name(f"{self._path.name}.{index}")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _assert_outside_repository(data_root: Path) -> None:
    """Fail closed when the configured sink would write inside a checkout."""

    for candidate in (data_root, *data_root.parents):
        if (candidate / ".git").exists():
            raise ValueError("observability data root must be outside the repository")
