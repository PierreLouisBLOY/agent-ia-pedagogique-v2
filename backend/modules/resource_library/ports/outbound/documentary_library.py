from collections.abc import Mapping
from typing import Protocol

from backend.modules.resource_library.contracts.dto.documentary_library import (
    DocumentaryAttachment,
    DocumentarySnapshot,
)


class DocumentaryPackageReader(Protocol):
    def read(self) -> tuple[DocumentarySnapshot, tuple[DocumentaryAttachment, ...]]: ...


class DocumentaryLibraryPort(Protocol):
    def descriptor(self) -> Mapping[str, object]: ...
    def append(self, snapshot: DocumentarySnapshot, files: tuple[DocumentaryAttachment, ...]) -> bool: ...
    def snapshots(self) -> tuple[DocumentarySnapshot, ...]: ...
    def attachment(self, archive_sha256: str, name: str) -> DocumentaryAttachment: ...
