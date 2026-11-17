"""Inbound boundary used by local operators; never exposes SQL or store access."""
from backend.modules.resource_library.application.services.documentary_library import (
    DocumentaryLibraryApplication,
)


class DocumentaryLibraryInbound:
    def __init__(self, application: DocumentaryLibraryApplication) -> None:
        self.application = application

    def execute(self, operation: str, *, archive: str = "", document: str | None = None) -> dict[str, object]:
        if operation == "import":
            return self.application.import_package()
        if operation == "summary":
            return self.application.summary()
        if operation == "read":
            return self.application.read(archive, document=document)
        if operation == "verify":
            return self.application.verify_files(archive)
        raise ValueError("DOCUMENTARY_OPERATION_REJECTED")
