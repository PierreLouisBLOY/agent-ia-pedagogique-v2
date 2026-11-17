from pathlib import Path

from backend.adapters.inbound.application.documentary_library import DocumentaryLibraryInbound
from backend.adapters.outbound.resource_library.documentary_package import LocalDocumentaryPackage
from backend.adapters.outbound.resource_library.documentary_sqlite import DocumentarySQLite
from backend.modules.resource_library.application.services.documentary_library import (
    DocumentaryLibraryApplication,
)


def build_documentary_library(*, database: Path, data_root: Path, archive: Path | None = None,
                              archive_sha256: str | None = None) -> DocumentaryLibraryInbound:
    package = None
    if archive is not None or archive_sha256 is not None:
        if archive is None or archive_sha256 is None:
            raise ValueError("DOCUMENTARY_EXACT_ARCHIVE_REQUIRED")
        package = LocalDocumentaryPackage(archive, archive_sha256)
        # Validate everything before creating even an empty database.
        package.read()
    store = DocumentarySQLite(database, allowed_root=data_root, create=package is not None)
    return DocumentaryLibraryInbound(DocumentaryLibraryApplication(store, package))
