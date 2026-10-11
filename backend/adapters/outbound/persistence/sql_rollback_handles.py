"""Windows no-replace handle moves for the closed RBACK maintenance only."""

from __future__ import annotations

import ctypes
import hashlib
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.infrastructure.filesystem import capture_secure_path
from backend.modules.local_provisioning.application.sql_rollback import RollbackFileIdentity


class _RenameInfo(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_uint32),
        ("root", ctypes.c_void_p),
        ("length", ctypes.c_uint32),
        ("name", ctypes.c_wchar * 1),
    ]


class RollbackPin:
    def __init__(self, fd: int, root: Path) -> None:
        self.fd, self.root = fd, root

    def identity(self) -> RollbackFileIdentity:
        opened = os.fstat(self.fd)
        digest = hashlib.sha256()
        os.lseek(self.fd, 0, os.SEEK_SET)
        while block := os.read(self.fd, 1024 * 1024):
            digest.update(block)
        return RollbackFileIdentity(
            opened.st_dev, opened.st_ino, opened.st_size, digest.hexdigest()
        )

    def verify(self, path: Path, expected: RollbackFileIdentity, links: int) -> None:
        named = capture_secure_path(path, allowed_root=self.root)
        opened = os.fstat(self.fd)
        if (
            not named.is_file
            or not stat.S_ISREG(opened.st_mode)
            or (named.device, named.inode) != (expected.device, expected.inode)
            or opened.st_nlink != links
            or self.identity() != expected
        ):
            raise ValueError("SQL_ROLLBACK_IDENTITY_OR_LINK_CHANGED")

    def rename_fresh(self, destination: Path) -> None:
        import msvcrt

        if capture_secure_path(destination, allowed_root=self.root).exists:
            raise ValueError("SQL_ROLLBACK_DESTINATION_COLLISION")
        encoded = str(destination).encode("utf-16-le")
        buffer = ctypes.create_string_buffer(_RenameInfo.name.offset + len(encoded) + 2)
        info = _RenameInfo.from_buffer(buffer)
        info.flags, info.root, info.length = 0, None, len(encoded)
        ctypes.memmove(ctypes.addressof(buffer) + _RenameInfo.name.offset, encoded, len(encoded))
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        move = kernel.SetFileInformationByHandle
        move.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
        move.restype = ctypes.c_int
        # FileRenameInfo; flags zero explicitly disables replace.
        if not move(msvcrt.get_osfhandle(self.fd), 3, buffer, len(buffer)):
            raise ValueError("SQL_ROLLBACK_FRESH_RENAME_REFUSED") from ctypes.WinError(
                ctypes.get_last_error()
            )


@contextmanager
def rollback_pin(
    path: Path, root: Path, *, rename: bool = False, exclusive: bool = False
) -> Iterator[RollbackPin]:
    if os.name != "nt":
        raise ValueError("SQL_ROLLBACK_WINDOWS_REQUIRED")
    import msvcrt

    before = capture_secure_path(path, allowed_root=root)
    if not before.is_file:
        raise ValueError("SQL_ROLLBACK_EXISTING_REGULAR_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    create.restype = ctypes.c_void_p
    handle = create(
        str(path),
        0x80010000 if rename else 0x80000000,
        0 if exclusive else 1,
        None,
        3,
        0x00200000,
        None,
    )
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ValueError("SQL_ROLLBACK_WRITER_OR_MAINTENANCE_PRESENT") from ctypes.WinError(
            ctypes.get_last_error()
        )
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close = kernel.CloseHandle
        close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
        close(handle)
        raise
    try:
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.device, before.inode)
            or not before.same_state(capture_secure_path(path, allowed_root=root))
        ):
            raise ValueError("SQL_ROLLBACK_OPENED_SUBSTITUTION")
        yield RollbackPin(fd, root)
    finally:
        os.close(fd)


MAINTENANCE_LOCK = "rollback-maintenance.lock"


@contextmanager
def refuse_successor_rollback_history(root: Path) -> Iterator[None]:
    path = root / MAINTENANCE_LOCK
    if capture_secure_path(path, allowed_root=root).exists:
        with rollback_pin(path, root, exclusive=True):
            raise ValueError("SQL_SUCCESSOR_ROLLBACK_HISTORY_RETAINED")
    yield
