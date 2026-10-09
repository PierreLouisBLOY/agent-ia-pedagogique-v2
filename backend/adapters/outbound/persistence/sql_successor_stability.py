"""Windows source stability without permissions, sidecar removal or mode changes."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, cast

from backend.infrastructure.filesystem import capture_secure_path


@contextmanager
def pinned_windows_paths(
    *,
    root: Path,
    files: tuple[Path, ...] = (),
    directories: tuple[Path, ...] = (),
) -> Iterator[None]:
    if os.name != "nt":
        raise ValueError("SQL_SUCCESSOR_WINDOWS_STABILITY_REQUIRED")
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
    close = kernel.CloseHandle
    close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
    handles: list[int] = []
    # Directory handles omit SHARE_DELETE to pin the whole ancestor chain.
    # File handles omit SHARE_WRITE and SHARE_DELETE: existing writers (including
    # writable mappings) cause refusal; subsequent writers/substitution are denied.
    parents = set(directories)
    for path in (*files, *directories):
        before = capture_secure_path(path, allowed_root=root)
        if not before.exists:
            raise ValueError("SQL_SUCCESSOR_PIN_EXISTING_REQUIRED")
        parents.update(path.parents)
    try:
        for path in sorted(parents, key=lambda p: len(p.parts)):
            handle = create(str(path), 0, 3, None, 3, 0x02200000, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise ValueError("SQL_SUCCESSOR_DIRECTORY_STABILITY_UNAVAILABLE")
            handles.append(handle)
        for path in files:
            before = capture_secure_path(path, allowed_root=root)
            if not before.is_file:
                raise ValueError("SQL_SUCCESSOR_PIN_REGULAR_REQUIRED")
            handle = create(str(path), 0x80000000, 1, None, 3, 0x00200000, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise ValueError("SQL_SUCCESSOR_SOURCE_WRITER_PRESENT")
            handles.append(handle)
            if not before.same_state(capture_secure_path(path, allowed_root=root)):
                raise ValueError("SQL_SUCCESSOR_PIN_SUBSTITUTION")
        yield
    finally:
        for handle in reversed(handles):
            close(handle)


@contextmanager
def exclusive_copy_destination(path: Path, root: Path) -> Iterator[BinaryIO]:
    """Open a regular, non-hardlinked destination before any truncation."""
    import msvcrt
    import stat

    before = capture_secure_path(path, allowed_root=root)
    if not before.is_file:
        raise ValueError("SQL_SUCCESSOR_COPY_REGULAR_REQUIRED")
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
    handle = create(str(path), 0xC0000000, 0, None, 3, 0x00200000, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ValueError("SQL_SUCCESSOR_COPY_DESTINATION_BUSY")
    fd = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
    with os.fdopen(fd, "r+b") as writer:
        current = os.fstat(writer.fileno())
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) != (before.device, before.inode)
            or not before.same_state(capture_secure_path(path, allowed_root=root))
        ):
            raise ValueError("SQL_SUCCESSOR_COPY_DESTINATION_SUBSTITUTION")
        writer.truncate(0)
        yield cast(BinaryIO, writer)
