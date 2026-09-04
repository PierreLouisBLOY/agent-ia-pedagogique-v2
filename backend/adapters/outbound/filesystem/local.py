"""Concrete no-follow resolver and inspector for trusted local sandbox roots."""

from __future__ import annotations

import hashlib
import os
import zipfile
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path

from backend.agent_runtime.sandbox.model import (
    ResolvedSandboxPath,
    SandboxRelativePath,
    SandboxRootRef,
)
from backend.infrastructure.filesystem import (
    LocalFileSecurityCode,
    LocalFileSecurityError,
    atomic_publish_fresh,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    private_temporary_file,
    read_file_nofollow,
    resolve_secure_path,
)

_MAX_INSPECTION_BYTES = 50 * 1024 * 1024
_EXECUTABLE_MAGICS = (b"MZ", b"\x7fELF", b"#!")
_MIME_BY_EXTENSION = {
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


class LocalSandboxFilesystemAdapter:
    """Bind opaque trusted root references to local paths outside agent runtime."""

    def __init__(self, roots: Mapping[SandboxRootRef, Path]) -> None:
        if not isinstance(roots, Mapping) or not roots:
            raise ValueError("roots must be a non-empty mapping")
        normalized: dict[SandboxRootRef, Path] = {}
        for root_ref, root_path in roots.items():
            if not isinstance(root_ref, SandboxRootRef) or not isinstance(root_path, Path):
                raise TypeError("roots must map SandboxRootRef to Path")
            resolved = resolve_secure_path(root_path, allowed_root=root_path)
            snapshot = capture_secure_path(resolved, allowed_root=resolved)
            if not snapshot.is_directory:
                raise LocalFileSecurityError(LocalFileSecurityCode.FILE_REQUIRED)
            normalized[root_ref] = resolved
        self._roots = normalized

    def resolve(
        self,
        *,
        root_ref: SandboxRootRef,
        relative_path: SandboxRelativePath,
    ) -> ResolvedSandboxPath:
        root = self._root(root_ref)
        if not isinstance(relative_path, SandboxRelativePath):
            raise TypeError("relative_path must be a SandboxRelativePath")
        path = root.joinpath(*relative_path.segments)
        return self._inspect_path(root_ref, relative_path, path)

    def inspect(self, *, resolved_path: ResolvedSandboxPath) -> ResolvedSandboxPath:
        if not isinstance(resolved_path, ResolvedSandboxPath):
            raise TypeError("resolved_path must be a ResolvedSandboxPath")
        refreshed = self.resolve(
            root_ref=resolved_path.root_ref,
            relative_path=resolved_path.relative_path,
        )
        if refreshed.canonical_path_token != resolved_path.canonical_path_token:
            raise LocalFileSecurityError(LocalFileSecurityCode.PATH_CHANGED)
        return refreshed

    def read_bytes(
        self,
        *,
        root_ref: SandboxRootRef,
        relative_path: SandboxRelativePath,
        maximum_bytes: int,
    ) -> bytes:
        root = self._root(root_ref)
        return read_file_nofollow(
            root.joinpath(*relative_path.segments),
            allowed_root=root,
            maximum_bytes=maximum_bytes,
        )

    def publish_bytes(
        self,
        *,
        root_ref: SandboxRootRef,
        relative_path: SandboxRelativePath,
        payload: bytes,
        maximum_bytes: int,
    ) -> ResolvedSandboxPath:
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        if len(payload) > maximum_bytes:
            raise LocalFileSecurityError(LocalFileSecurityCode.FILE_TOO_LARGE)
        root = self._root(root_ref)
        destination = resolve_secure_path(
            root.joinpath(*relative_path.segments), allowed_root=root
        )
        ensure_private_directory(destination.parent, allowed_root=root)
        temporary = private_temporary_file(
            destination.parent,
            allowed_root=root,
            prefix=".projet-v2-sandbox-",
            suffix=".tmp",
        )
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                view = memoryview(payload)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            harden_private_file(temporary, allowed_root=root)
            atomic_publish_fresh(temporary, destination, allowed_root=root)
        finally:
            temporary.unlink(missing_ok=True)
        return self.resolve(root_ref=root_ref, relative_path=relative_path)

    def _root(self, root_ref: SandboxRootRef) -> Path:
        if not isinstance(root_ref, SandboxRootRef):
            raise TypeError("root_ref must be a SandboxRootRef")
        try:
            return self._roots[root_ref]
        except KeyError as error:
            raise LocalFileSecurityError(
                LocalFileSecurityCode.OUTSIDE_ALLOWED_ROOT
            ) from error

    def _inspect_path(
        self,
        root_ref: SandboxRootRef,
        relative_path: SandboxRelativePath,
        path: Path,
    ) -> ResolvedSandboxPath:
        root = self._root(root_ref)
        snapshot = capture_secure_path(path, allowed_root=root)
        extension = relative_path.extension or None
        mime_type: str | None = None
        active_content = False
        executable_content = False
        if snapshot.is_file:
            payload = read_file_nofollow(
                snapshot.path,
                allowed_root=root,
                maximum_bytes=_MAX_INSPECTION_BYTES,
            )
            executable_content = payload.startswith(_EXECUTABLE_MAGICS)
            mime_type, active_content = _classify_content(extension, payload)
        token_payload = (
            f"{root_ref.run_id}\0{root_ref.root_id}\0{relative_path.value}\0"
            f"{snapshot.token}"
        ).encode()
        return ResolvedSandboxPath(
            root_ref=root_ref,
            relative_path=relative_path,
            canonical_path_token=hashlib.sha256(token_payload).hexdigest(),
            exists=snapshot.exists,
            is_file=snapshot.is_file,
            is_symlink=False,
            is_within_root=True,
            size_bytes=snapshot.size_bytes,
            observed_extension=extension,
            observed_mime_type=mime_type,
            has_active_content=active_content,
            is_executable_content=executable_content,
        )


def _classify_content(extension: str | None, payload: bytes) -> tuple[str | None, bool]:
    if extension == ".pdf":
        return ("application/pdf", False) if payload.startswith(b"%PDF-") else (None, False)
    if extension == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                names = frozenset(archive.namelist())
        except (OSError, zipfile.BadZipFile):
            return None, False
        required = {"[Content_Types].xml", "word/document.xml"}
        if not required.issubset(names):
            return None, False
        return (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "word/vbaProject.bin" in names,
        )
    if extension in _MIME_BY_EXTENSION:
        if b"\0" in payload:
            return None, False
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError:
            return None, False
        return _MIME_BY_EXTENSION[extension], False
    return None, False
