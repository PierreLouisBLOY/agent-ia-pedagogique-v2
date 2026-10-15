"""Native readonly proof scopes for V2 only; no reusable cross-operation cache."""

from __future__ import annotations

import ctypes
import hashlib
import os
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
    RejectedReadPhaseKind,
)

MAX_READ_FILES = 4096
MAX_HASH_BYTES = 128_000_000


class _FileId(ctypes.Structure):
    _fields_ = [("volume", ctypes.c_uint64), ("file_id", ctypes.c_ubyte * 16)]


class _Attributes(ctypes.Structure):
    _fields_ = [("attributes", ctypes.c_uint32), ("tag", ctypes.c_uint32)]


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("internal", ctypes.c_size_t),
        ("internal_high", ctypes.c_size_t),
        ("offset", ctypes.c_uint32),
        ("offset_high", ctypes.c_uint32),
        ("event", ctypes.c_void_p),
    ]


class _Request(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_uint16),
        ("length", ctypes.c_uint16),
        ("level", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class _Output(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_uint16),
        ("length", ctypes.c_uint16),
        ("original", ctypes.c_uint32),
        ("new", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("access", ctypes.c_uint32),
        ("share", ctypes.c_uint16),
    ]


class _Windows:
    def __init__(self) -> None:
        if os.name != "nt":
            raise ValueError("P0_READSET_WINDOWS_REQUIRED")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.create = self.kernel.CreateFileW
        self.create.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        )
        self.create.restype = ctypes.c_void_p
        self.close = self.kernel.CloseHandle
        self.close.argtypes, self.close.restype = (ctypes.c_void_p,), ctypes.c_int
        self.info = self.kernel.GetFileInformationByHandleEx
        self.info.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
        self.info.restype = ctypes.c_int
        self.event = self.kernel.CreateEventW
        self.event.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p)
        self.event.restype = ctypes.c_void_p
        self.wait = self.kernel.WaitForSingleObject
        self.wait.argtypes, self.wait.restype = (ctypes.c_void_p, ctypes.c_uint32), ctypes.c_uint32
        self.io = self.kernel.DeviceIoControl
        self.io.argtypes = (
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        self.io.restype = ctypes.c_int
        self.cancel = self.kernel.CancelIoEx
        self.cancel.argtypes, self.cancel.restype = (ctypes.c_void_p, ctypes.c_void_p), ctypes.c_int
        self.result = self.kernel.GetOverlappedResult
        self.result.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
        self.result.restype = ctypes.c_int
        self.size = self.kernel.GetFileSizeEx
        self.size.argtypes, self.size.restype = (ctypes.c_void_p, ctypes.c_void_p), ctypes.c_int
        self.read = self.kernel.ReadFile
        self.read.argtypes = (
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        self.read.restype = ctypes.c_int

    def open(self, path: Path, *, directory: bool, asynchronous: bool = False) -> int:
        flags = 0x00200000 | (0x02000000 if directory else 0)
        flags |= 0x40000000 if asynchronous else 0
        access = 0x80000000 if asynchronous else 0x80
        share = 3 if directory else (1 if asynchronous else 7)
        handle = self.create(str(path), access, share, None, 3, flags, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise ValueError("P0_READSET_NATIVE_OPEN_REFUSED")
        return cast(int, handle)

    def identify(self, handle: int, *, directory: bool) -> tuple[int, int, int]:
        identity, attrs = _FileId(), _Attributes()
        if (
            not self.info(handle, 18, ctypes.byref(identity), ctypes.sizeof(identity))
            or not self.info(handle, 9, ctypes.byref(attrs), ctypes.sizeof(attrs))
            or attrs.attributes & 0x400
            or bool(attrs.attributes & 0x10) is not directory
        ):
            raise ValueError("P0_READSET_NATIVE_IDENTITY_OR_REPARSE")
        return identity.volume, int.from_bytes(bytes(identity.file_id), "little"), attrs.attributes

    def path_identity(self, path: Path, *, directory: bool) -> tuple[int, int, int]:
        handle = self.open(path, directory=directory)
        try:
            return self.identify(handle, directory=directory)
        finally:
            self.close(handle)


@dataclass
class _ReadIO:
    overlapped: _Overlapped
    event: int
    buffer: ctypes.Array[ctypes.c_char]
    pending: bool = False


@dataclass
class _Member:
    path: Path
    handle: int
    identity: tuple[int, int, int]
    overlapped: _Overlapped
    output: _Output
    event: int
    pending: bool = False
    read_io: _ReadIO | None = None


class WindowsImmutableReadSet:
    """Read share barriers plus READ oplocks, never directory write blocking."""

    def __init__(
        self, files: Mapping[Path, tuple[Path, str]], *, mutable_directories: Sequence[Path] = ()
    ) -> None:
        if not files or len(files) > MAX_READ_FILES:
            raise ValueError("P0_READSET_FILE_BOUND")
        self.files = dict(files)
        self.mutable_directories = set(mutable_directories)
        self.native = _Windows()
        self.members: list[_Member] = []
        self.parents: dict[Path, tuple[int | None, tuple[int, int, int]]] = {}
        self.active = False
        self.cleanup_unconfirmed = False

    def acquire(self) -> None:
        if self.active or self.members or self.parents:
            raise ValueError("P0_READSET_REUSE_REFUSED")
        try:
            all_parents = {parent for path in self.files for parent in path.parents}
            for path in sorted(all_parents, key=lambda item: len(item.parts)):
                identity = self.native.path_identity(path, directory=True)
                handle = (
                    None
                    if path in self.mutable_directories
                    else self.native.open(path, directory=True)
                )
                if handle is not None and self.native.identify(handle, directory=True) != identity:
                    self.native.close(handle)
                    raise ValueError("P0_READSET_PARENT_CHANGED")
                self.parents[path] = (handle, identity)
            for path, (root, expected) in self.files.items():
                if (
                    not path.is_absolute()
                    or not root.is_absolute()
                    or not path.is_relative_to(root)
                ):
                    raise ValueError("P0_READSET_OUTSIDE_ADOPTED_ROOT")
                identity = self.native.path_identity(path, directory=False)
                handle = self.native.open(path, directory=False, asynchronous=True)
                event = self.native.event(None, True, False, None)
                if not event:
                    self.native.close(handle)
                    raise ValueError("P0_READSET_EVENT_REFUSED")
                member = _Member(
                    path, handle, identity, _Overlapped(event=event), _Output(), cast(int, event)
                )
                self.members.append(member)
                if self.native.identify(handle, directory=False) != identity:
                    raise ValueError("P0_READSET_FILE_CHANGED")
                request = _Request(1, ctypes.sizeof(_Request), 1, 1)
                # Own the possibly pending IRP before ctypes can release the GIL.
                member.pending = True
                accepted = self.native.io(
                    handle,
                    0x00090240,
                    ctypes.byref(request),
                    ctypes.sizeof(request),
                    ctypes.byref(member.output),
                    ctypes.sizeof(member.output),
                    None,
                    ctypes.byref(member.overlapped),
                )
                error = ctypes.get_last_error()
                if accepted or error != 997:
                    member.pending = False
                    raise ValueError("P0_READSET_READ_OPLOCK_NOT_GRANTED")
                if self.native.wait(event, 0) != 258:
                    raise ValueError("P0_READSET_READ_OPLOCK_BROKEN")
                if self._hash_retained(member) != expected:
                    raise ValueError("P0_READSET_PIN_CHANGED")
            self.active = True
            self.require_intact()
        except BaseException:
            self.close()
            raise

    def _hash_retained(self, member: _Member) -> str:
        """Hash only this retained handle, with independent async read ownership."""
        size = ctypes.c_int64()
        if (
            not self.native.size(member.handle, ctypes.byref(size))
            or not 0 <= size.value <= MAX_HASH_BYTES
        ):
            raise ValueError("P0_READSET_HASH_SIZE_BOUND")
        digest, offset = hashlib.sha256(), 0
        while offset < size.value:
            count = min(size.value - offset, 1024 * 1024)
            event = self.native.event(None, True, False, None)
            if not event:
                raise ValueError("P0_READSET_READ_EVENT_REFUSED")
            read_io = _ReadIO(
                _Overlapped(
                    offset=offset & 0xFFFFFFFF,
                    offset_high=offset >> 32,
                    event=event,
                ),
                cast(int, event),
                ctypes.create_string_buffer(count),
            )
            member.read_io = read_io
            read_io.pending = True
            accepted = self.native.read(
                member.handle,
                read_io.buffer,
                count,
                None,
                ctypes.byref(read_io.overlapped),
            )
            if not accepted and ctypes.get_last_error() != 997:
                read_io.pending = False
                raise ValueError("P0_READSET_RETAINED_READ_REFUSED")
            if self.native.wait(read_io.event, 5000) != 0:
                raise ValueError("P0_READSET_RETAINED_READ_TIMEOUT")
            transferred = ctypes.c_uint32()
            if not self.native.result(
                member.handle,
                ctypes.byref(read_io.overlapped),
                ctypes.byref(transferred),
                False,
            ):
                raise ValueError("P0_READSET_RETAINED_READ_INCOMPLETE")
            read_io.pending = False
            if transferred.value != count:
                raise ValueError("P0_READSET_RETAINED_READ_SHORT")
            digest.update(read_io.buffer.raw[:count])
            if not self.native.close(read_io.event):
                raise ValueError("P0_READSET_READ_EVENT_CLOSE_UNCONFIRMED")
            member.read_io = None
            offset += count
        after = ctypes.c_int64()
        if not self.native.size(member.handle, ctypes.byref(after)) or after.value != size.value:
            raise ValueError("P0_READSET_RETAINED_SIZE_CHANGED")
        return digest.hexdigest()

    def _cancelled(self, handle: int, overlapped: _Overlapped, event: int) -> bool:
        cancelled = self.native.cancel(handle, ctypes.byref(overlapped))
        if not cancelled and ctypes.get_last_error() != 1168:
            return False
        if self.native.wait(event, 5000) != 0:
            return False
        transferred = ctypes.c_uint32()
        completed = self.native.result(
            handle, ctypes.byref(overlapped), ctypes.byref(transferred), False
        )
        return bool(completed) or ctypes.get_last_error() in {995, 38}

    def require_intact(self) -> None:
        if not self.active or self.cleanup_unconfirmed:
            raise ValueError("P0_READSET_NOT_ACTIVE")
        for path, (handle, identity) in self.parents.items():
            if (
                handle is not None and self.native.identify(handle, directory=True) != identity
            ) or self.native.path_identity(path, directory=True) != identity:
                raise ValueError("P0_READSET_PARENT_CHANGED")
        for member in self.members:
            if (
                not member.pending
                or self.native.wait(member.event, 0) != 258
                or self.native.identify(member.handle, directory=False) != member.identity
                or self.native.path_identity(member.path, directory=False) != member.identity
            ):
                raise ValueError("P0_READSET_BROKEN_OR_PATH_CHANGED")

    def close(self) -> None:
        self.active = False
        failed = False
        for member in reversed(self.members):
            read_io = member.read_io
            if read_io is not None:
                if read_io.pending and not self._cancelled(
                    member.handle, read_io.overlapped, read_io.event
                ):
                    failed = True
                    continue
                read_io.pending = False
                if not self.native.close(read_io.event):
                    failed = True
                    continue
                member.read_io = None
            if member.pending:
                if not self._cancelled(member.handle, member.overlapped, member.event):
                    failed = True
                    continue
                member.pending = False
            if member.handle:
                self.native.close(member.handle)
                member.handle = 0
            if member.event:
                self.native.close(member.event)
                member.event = 0
        for path, (handle, identity) in list(self.parents.items()):
            if handle:
                self.native.close(handle)
            self.parents[path] = (None, identity)
        self.cleanup_unconfirmed = failed
        if failed:
            # Keep the IRP/OVERLAPPED/events alive on the composed owner. Never
            # announce CLOSED or accept another phase with an unconfirmed close.
            raise ValueError("P0_READSET_ASYNC_TERMINATION_UNCONFIRMED")
        self.members.clear()
        self.parents.clear()


class NativeP0RejectedReadPhases:
    """An invocation-local proof whose owner must already hold the native LOCK."""

    def __init__(
        self,
        *,
        lock_scope: Callable[[], object],
        collect: Callable[[], Mapping[Path, tuple[Path, str]]],
        full_chain: Callable[[], BoundChainV2],
        fresh: Callable[[BoundChainV2], None],
        mutable_directories: Sequence[Path] = (),
    ) -> None:
        self.lock_scope, self.collect, self.full_chain, self.fresh = (
            lock_scope,
            collect,
            full_chain,
            fresh,
        )
        self.mutable_directories = mutable_directories
        self._lease: WindowsImmutableReadSet | None = None
        self._proof: BoundChainV2 | None = None
        self._scope: object | None = None
        self._thread: int | None = None
        self.poisoned = False
        self.full_checks = self.proof_reuses = 0

    @contextmanager
    def phase(self, kind: RejectedReadPhaseKind) -> Iterator[None]:
        if (
            kind not in {"PREVIEW", "ACCEPT", "GENERATE"}
            or self._lease is not None
            or self.poisoned
        ):
            raise ValueError("P0_READSET_SCOPE_REFUSED")
        scope = self.lock_scope()
        lease = WindowsImmutableReadSet(
            self.collect(), mutable_directories=self.mutable_directories
        )
        self._lease, self._scope, self._thread = lease, scope, threading.get_ident()
        try:
            lease.acquire()
            self._proof = self.full_chain()
            self.full_checks += 1
            self.require_proof()
            yield
        finally:
            self._proof, self._scope, self._thread = None, None, None
            try:
                lease.close()
            except BaseException:
                self.poisoned = True
                raise
            else:
                self._lease = None

    def require_proof(self) -> BoundChainV2:
        if (
            self.poisoned
            or self._lease is None
            or self._proof is None
            or self._thread != threading.get_ident()
            or self.lock_scope() != self._scope
        ):
            raise ValueError("P0_READSET_PROOF_SCOPE_REFUSED")
        self._lease.require_intact()
        self.fresh(self._proof)
        self.proof_reuses += 1
        return self._proof

    @property
    def has_proof(self) -> bool:
        return self._proof is not None

    @property
    def protected_paths(self) -> tuple[Path, ...]:
        if self._lease is None or self._proof is None:
            raise ValueError("P0_READSET_PROOF_SCOPE_REFUSED")
        return tuple(self._lease.files)

    def close(self) -> None:
        if self._lease is not None:
            self._proof = None
            self._lease.close()
            self._lease = None
        self.poisoned = False
