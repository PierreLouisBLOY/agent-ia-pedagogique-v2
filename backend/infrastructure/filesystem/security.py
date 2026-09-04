"""Fail-closed local path, permission, no-follow, and publication helpers."""

from __future__ import annotations

import ctypes
import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn


class LocalFileSecurityCode(StrEnum):
    RELATIVE_PATH = "RELATIVE_PATH"
    NETWORK_PATH = "NETWORK_PATH"
    NON_LOCAL_ROOT = "NON_LOCAL_ROOT"
    OUTSIDE_ALLOWED_ROOT = "OUTSIDE_ALLOWED_ROOT"
    PATH_RESOLUTION_FAILED = "PATH_RESOLUTION_FAILED"
    PATH_REDIRECTION_FORBIDDEN = "PATH_REDIRECTION_FORBIDDEN"
    PATH_CHANGED = "PATH_CHANGED"
    PATH_COLLISION = "PATH_COLLISION"
    FILE_REQUIRED = "FILE_REQUIRED"
    DESTINATION_EXISTS = "DESTINATION_EXISTS"
    PERMISSION_HARDENING_FAILED = "PERMISSION_HARDENING_FAILED"
    PERMISSION_EXCESSIVE = "PERMISSION_EXCESSIVE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    ATOMIC_PUBLICATION_FAILED = "ATOMIC_PUBLICATION_FAILED"


class LocalFileSecurityError(RuntimeError):
    """Redaction-safe local boundary error."""

    def __init__(self, code: LocalFileSecurityCode) -> None:
        if not isinstance(code, LocalFileSecurityCode):
            raise TypeError("code must be a LocalFileSecurityCode")
        self.code = code
        super().__init__(f"local filesystem boundary failed: {code.value}")


class PermissionStatus(StrEnum):
    PRIVATE_OWNER_ONLY = "PRIVATE_OWNER_ONLY"
    EXTERNAL_READABLE_RESTRICTED = "EXTERNAL_READABLE_RESTRICTED"
    EXCESSIVE_WRITE = "EXCESSIVE_WRITE"
    WINDOWS_DACL_PRESENT = "WINDOWS_DACL_PRESENT"


@dataclass(frozen=True, slots=True)
class PathSnapshot:
    """Internal physical identity snapshot; never crosses the sandbox port."""

    path: Path
    exists: bool
    is_file: bool
    is_directory: bool
    size_bytes: int
    modified_ns: int | None
    device: int | None
    inode: int | None
    token: str

    def same_identity(self, other: PathSnapshot) -> bool:
        if not isinstance(other, PathSnapshot):
            return False
        if self.exists is not other.exists:
            return False
        if not self.exists:
            return os.path.normcase(str(self.path)) == os.path.normcase(str(other.path))
        return (self.device, self.inode) == (other.device, other.inode)

    def same_state(self, other: PathSnapshot) -> bool:
        return self.same_identity(other) and self.token == other.token


def _raise(
    code: LocalFileSecurityCode, error: BaseException | None = None
) -> NoReturn:
    exception = LocalFileSecurityError(code)
    if error is None:
        raise exception
    raise exception from error


def _lexical_absolute(path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError("local paths must be pathlib.Path values")
    if not path.is_absolute():
        _raise(LocalFileSecurityCode.RELATIVE_PATH)
    rendered = str(path)
    if rendered.startswith(("\\\\", "//")):
        _raise(LocalFileSecurityCode.NETWORK_PATH)
    try:
        return Path(os.path.abspath(os.path.normpath(rendered)))
    except OSError as error:
        _raise(LocalFileSecurityCode.PATH_RESOLUTION_FAILED, error)


def _is_within(path: Path, root: Path) -> bool:
    try:
        common = os.path.commonpath((str(root), str(path)))
    except (OSError, ValueError) as error:
        _raise(LocalFileSecurityCode.PATH_RESOLUTION_FAILED, error)
    return os.path.normcase(common) == os.path.normcase(str(root))


def _is_redirection(file_stat: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return stat.S_ISLNK(file_stat.st_mode) or bool(attributes & reparse)


def _existing_components(path: Path) -> tuple[Path, ...]:
    anchor = Path(path.anchor)
    current = anchor
    components: list[Path] = [anchor]
    for part in path.parts[1:]:
        current /= part
        components.append(current)
    return tuple(components)


def _assert_no_redirection(path: Path) -> None:
    try:
        for component in _existing_components(path):
            if not os.path.lexists(component):
                continue
            if _is_redirection(os.lstat(component)):
                _raise(LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN)
    except LocalFileSecurityError:
        raise
    except OSError as error:
        _raise(LocalFileSecurityCode.PATH_RESOLUTION_FAILED, error)


def resolve_secure_path(path: Path, *, allowed_root: Path) -> Path:
    """Resolve an absolute path without accepting traversal or reparse components."""

    lexical_root = _lexical_absolute(allowed_root)
    lexical_path = _lexical_absolute(path)
    _assert_no_redirection(lexical_root)
    _assert_no_redirection(lexical_path)
    try:
        physical_root = lexical_root.resolve(strict=False)
        physical_path = lexical_path.resolve(strict=False)
    except OSError as error:
        _raise(LocalFileSecurityCode.PATH_RESOLUTION_FAILED, error)
    if not _is_within(physical_path, physical_root):
        _raise(LocalFileSecurityCode.OUTSIDE_ALLOWED_ROOT)
    _assert_no_redirection(lexical_path)
    return physical_path


def assert_local_data_root(path: Path) -> Path:
    """Accept only a local application-data root, never a sync/network locator."""

    root = _lexical_absolute(path)
    folded_parts = {part.casefold() for part in root.parts}
    if (
        root.drive.casefold() == "g:"
        or any("onedrive" in part for part in folded_parts)
        or "mon drive" in folded_parts
        or "google drive" in folded_parts
    ):
        _raise(LocalFileSecurityCode.NON_LOCAL_ROOT)
    if os.name == "nt" and root.drive:
        drive_type = int(ctypes.windll.kernel32.GetDriveTypeW(root.anchor))
        if drive_type != 3:  # DRIVE_FIXED
            _raise(LocalFileSecurityCode.NON_LOCAL_ROOT)
    _assert_no_redirection(root)
    return root.resolve(strict=False)


def _snapshot_token(path: Path, file_stat: os.stat_result | None) -> str:
    identity = "missing"
    if file_stat is not None:
        identity = (
            f"{file_stat.st_dev}:{file_stat.st_ino}:{file_stat.st_size}:"
            f"{file_stat.st_mtime_ns}"
        )
    payload = f"{os.path.normcase(str(path))}\0{identity}".encode()
    return hashlib.sha256(payload).hexdigest()


def capture_secure_path(path: Path, *, allowed_root: Path) -> PathSnapshot:
    resolved = resolve_secure_path(path, allowed_root=allowed_root)
    try:
        file_stat = os.lstat(resolved) if os.path.lexists(resolved) else None
    except OSError as error:
        _raise(LocalFileSecurityCode.PATH_RESOLUTION_FAILED, error)
    if file_stat is not None and _is_redirection(file_stat):
        _raise(LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN)
    return PathSnapshot(
        path=resolved,
        exists=file_stat is not None,
        is_file=file_stat is not None and stat.S_ISREG(file_stat.st_mode),
        is_directory=file_stat is not None and stat.S_ISDIR(file_stat.st_mode),
        size_bytes=0 if file_stat is None else file_stat.st_size,
        modified_ns=None if file_stat is None else file_stat.st_mtime_ns,
        device=None if file_stat is None else file_stat.st_dev,
        inode=None if file_stat is None else file_stat.st_ino,
        token=_snapshot_token(resolved, file_stat),
    )


def assert_distinct_paths(left: Path, right: Path) -> None:
    left_root = left.parent if left != left.parent else left
    right_root = right.parent if right != right.parent else right
    left_snapshot = capture_secure_path(left, allowed_root=left_root)
    right_snapshot = capture_secure_path(right, allowed_root=right_root)
    if os.path.normcase(str(left_snapshot.path)) == os.path.normcase(
        str(right_snapshot.path)
    ):
        _raise(LocalFileSecurityCode.PATH_COLLISION)
    if left_snapshot.exists and right_snapshot.exists:
        try:
            if os.path.samefile(left_snapshot.path, right_snapshot.path):
                _raise(LocalFileSecurityCode.PATH_COLLISION)
        except LocalFileSecurityError:
            raise
        except OSError as error:
            _raise(LocalFileSecurityCode.PATH_RESOLUTION_FAILED, error)


def _apply_windows_owner_dacl(path: Path, *, is_directory: bool) -> None:
    descriptor = ctypes.c_void_p()
    sddl = "D:P(A;OICI;FA;;;OW)" if is_directory else "D:P(A;;FA;;;OW)"
    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint32),
        )
        convert.restype = ctypes.c_int
        if not convert(sddl, 1, ctypes.byref(descriptor), None):
            _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED)
        set_security = advapi32.SetFileSecurityW
        set_security.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p)
        set_security.restype = ctypes.c_int
        security_information = 0x00000004 | 0x80000000
        if not set_security(str(path), security_information, descriptor):
            _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED)
        local_free = kernel32.LocalFree
        local_free.argtypes = (ctypes.c_void_p,)
        local_free.restype = ctypes.c_void_p
    except LocalFileSecurityError:
        raise
    except (AttributeError, OSError) as error:
        _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED, error)
    finally:
        if descriptor.value:
            ctypes.windll.kernel32.LocalFree(descriptor)


def ensure_private_directory(path: Path, *, allowed_root: Path) -> PermissionStatus:
    resolved = resolve_secure_path(path, allowed_root=allowed_root)
    try:
        resolved.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED, error)
    snapshot = capture_secure_path(resolved, allowed_root=allowed_root)
    if not snapshot.is_directory:
        _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED)
    try:
        if os.name == "nt":
            _apply_windows_owner_dacl(resolved, is_directory=True)
        else:
            os.chmod(resolved, 0o700, follow_symlinks=False)
    except LocalFileSecurityError:
        raise
    except OSError as error:
        _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED, error)
    return PermissionStatus.PRIVATE_OWNER_ONLY


def harden_private_file(path: Path, *, allowed_root: Path) -> PermissionStatus:
    snapshot = capture_secure_path(path, allowed_root=allowed_root)
    if not snapshot.is_file:
        _raise(LocalFileSecurityCode.FILE_REQUIRED)
    try:
        if os.name == "nt":
            _apply_windows_owner_dacl(snapshot.path, is_directory=False)
        else:
            os.chmod(snapshot.path, 0o600, follow_symlinks=False)
    except LocalFileSecurityError:
        raise
    except OSError as error:
        _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED, error)
    return PermissionStatus.PRIVATE_OWNER_ONLY


def inspect_permission_status(
    path: Path, *, allowed_root: Path, external_readonly: bool = False
) -> PermissionStatus:
    snapshot = capture_secure_path(path, allowed_root=allowed_root)
    if not snapshot.is_file:
        _raise(LocalFileSecurityCode.FILE_REQUIRED)
    if os.name == "nt":
        return (
            PermissionStatus.WINDOWS_DACL_PRESENT
            if external_readonly
            else PermissionStatus.PRIVATE_OWNER_ONLY
        )
    try:
        mode = stat.S_IMODE(os.lstat(snapshot.path).st_mode)
    except OSError as error:
        _raise(LocalFileSecurityCode.PATH_RESOLUTION_FAILED, error)
    if mode & 0o022:
        return PermissionStatus.EXCESSIVE_WRITE
    if mode & 0o077:
        return PermissionStatus.EXTERNAL_READABLE_RESTRICTED
    return PermissionStatus.PRIVATE_OWNER_ONLY


def private_temporary_file(
    parent: Path,
    *,
    allowed_root: Path,
    prefix: str,
    suffix: str,
) -> Path:
    private_parent = resolve_secure_path(parent, allowed_root=allowed_root)
    ensure_private_directory(private_parent, allowed_root=allowed_root)
    try:
        descriptor, raw_path = tempfile.mkstemp(
            dir=private_parent,
            prefix=prefix,
            suffix=suffix,
        )
        os.close(descriptor)
    except OSError as error:
        _raise(LocalFileSecurityCode.PERMISSION_HARDENING_FAILED, error)
    result = Path(raw_path)
    harden_private_file(result, allowed_root=allowed_root)
    return result


def read_file_nofollow(path: Path, *, allowed_root: Path, maximum_bytes: int) -> bytes:
    if not isinstance(maximum_bytes, int) or isinstance(maximum_bytes, bool) or maximum_bytes < 0:
        raise ValueError("maximum_bytes must be a non-negative int")
    before = capture_secure_path(path, allowed_root=allowed_root)
    if not before.is_file:
        _raise(LocalFileSecurityCode.FILE_REQUIRED)
    if before.size_bytes > maximum_bytes:
        _raise(LocalFileSecurityCode.FILE_TOO_LARGE)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(before.path, flags)
    except OSError as error:
        _raise(LocalFileSecurityCode.PATH_CHANGED, error)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.device, before.inode):
            _raise(LocalFileSecurityCode.PATH_CHANGED)
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > maximum_bytes:
            _raise(LocalFileSecurityCode.FILE_TOO_LARGE)
    finally:
        os.close(descriptor)
    after = capture_secure_path(path, allowed_root=allowed_root)
    if not before.same_state(after):
        _raise(LocalFileSecurityCode.PATH_CHANGED)
    return payload


def hash_file_nofollow(path: Path, *, allowed_root: Path) -> str:
    before = capture_secure_path(path, allowed_root=allowed_root)
    if not before.is_file:
        _raise(LocalFileSecurityCode.FILE_REQUIRED)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(before.path, flags)
    except OSError as error:
        _raise(LocalFileSecurityCode.PATH_CHANGED, error)
    digest = hashlib.sha256()
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.device, before.inode):
            _raise(LocalFileSecurityCode.PATH_CHANGED)
        while block := os.read(descriptor, 1024 * 1024):
            digest.update(block)
    finally:
        os.close(descriptor)
    after = capture_secure_path(path, allowed_root=allowed_root)
    if not before.same_state(after):
        _raise(LocalFileSecurityCode.PATH_CHANGED)
    return digest.hexdigest()


def atomic_publish_fresh(source: Path, destination: Path, *, allowed_root: Path) -> None:
    source_snapshot = capture_secure_path(source, allowed_root=allowed_root)
    destination_snapshot = capture_secure_path(destination, allowed_root=allowed_root)
    if not source_snapshot.is_file:
        _raise(LocalFileSecurityCode.FILE_REQUIRED)
    if destination_snapshot.exists:
        _raise(LocalFileSecurityCode.DESTINATION_EXISTS)
    if source_snapshot.path.anchor != destination_snapshot.path.anchor:
        _raise(LocalFileSecurityCode.ATOMIC_PUBLICATION_FAILED)
    if not source_snapshot.same_state(
        capture_secure_path(source, allowed_root=allowed_root)
    ) or capture_secure_path(destination, allowed_root=allowed_root).exists:
        _raise(LocalFileSecurityCode.PATH_CHANGED)
    try:
        os.link(source_snapshot.path, destination_snapshot.path)
    except FileExistsError as error:
        _raise(LocalFileSecurityCode.DESTINATION_EXISTS, error)
    except OSError as error:
        _raise(LocalFileSecurityCode.ATOMIC_PUBLICATION_FAILED, error)
    published = capture_secure_path(destination, allowed_root=allowed_root)
    if not source_snapshot.same_identity(published):
        _raise(LocalFileSecurityCode.PATH_CHANGED)
    harden_private_file(published.path, allowed_root=allowed_root)
    try:
        source_snapshot.path.unlink()
    except OSError as error:
        current = capture_secure_path(destination, allowed_root=allowed_root)
        if published.same_identity(current):
            current.path.unlink(missing_ok=True)
        _raise(LocalFileSecurityCode.ATOMIC_PUBLICATION_FAILED, error)


def atomic_replace_checked(
    source: Path,
    destination: Path,
    *,
    allowed_root: Path,
    expected_destination: PathSnapshot,
) -> None:
    source_snapshot = capture_secure_path(source, allowed_root=allowed_root)
    current = capture_secure_path(destination, allowed_root=allowed_root)
    if not source_snapshot.is_file:
        _raise(LocalFileSecurityCode.FILE_REQUIRED)
    if not expected_destination.same_state(current):
        _raise(LocalFileSecurityCode.PATH_CHANGED)
    if not current.exists:
        atomic_publish_fresh(source, destination, allowed_root=allowed_root)
        return
    if not current.is_file or source_snapshot.path.anchor != current.path.anchor:
        _raise(LocalFileSecurityCode.ATOMIC_PUBLICATION_FAILED)
    try:
        os.replace(source_snapshot.path, current.path)
    except OSError as error:
        _raise(LocalFileSecurityCode.ATOMIC_PUBLICATION_FAILED, error)
    published = capture_secure_path(current.path, allowed_root=allowed_root)
    if not source_snapshot.same_identity(published):
        _raise(LocalFileSecurityCode.PATH_CHANGED)
    harden_private_file(published.path, allowed_root=allowed_root)
