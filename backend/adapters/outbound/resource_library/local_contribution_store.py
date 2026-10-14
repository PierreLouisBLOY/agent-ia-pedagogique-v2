"""Private Windows overlay: exclusive immutable publications, stages retained."""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any

from backend.infrastructure.filesystem import (
    capture_secure_path,
    ensure_private_directory,
    private_temporary_file,
    read_file_nofollow,
)
from backend.infrastructure.filesystem.security import LocalFileSecurityError
from backend.modules.documents_provenance.contracts.dto.local_contribution_provenance import digest
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    encoded,
    fingerprint,
    object_data,
)
from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionRead,
    LocalContributionRecord,
)
from backend.modules.resource_library.ports.outbound.local_contribution_store import (
    LocalContributionPersistenceError,
)

_ROOT = Path(__file__).resolve().parents[4]
_FOLDERS = ("intents", "staging", "versions", "commits")


def native_operator() -> dict[str, str]:
    if sys.platform != "win32":
        raise ValueError("LOCAL_CONTRIBUTION_WINDOWS_REQUIRED")
    kernel, advapi, userenv = (ctypes.WinDLL(name, use_last_error=True) for name in ("kernel32", "advapi32", "userenv"))
    process = kernel.GetCurrentProcess
    process.restype = ctypes.c_void_p
    open_token = advapi.OpenProcessToken
    open_token.argtypes, open_token.restype = (ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)), ctypes.c_int
    handle = ctypes.c_void_p()
    if not open_token(process(), 8, ctypes.byref(handle)):
        raise ValueError("LOCAL_CONTRIBUTION_OPERATOR")
    close = kernel.CloseHandle
    close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
    info = advapi.GetTokenInformation
    info.argtypes, info.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int
    try:
        length = ctypes.c_uint32()
        elevation = ctypes.c_uint32()
        if not info(handle, 20, ctypes.byref(elevation), ctypes.sizeof(elevation), ctypes.byref(length)) or elevation.value:
            raise ValueError("LOCAL_CONTRIBUTION_NORMAL_CONTEXT_REQUIRED")
        info(handle, 1, None, 0, ctypes.byref(length))
        buffer = ctypes.create_string_buffer(length.value)
        if not info(handle, 1, buffer, length.value, ctypes.byref(length)):
            raise ValueError("LOCAL_CONTRIBUTION_OPERATOR")
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        convert = advapi.ConvertSidToStringSidW
        convert.argtypes, convert.restype = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.c_int
        text = ctypes.c_void_p()
        if not convert(sid, ctypes.byref(text)):
            raise ValueError("LOCAL_CONTRIBUTION_OPERATOR")
        free = kernel.LocalFree
        free.argtypes, free.restype = (ctypes.c_void_p,), ctypes.c_void_p
        try:
            sid_text = ctypes.wstring_at(text)
        finally:
            free(text)
        profile = userenv.GetUserProfileDirectoryW
        profile.argtypes, profile.restype = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int
        length = ctypes.c_uint32()
        profile(handle, None, ctypes.byref(length))
        path = ctypes.create_unicode_buffer(length.value)
        if not profile(handle, path, ctypes.byref(length)):
            raise ValueError("LOCAL_CONTRIBUTION_OPERATOR")
        return {"windows_sid": sid_text, "windows_profile": path.value}
    finally:
        close(handle)


def _owner_only(path: Path, sid: str) -> None:
    """Effective owner/DACL/protection/ACE inspection, not a conventional status."""
    advapi, kernel = (ctypes.WinDLL(name, use_last_error=True) for name in ("advapi32", "kernel32"))
    descriptor, owner, acl = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    get = advapi.GetNamedSecurityInfoW
    get.argtypes, get.restype = (ctypes.c_wchar_p, ctypes.c_int, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)), ctypes.c_uint32
    convert = advapi.ConvertSidToStringSidW
    convert.argtypes, convert.restype = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.c_int
    free = kernel.LocalFree
    free.argtypes, free.restype = (ctypes.c_void_p,), ctypes.c_void_p
    def sid_string(pointer: Any) -> str:
        result = ctypes.c_void_p()
        if not convert(pointer, ctypes.byref(result)):
            raise ValueError("LOCAL_CONTRIBUTION_DACL")
        try:
            return ctypes.wstring_at(result)
        finally:
            free(result)
    class ACLSize(ctypes.Structure):
        _fields_ = [("count", ctypes.c_uint32), ("used", ctypes.c_uint32), ("free", ctypes.c_uint32)]
    try:
        if get(str(path), 1, 5, ctypes.byref(owner), None, ctypes.byref(acl), None, ctypes.byref(descriptor)) or not acl.value:
            raise ValueError("LOCAL_CONTRIBUTION_DACL")
        if sid_string(owner) != sid:
            raise ValueError("LOCAL_CONTRIBUTION_OWNER")
        control, revision = ctypes.c_uint16(), ctypes.c_uint32()
        get_control = advapi.GetSecurityDescriptorControl
        get_control.argtypes, get_control.restype = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int
        if not get_control(descriptor, ctypes.byref(control), ctypes.byref(revision)) or not control.value & 0x1000:
            raise ValueError("LOCAL_CONTRIBUTION_DACL_PROTECTION")
        size = ACLSize()
        get_info = advapi.GetAclInformation
        get_info.argtypes, get_info.restype = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int), ctypes.c_int
        if not get_info(acl, ctypes.byref(size), ctypes.sizeof(size), 2) or size.count != 1:
            raise ValueError("LOCAL_CONTRIBUTION_DACL")
        ace = ctypes.c_void_p()
        get_ace = advapi.GetAce
        get_ace.argtypes, get_ace.restype = (ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)), ctypes.c_int
        if not get_ace(acl, 0, ctypes.byref(ace)) or not ace.value:
            raise ValueError("LOCAL_CONTRIBUTION_DACL")
        header = ctypes.string_at(ace, 8)
        if header[0] != 0 or header[1] & 0x10 or int.from_bytes(header[4:8], "little") != 0x1F01FF:
            raise ValueError("LOCAL_CONTRIBUTION_DACL")
        if sid_string(ctypes.c_void_p(ace.value + 8)) not in {"S-1-3-4", sid}:
            raise ValueError("LOCAL_CONTRIBUTION_DACL")
    finally:
        if descriptor.value:
            free(descriptor)


class _Information(ctypes.Structure):
    _fields_ = [("attributes", ctypes.c_uint32), ("creation_low", ctypes.c_uint32), ("creation_high", ctypes.c_uint32),
        ("access_low", ctypes.c_uint32), ("access_high", ctypes.c_uint32), ("write_low", ctypes.c_uint32),
        ("write_high", ctypes.c_uint32), ("volume", ctypes.c_uint32), ("size_high", ctypes.c_uint32),
        ("size_low", ctypes.c_uint32), ("links", ctypes.c_uint32), ("index_high", ctypes.c_uint32), ("index_low", ctypes.c_uint32)]


@contextmanager
def directory_lease(path: Path, *, allowed_root: Path) -> Iterator[tuple[int, int, int]]:
    capture_secure_path(path, allowed_root=allowed_root)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes, create.restype = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p), ctypes.c_void_p
    handle = create(str(path), 0x81, 3, None, 3, 0x02200000, None)  # LIST_DIRECTORY + READ_ATTRIBUTES; no SHARE_DELETE
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ValueError("LOCAL_CONTRIBUTION_DIRECTORY_LEASE")
    close = kernel.CloseHandle
    close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
    get = kernel.GetFileInformationByHandle
    get.argtypes, get.restype = (ctypes.c_void_p, ctypes.POINTER(_Information)), ctypes.c_int
    try:
        info = _Information()
        if not get(handle, ctypes.byref(info)) or not info.attributes & 0x10 or info.attributes & 0x400:
            raise ValueError("LOCAL_CONTRIBUTION_DIRECTORY_LEASE")
        before = (info.volume, info.index_high, info.index_low)
        yield before
        if not get(handle, ctypes.byref(info)) or (info.volume, info.index_high, info.index_low) != before:
            raise ValueError("LOCAL_CONTRIBUTION_DIRECTORY_CHANGED")
    finally:
        close(handle)


@dataclass(frozen=True, slots=True)
class LocalContributionTarget:
    root: Path
    parent_identity: tuple[int | None, int | None]
    operator_profile_sha256: str

    @classmethod
    def prepare(cls, root: Path) -> LocalContributionTarget:
        if (not root.is_absolute() or root == Path(root.anchor) or root == _ROOT or _ROOT in root.parents
                or str(root).startswith("\\\\")):
            raise ValueError("LOCAL_CONTRIBUTION_TARGET")
        parent = capture_secure_path(root.parent, allowed_root=root.parent)
        if not parent.is_directory:
            raise ValueError("LOCAL_CONTRIBUTION_PARENT_REQUIRED")
        capture_secure_path(root, allowed_root=root.parent)
        return cls(root, (parent.device, parent.inode), fingerprint(native_operator()))

    @property
    def sha256(self) -> str:
        return fingerprint({"root": os.path.normcase(str(self.root)), "parent_identity": self.parent_identity,
            "operator_profile_sha256": self.operator_profile_sha256})


class LocalContributionFileStore:
    def __init__(self, target: LocalContributionTarget, *, binding_sha256: str) -> None:
        self.target, self.binding_sha256 = target, digest(binding_sha256)
        self._mutex = threading.RLock()
        self._local = threading.local()
        self._root_identity: tuple[int, int, int] | None = None

    def attest(self) -> Mapping[str, object]:
        operator = native_operator()
        if fingerprint(operator) != self.target.operator_profile_sha256:
            raise ValueError("LOCAL_CONTRIBUTION_OPERATOR_CHANGED")
        parent = capture_secure_path(self.target.root.parent, allowed_root=self.target.root.parent)
        if not parent.is_directory or (parent.device, parent.inode) != self.target.parent_identity:
            raise ValueError("LOCAL_CONTRIBUTION_PARENT_CHANGED")
        capture_secure_path(self.target.root, allowed_root=self.target.root.parent)
        return {"target_ref": "local-target:" + self.target.sha256, "target_binding_sha256": self.target.sha256,
            "operator_profile_sha256": self.target.operator_profile_sha256, "binding_sha256": self.binding_sha256}

    def _json(self, path: Path) -> dict[str, object]:
        raw = read_file_nofollow(path, allowed_root=self.target.root, maximum_bytes=65536)
        _owner_only(path, native_operator()["windows_sid"])
        def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("LOCAL_CONTRIBUTION_DUPLICATE_FIELD")
                result[key] = value
            return result
        def nonfinite(_: str) -> None:
            raise ValueError("LOCAL_CONTRIBUTION_NONFINITE")
        data = object_data(json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite))
        if encoded(data) != raw:
            raise ValueError("LOCAL_CONTRIBUTION_NONCANONICAL_RECORD")
        return data

    def _fresh(self, destination: Path, value: Mapping[str, object]) -> None:
        raw = encoded(value)
        if len(raw) > 65536:
            raise ValueError("LOCAL_CONTRIBUTION_FILE_TOO_LARGE")
        stage = private_temporary_file(self.target.root / "staging", allowed_root=self.target.root,
            prefix="contribution-", suffix=".pending")
        before = capture_secure_path(stage, allowed_root=self.target.root)
        descriptor = os.open(stage, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != (before.device, before.inode):
                raise ValueError("LOCAL_CONTRIBUTION_STAGE_CHANGED")
            position = 0
            while position < len(raw):
                count = os.write(descriptor, raw[position:])
                if count <= 0:
                    raise ValueError("LOCAL_CONTRIBUTION_STAGE_WRITE")
                position += count
            os.fsync(descriptor)
            _owner_only(stage, native_operator()["windows_sid"])
            if capture_secure_path(destination, allowed_root=self.target.root).exists:
                raise ValueError("LOCAL_CONTRIBUTION_DESTINATION_EXISTS")
            os.link(stage, destination)  # exclusive publication; retain both names
            published = capture_secure_path(destination, allowed_root=self.target.root)
            if (published.device, published.inode) != (info.st_dev, info.st_ino):
                raise ValueError("LOCAL_CONTRIBUTION_PUBLISH_IDENTITY")
            if read_file_nofollow(destination, allowed_root=self.target.root, maximum_bytes=65536) != raw:
                raise ValueError("LOCAL_CONTRIBUTION_READBACK")
        finally:
            os.close(descriptor)

    def _initialise(self) -> None:
        root = self.target.root
        if capture_secure_path(root, allowed_root=root.parent).exists:
            return
        root.mkdir(parents=False, exist_ok=False)
        with directory_lease(root, allowed_root=root.parent) as identity:
            ensure_private_directory(root, allowed_root=root.parent)
            for name in _FOLDERS:
                child = root / name
                child.mkdir(parents=False, exist_ok=False)
                with directory_lease(child, allowed_root=root):
                    ensure_private_directory(child, allowed_root=root)
            with (root / "writer.lock").open("xb") as stream:
                stream.write(b"0")
                stream.flush()
                os.fsync(stream.fileno())
            from backend.infrastructure.filesystem.security import harden_private_file
            harden_private_file(root / "writer.lock", allowed_root=root)
            with directory_lease(root / "staging", allowed_root=root):
                self._fresh(root / "OVERLAY", {"schema": "LOCAL-CONTRIBUTION-ROOT-1.0",
                    "binding_sha256": self.binding_sha256, "target_sha256": self.target.sha256,
                    "root_identity": list(identity)})

    @contextmanager
    def session(self, *, create: bool = False) -> Iterator[None]:
        if type(create) is not bool:
            raise ValueError("LOCAL_CONTRIBUTION_CREATE_BOOL")
        with self._mutex, directory_lease(self.target.root.parent, allowed_root=self.target.root.parent):
            self.attest()
            footprint = False
            self._local.mutated = False
            try:
                if create:
                    footprint = not capture_secure_path(self.target.root, allowed_root=self.target.root.parent).exists
                    self._initialise()
                with directory_lease(self.target.root, allowed_root=self.target.root.parent) as root_identity:
                    marker = object_data(self._json(self.target.root / "OVERLAY"), {"schema", "binding_sha256", "target_sha256", "root_identity"})
                    if (marker["schema"] != "LOCAL-CONTRIBUTION-ROOT-1.0" or marker["binding_sha256"] != self.binding_sha256
                            or marker["target_sha256"] != self.target.sha256 or marker["root_identity"] != list(root_identity)
                            or self._root_identity not in (None, root_identity)):
                        raise ValueError("LOCAL_CONTRIBUTION_ROOT_CHANGED")
                    self._root_identity = root_identity
                    _owner_only(self.target.root, native_operator()["windows_sid"])
                    from contextlib import ExitStack
                    with ExitStack() as stack:
                        for name in _FOLDERS:
                            path = self.target.root / name
                            stack.enter_context(directory_lease(path, allowed_root=self.target.root))
                            _owner_only(path, native_operator()["windows_sid"])
                        lock_path = self.target.root / "writer.lock"
                        before = capture_secure_path(lock_path, allowed_root=self.target.root)
                        _owner_only(lock_path, native_operator()["windows_sid"])
                        fd = os.open(lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
                        try:
                            info = os.fstat(fd)
                            if (info.st_dev, info.st_ino) != (before.device, before.inode):
                                raise ValueError("LOCAL_CONTRIBUTION_LOCK_CHANGED")
                            import msvcrt
                            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                            self._local.active = True
                            yield
                            self.attest()
                        finally:
                            self._local.active = False
                            os.close(fd)
            except LocalContributionPersistenceError:
                raise
            except (OSError, ValueError, LocalFileSecurityError) as error:
                raise LocalContributionPersistenceError("LOCAL_CONTRIBUTION_SESSION_FAILED",
                    uncertain=footprint or bool(getattr(self._local, "mutated", False))) from error

    def _require_session(self) -> None:
        if not getattr(self._local, "active", False):
            raise ValueError("LOCAL_CONTRIBUTION_SESSION_REQUIRED")

    def _inventory(self, publications: tuple[Path, ...]) -> bool:
        root = self.target.root
        if {p.name for p in islice(root.iterdir(), 7)} != {"OVERLAY", "writer.lock", *_FOLDERS}:
            return False
        stages = tuple(islice((root / "staging").iterdir(), len(publications) + 1))
        if len(stages) != len(publications):
            return False
        snapshots = [capture_secure_path(path, allowed_root=root) for path in publications]
        observed = [capture_secure_path(path, allowed_root=root) for path in stages]
        if any(not p.exists or not p.is_file for p in (*snapshots, *observed)):
            return False
        return all(sum(stage.same_identity(final) for stage in observed) == 1 for final in snapshots)

    def inspect_operation(self, operation_key: str, binding_sha256: str) -> Mapping[str, object]:
        self._require_session()
        key, binding = digest(operation_key), digest(binding_sha256)
        if binding != self.binding_sha256:
            raise ValueError("LOCAL_CONTRIBUTION_BINDING_CHANGED")
        root = self.target.root
        entries = tuple(islice((root / "intents").iterdir(), 2))
        if len(entries) > 1:
            return {"state": "UNKNOWN"}
        if not entries:
            if (next((root / "versions").iterdir(), None) is not None or next((root / "commits").iterdir(), None) is not None
                    or not self._inventory((root / "OVERLAY",))):
                return {"state": "UNKNOWN"}
            return {"state": "ABSENT"}
        if entries[0].name != key + ".json":
            return {"state": "UNKNOWN"}
        commit_path = root / "commits" / (key + ".json")
        if not capture_secure_path(commit_path, allowed_root=root).exists:
            return {"state": "UNKNOWN"}
        intent = object_data(self._json(entries[0]), {"contract_id", "operation_key", "binding_sha256", "record_sha256", "record"})
        commit = object_data(self._json(commit_path), {"schema", "operation_key", "binding_sha256", "intent_sha256", "record_sha256", "record_name"})
        if (intent["contract_id"] != "LOCAL-CONTRIBUTION-INTENT-1.0" or intent["operation_key"] != key
                or intent["binding_sha256"] != binding or commit["schema"] != "LOCAL-CONTRIBUTION-COMMIT-1.0"
                or commit["operation_key"] != key or commit["binding_sha256"] != binding
                or commit["intent_sha256"] != fingerprint(intent) or commit["record_sha256"] != intent["record_sha256"]):
            raise ValueError("LOCAL_CONTRIBUTION_COMMIT_CHANGED")
        record = LocalContributionRecord(object_data(intent["record"]))
        name = str(record.data["object_ref"]).split(":")[1] + "-" + str(record.data["version_ref"]).split(":")[1] + ".json"
        if commit["record_name"] != name or record.sha256 != intent["record_sha256"]:
            raise ValueError("LOCAL_CONTRIBUTION_RECORD_CHANGED")
        observed = LocalContributionRecord(self._json(root / "versions" / name))
        if observed.sha256 != record.sha256 or record.data["operation_key"] != key or record.data["binding_sha256"] != binding:
            raise ValueError("LOCAL_CONTRIBUTION_RECORD_CHANGED")
        if (tuple(islice((root / "versions").iterdir(), 2)) != (root / "versions" / name,)
                or tuple(islice((root / "commits").iterdir(), 2)) != (commit_path,)
                or not self._inventory((root / "OVERLAY", entries[0], root / "versions" / name, commit_path))):
            return {"state": "UNKNOWN"}
        return {"state": "COMMITTED", "record": record.as_dict(), "record_sha256": record.sha256}

    def append(self, record: LocalContributionRecord, intention: Mapping[str, object]) -> LocalContributionRecord:
        self._require_session()
        key = digest(record.data["operation_key"])
        footprint = False
        try:
            if (record.data["binding_sha256"] != self.binding_sha256 or record.data["target_binding_sha256"] != self.target.sha256
                    or intention.get("record_sha256") != record.sha256 or intention.get("record") != record.as_dict()
                    or self.inspect_operation(key, self.binding_sha256)["state"] != "ABSENT"):
                raise ValueError("LOCAL_CONTRIBUTION_RECONCILE_REQUIRED")
            footprint = True
            self._local.mutated = True
            self._fresh(self.target.root / "intents" / (key + ".json"), intention)
            name = str(record.data["object_ref"]).split(":")[1] + "-" + str(record.data["version_ref"]).split(":")[1] + ".json"
            self._fresh(self.target.root / "versions" / name, record.as_dict())
            self._fresh(self.target.root / "commits" / (key + ".json"), {"schema": "LOCAL-CONTRIBUTION-COMMIT-1.0",
                "operation_key": key, "binding_sha256": self.binding_sha256,
                "intent_sha256": fingerprint(intention), "record_sha256": record.sha256, "record_name": name})
            outcome = self.inspect_operation(key, self.binding_sha256)
            if outcome["state"] != "COMMITTED":
                raise ValueError("LOCAL_CONTRIBUTION_COMMIT_UNKNOWN")
            return LocalContributionRecord(object_data(outcome["record"]))
        except (OSError, ValueError, LocalFileSecurityError) as error:
            raise LocalContributionPersistenceError("LOCAL_CONTRIBUTION_APPEND_FAILED", uncertain=footprint) from error

    def read_exact(self, request: LocalContributionRead) -> LocalContributionRecord:
        self._require_session()
        name = str(request.data["object_ref"]).split(":")[1] + "-" + str(request.data["version_ref"]).split(":")[1] + ".json"
        record = LocalContributionRecord(self._json(self.target.root / "versions" / name))
        if (record.sha256 != request.data["record_sha256"] or any(record.data[k] != request.data[k] for k in ("object_ref", "version_ref", "passage_ref"))
                or self.inspect_operation(str(record.data["operation_key"]), self.binding_sha256)["state"] != "COMMITTED"):
            raise ValueError("LOCAL_CONTRIBUTION_EXACT_READ_CHANGED")
        return record
