"""Immutable binary references in an explicit isolated library, never incident stores."""
import hashlib
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.adapters.outbound.persistence.partial_workspace import closed_json
from backend.infrastructure.filesystem import (
    LocalFileSecurityCode,
    LocalFileSecurityError,
    assert_local_data_root,
    atomic_publish_fresh,
    capture_secure_path,
    ensure_private_directory,
    private_temporary_file,
    read_file_nofollow,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference


class LocalFormatReferenceStore:
    def __init__(self, library_root: Path, source_root: Path) -> None:
        self.library = assert_local_data_root(library_root)
        self.source = assert_local_data_root(source_root)
        source_tree = Path(__file__).resolve().parents[4]
        if self.library == source_tree or source_tree in self.library.parents:
            raise ValueError("FORMAT_REFERENCE_OUTSIDE_SOURCE")
        self.root = self.library / "format-references"

    def _directory(self, ref: str) -> Path:
        if re.fullmatch(r"V2-FORMAT-[A-Z0-9-]{1,80}", ref) is None:
            raise ValueError("FORMAT_REFERENCE_ID")
        return self.root / ref

    def _fresh(self, directory: Path, name: str, raw: bytes) -> None:
        temporary = private_temporary_file(directory, allowed_root=self.library, prefix="format-", suffix=".pending")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_publish_fresh(temporary, directory / name, allowed_root=self.library)

    @contextmanager
    def _locked(self, directory: Path) -> Iterator[None]:
        path = directory / "writer.lock"
        before = capture_secure_path(path, allowed_root=self.library)
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != (before.device, before.inode):
                raise ValueError("FORMAT_REFERENCE_LOCK_CHANGED")
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(descriptor)

    def _read_locked(self, directory: Path, ref: str) -> FormatReference:
        raw = read_file_nofollow(directory / "record.json", allowed_root=self.library, maximum_bytes=16384)
        record = FormatReference(closed_json(raw))
        if record.reference_id != ref or encoded(record.as_dict()) != raw:
            raise ValueError("FORMAT_REFERENCE_RECORD_CHANGED")
        binary = read_file_nofollow(directory / "document.docx", allowed_root=self.library, maximum_bytes=16 * 1024 * 1024)
        self._check(record, binary)
        return record

    @staticmethod
    def _check(record: FormatReference, raw: bytes) -> None:
        if len(raw) != record.as_dict()["size_bytes"] or hashlib.sha256(raw).hexdigest() != record.as_dict()["source_sha256"]:
            raise ValueError("FORMAT_REFERENCE_BINARY_CHANGED")

    def register(self, record: FormatReference, source_locator: str) -> FormatReference:
        relative = Path(source_locator)
        if (not source_locator or "\\" in source_locator or ":" in source_locator
                or relative.is_absolute() or ".." in relative.parts):
            raise ValueError("FORMAT_REFERENCE_SOURCE_PATH")
        raw = read_file_nofollow(self.source / relative, allowed_root=self.source, maximum_bytes=16 * 1024 * 1024)
        self._check(record, raw)
        directory = self._directory(record.reference_id)
        ensure_private_directory(directory, allowed_root=self.library)
        if not capture_secure_path(directory / "writer.lock", allowed_root=self.library).exists:
            try:
                self._fresh(directory, "writer.lock", b"0")
            except LocalFileSecurityError as error:
                if error.code != LocalFileSecurityCode.DESTINATION_EXISTS:
                    raise
        with self._locked(directory):
            present = [capture_secure_path(directory / name, allowed_root=self.library).exists
                for name in ("document.docx", "record.json")]
            if any(present):
                if not all(present):
                    raise ValueError("FORMAT_REFERENCE_PUBLICATION_INCOMPLETE")
                prior = self._read_locked(directory, record.reference_id)
                if prior.as_dict() != record.as_dict():
                    raise ValueError("FORMAT_REFERENCE_CONFLICT")
                return prior
            self._fresh(directory, "document.docx", raw)
            self._fresh(directory, "record.json", encoded(record.as_dict()))
            return self._read_locked(directory, record.reference_id)

    def read(self, reference_id: str) -> FormatReference:
        directory = self._directory(reference_id)
        with self._locked(directory):
            return self._read_locked(directory, reference_id)
