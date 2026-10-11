"""Windows-only, handle-relative private I/O for the isolated V3 successor.

No fallback to path-based I/O. Ordinary same-authority file operations cannot
rename/delete or acquire write access to pinned objects during the operation.
This does not defend against hostile administrators, process injection, or
removal of durable evidence after every handle has been closed.
"""

from __future__ import annotations

import ctypes as c
import os
from contextlib import ExitStack
from contextvars import ContextVar
from ctypes import wintypes as w
from pathlib import Path
from typing import Any


class UnicodeString(c.Structure):
    _fields_ = [("length", w.USHORT), ("maximum", w.USHORT), ("buffer", w.LPWSTR)]


class ObjectAttributes(c.Structure):
    _fields_ = [
        ("length", w.ULONG), ("root", w.HANDLE), ("name", c.POINTER(UnicodeString)),
        ("attributes", w.ULONG), ("security", w.LPVOID), ("quality", w.LPVOID),
    ]


class IoStatus(c.Structure):
    _fields_ = [("status", c.c_void_p), ("information", c.c_size_t)]


class FileIdentity(c.Structure):
    _fields_ = [("volume", c.c_ulonglong), ("identifier", c.c_ubyte * 16)]


class AttributeTag(c.Structure):
    _fields_ = [("attributes", w.DWORD), ("tag", w.DWORD)]


def _api() -> tuple[Any, Any]:
    if os.name != "nt":
        raise OSError("F02_WINDOWS_REQUIRED")
    kernel = c.WinDLL("kernel32", use_last_error=True)
    native = c.WinDLL("ntdll", use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID,
                                   w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    kernel.GetFileInformationByHandleEx.argtypes = [w.HANDLE, c.c_int, w.LPVOID, w.DWORD]
    kernel.GetFileInformationByHandleEx.restype = w.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD]
    kernel.GetFinalPathNameByHandleW.restype = w.DWORD
    kernel.ReadFile.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, c.POINTER(w.DWORD), w.LPVOID]
    kernel.ReadFile.restype = w.BOOL
    kernel.WriteFile.argtypes = [w.HANDLE, w.LPCVOID, w.DWORD, c.POINTER(w.DWORD), w.LPVOID]
    kernel.WriteFile.restype = w.BOOL
    kernel.FlushFileBuffers.argtypes = [w.HANDLE]
    kernel.FlushFileBuffers.restype = w.BOOL
    native.NtCreateFile.argtypes = [c.POINTER(w.HANDLE), w.DWORD,
        c.POINTER(ObjectAttributes), c.POINTER(IoStatus), c.c_void_p, w.ULONG,
        w.ULONG, w.ULONG, w.ULONG, w.LPVOID, w.ULONG]
    native.NtCreateFile.restype = w.LONG
    native.RtlNtStatusToDosError.argtypes = [w.LONG]
    native.RtlNtStatusToDosError.restype = w.ULONG
    return kernel, native


def _parts(path: Path) -> tuple[str, tuple[str, ...]]:
    # Exclude UNC/device namespaces, ADS, relative traversal and ambiguous tails.
    if not path.is_absolute() or len(path.drive) != 2 or path.drive[1] != ":":
        raise ValueError("F02_LOCAL_ABSOLUTE_PATH_REQUIRED")
    parts = path.parts[1:]
    for part in parts:
        _component(part)
    return path.anchor, parts


def _component(name: str) -> None:
    if (not name or name in {".", ".."} or any(ch in name for ch in '\\/:\x00')
            or name.endswith((".", " "))):
        raise ValueError("F02_COMPONENT_REJECTED")


class Handle:
    def __init__(self, raw: int, kernel: Any) -> None:
        self.raw, self.kernel = raw, kernel
        self.final_name = ""
        self.identity: tuple[int, bytes] = (0, b"")
        self.chain_identity: tuple[tuple[int, bytes], ...] = ()

    def close(self) -> None:
        if self.raw:
            self.kernel.CloseHandle(self.raw)
            self.raw = 0


def _checked(raw: int, kernel: Any, *, directory: bool) -> Handle:
    handle = Handle(raw, kernel)
    info = AttributeTag()
    try:
        if not kernel.GetFileInformationByHandleEx(raw, 9, c.byref(info), c.sizeof(info)):
            raise OSError("F02_HANDLE_OPERATION_FAILED")
        if info.attributes & 0x400:
            raise ValueError("PRIVATE_LINK_REJECTED")
        if bool(info.attributes & 0x10) != directory:
            raise ValueError("F02_OBJECT_TYPE_REJECTED")
        identity = FileIdentity()
        if not kernel.GetFileInformationByHandleEx(raw, 18, c.byref(identity), c.sizeof(identity)):
            raise OSError("F02_HANDLE_IDENTITY_FAILED")
        final = c.create_unicode_buffer(32768)
        length = kernel.GetFinalPathNameByHandleW(raw, final, len(final), 0)
        if not 0 < length < len(final):
            raise OSError("F02_FINAL_PATH_FAILED")
        handle.final_name = final.value
        handle.identity = (identity.volume, bytes(identity.identifier))
        return handle
    except BaseException:
        handle.close()
        raise


def _child(parent: Handle, name: str, *, directory: bool, create: bool = False,
           write: bool = False) -> Handle:
    _component(name)
    kernel, native = _api()
    text = c.create_unicode_buffer(name)
    size = len(name.encode("utf-16-le"))
    string = UnicodeString(size, size + 2, c.cast(text, w.LPWSTR))
    attributes = ObjectAttributes(c.sizeof(ObjectAttributes), parent.raw,
                                  c.pointer(string), 0x40, None, None)
    result, status = w.HANDLE(), IoStatus()
    # Directory handles never perform synchronous data I/O. Prefer traversal access
    # where granted because Windows needs a read-class handle to hold delete sharing;
    # fall back only for ACCESS_DENIED so restricted profile ancestors remain inspectable.
    if directory:
        access = 0xA0  # FILE_READ_ATTRIBUTES | FILE_TRAVERSE
        options = 0x200000 | 0x1  # OPEN_REPARSE_POINT | DIRECTORY_FILE
    else:
        access = 0x100080 | (0x40000000 if write else 0x80000000)
        options = 0x200000 | 0x20 | 0x40  # OPEN_REPARSE_POINT | SYNCHRONOUS | NON_DIRECTORY
    code = native.NtCreateFile(c.byref(result), access, c.byref(attributes),
        c.byref(status), None, 0, 1, 2 if create else 1, options, None, 0)
    if directory and c.c_uint32(code).value == 0xC0000022:
        access = 0x80  # FILE_READ_ATTRIBUTES: metadata-only fallback for restricted ancestors
        result, status = w.HANDLE(), IoStatus()
        code = native.NtCreateFile(c.byref(result), access, c.byref(attributes),
            c.byref(status), None, 0, 1, 2 if create else 1, options, None, 0)
    if code < 0:
        error = int(native.RtlNtStatusToDosError(code))
        if error in {80, 183}:
            raise FileExistsError("F02_RESERVATION_ALREADY_EXISTS")
        if error in {2, 3}:
            raise ValueError("INPUT_FILE_REJECTED")
        raise OSError("F02_OPEN_REJECTED")
    if result.value is None:
        raise OSError("F02_INVALID_HANDLE")
    handle = _checked(result.value, kernel, directory=directory)
    # NtCreateFile resolved one validated component relative to the pinned parent.
    # Compare the final parent, allowing Windows to expand legitimate 8.3 names.
    if Path(handle.final_name).parent != Path(parent.final_name):
        handle.close()
        raise ValueError("F02_FINAL_PATH_MISMATCH")
    handle.chain_identity = (*parent.chain_identity, handle.identity)
    return handle


def pin_directory(path: Path, stack: ExitStack) -> Handle:
    anchor, parts = _parts(path)
    kernel, _ = _api()
    raw = kernel.CreateFileW(anchor, 0x1000A0, 1, None, 3, 0x02200000, None)
    if raw == c.c_void_p(-1).value:
        raise OSError("F02_HANDLE_OPERATION_FAILED")
    current = _checked(raw, kernel, directory=True)
    stack.callback(current.close)
    if current.final_name.casefold() != ("\\\\?\\" + anchor).casefold():
        raise ValueError("F02_LOCAL_VOLUME_REQUIRED")
    current.chain_identity = (current.identity,)
    for part in parts:
        current = _child(current, part, directory=True)
        stack.callback(current.close)
    return current


def directory_identity(path: Path) -> tuple[tuple[int, bytes], ...]:
    with ExitStack() as stack:
        return pin_directory(path, stack).chain_identity


def read_private(path: Path, *, maximum_bytes: int) -> bytes:
    _parts(path)
    if maximum_bytes < 0:
        raise ValueError("F02_SIZE_REJECTED")
    with ExitStack() as stack:
        parent = pin_directory(path.parent, stack)
        handle = _child(parent, path.name, directory=False)
        stack.callback(handle.close)
        buffer = c.create_string_buffer(maximum_bytes + 1)
        count = w.DWORD()
        if not handle.kernel.ReadFile(handle.raw, buffer, len(buffer), c.byref(count), None):
            raise OSError("F02_HANDLE_OPERATION_FAILED")
        if count.value > maximum_bytes:
            raise ValueError("INPUT_FILE_TOO_LARGE")
        return buffer.raw[:count.value]


_ACTIVE: ContextVar[Reservation | None] = ContextVar("f02_active_reservation", default=None)


class Reservation:
    """Atomically create and pin the namespace; retain each written file handle."""

    def __init__(self, directory: Path, allowed_root: Path,
                 expected_parent: tuple[tuple[int, bytes], ...]) -> None:
        _parts(directory)
        _parts(allowed_root)
        if directory == allowed_root or not directory.is_relative_to(allowed_root):
            raise ValueError("PRIVATE_PATH_BOUNDARY_REJECTED")
        self.directory = directory
        self.expected_parent = expected_parent
        self.stack = ExitStack()

    def __enter__(self) -> Reservation:
        try:
            parent = pin_directory(self.directory.parent, self.stack)
            if parent.chain_identity != self.expected_parent:
                raise ValueError("F02_ROOT_IDENTITY_CHANGED")
            self.handle = _child(parent, self.directory.name, directory=True, create=True)
            self.stack.callback(self.handle.close)
            self.token = _ACTIVE.set(self)
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args: object) -> None:
        _ACTIVE.reset(self.token)
        self.stack.close()

    def write(self, name: str, raw: bytes) -> None:
        handle = _child(self.handle, name, directory=False, create=True, write=True)
        self.stack.callback(handle.close)
        written = w.DWORD()
        if not handle.kernel.WriteFile(handle.raw, raw, len(raw), c.byref(written), None):
            raise OSError("F02_HANDLE_OPERATION_FAILED")
        if written.value != len(raw) or not handle.kernel.FlushFileBuffers(handle.raw):
            raise OSError("F02_DURABLE_WRITE_FAILED")


def write_reserved(directory: Path, name: str, raw: bytes) -> None:
    active = _ACTIVE.get()
    if active is None or active.directory != directory:
        raise ValueError("F02_PINNED_RESERVATION_REQUIRED")
    active.write(name, raw)
