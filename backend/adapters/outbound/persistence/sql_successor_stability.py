"""Windows source stability without permissions, sidecar removal or mode changes."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
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
    file_descriptors: list[int] = []
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
            import msvcrt
            import stat

            try:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                close(handle)
                raise
            file_descriptors.append(fd)
            opened = os.fstat(fd)
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.device, before.inode)
                or not before.same_state(capture_secure_path(path, allowed_root=root))
            ):
                raise ValueError("SQL_SUCCESSOR_PIN_SUBSTITUTION")
        yield
    finally:
        for fd in reversed(file_descriptors):
            os.close(fd)
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


@contextmanager
def pinned_working_copy(path: Path, root: Path) -> Iterator[None]:
    """Keep the physical file stable while permitting SQLite's legitimate writes."""
    import msvcrt
    import stat

    before = capture_secure_path(path, allowed_root=root)
    if not before.is_file:
        raise ValueError("SQL_SUCCESSOR_WORKING_REGULAR_REQUIRED")
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
    # SHARE_READ|SHARE_WRITE permits SQLite; omission of SHARE_DELETE prevents
    # renaming/unlinking/replacement throughout connection/transaction/verification.
    handle = create(str(path), 0x80000000, 3, None, 3, 0x00200000, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ValueError("SQL_SUCCESSOR_WORKING_IDENTITY_UNAVAILABLE")
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    with os.fdopen(fd, "rb") as reader:
        opened = os.fstat(reader.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.device, before.inode)
            or not before.same_state(capture_secure_path(path, allowed_root=root))
        ):
            raise ValueError("SQL_SUCCESSOR_WORKING_IDENTITY_CHANGED")
        yield


def publish_pinned_fresh(
    source: Path, destination: Path, *, allowed_root: Path, guard: ExitStack
) -> None:
    """Publish one fresh hardlink while retaining the pinned evidence name.

    The shared publish-and-unlink primitive cannot unlink an identity-pinned
    Windows file. This successor deliberately retains its temporary name; no
    protection gap or cleanup of historical evidence is introduced.
    """
    from backend.infrastructure.filesystem import harden_private_file

    with pinned_windows_paths(root=allowed_root, files=(source,)):
        before = capture_secure_path(source, allowed_root=allowed_root)
        target = capture_secure_path(destination, allowed_root=allowed_root)
        if not before.is_file or target.exists or source.anchor != destination.anchor:
            raise RuntimeError("SQL_SUCCESSOR_FRESH_PUBLICATION_REQUIRED")
        try:
            os.link(source, destination)
        except OSError as error:
            raise RuntimeError("SQL_SUCCESSOR_FRESH_PUBLICATION_FAILED") from error
        # Pin the new destination name too: on Windows a handle on another
        # hardlink does not protect this new directory entry from replacement.
        guard.enter_context(pinned_windows_paths(root=allowed_root, files=(destination,)))
        if not before.same_identity(capture_secure_path(destination, allowed_root=allowed_root)):
            raise ValueError("SQL_SUCCESSOR_PUBLICATION_SUBSTITUTION")
        harden_private_file(destination, allowed_root=allowed_root)
