"""Bounded Application import/read boundary; no admission or generation effect."""
import re
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items
from backend.modules.resource_library.contracts.dto.documentary_library import documentary_hash
from backend.modules.resource_library.ports.outbound.documentary_library import (
    DocumentaryLibraryPort,
    DocumentaryPackageReader,
)


class DocumentaryLibraryApplication:
    def __init__(self, store: DocumentaryLibraryPort, package: DocumentaryPackageReader | None = None) -> None:
        self.store, self.package = store, package

    def import_package(self) -> dict[str, object]:
        if self.package is None:
            raise ValueError("DOCUMENTARY_IMPORT_NOT_CONFIGURED")
        snapshot, attachments = self.package.read()
        created = self.store.append(snapshot, attachments)
        return {"state": "IMPORTED_NOT_ADMITTED" if created else "ALREADY_PRESENT_UNCHANGED",
                "archive_sha256": snapshot.data["archive_sha256"], "snapshot_sha256": snapshot.sha256,
                "authority": snapshot.as_dict()["authority"], "provider_calls": 0}

    def summary(self) -> dict[str, object]:
        before = dict(self.store.descriptor())
        snapshots = self.store.snapshots()
        after = dict(self.store.descriptor())
        if before != after:
            raise ValueError("DOCUMENTARY_CONCURRENT_CHANGE")
        return {"packages": [{"archive_sha256": s.data["archive_sha256"], "snapshot_sha256": s.sha256,
            "organizations": len(items(s.data["organizations"], 100)),
            "documents": len(items(s.data["documents"], 1000)), "sources": len(items(s.data["sources"], 1000)),
            "files": len(items(s.data["files"], 100)), "authority": s.as_dict()["authority"]} for s in snapshots],
            "provider_calls": 0, "mode": "DOCUMENTARY_READ_ONLY", "database": after}

    def read(self, archive: str, *, document: str | None = None) -> dict[str, object]:
        documentary_hash(archive)
        if document is not None and re.fullmatch(r"[DO][0-9]{2}", document) is None:
            raise ValueError("DOCUMENTARY_ID_REJECTED")
        selected = [s for s in self.store.snapshots() if s.data["archive_sha256"] == archive]
        if len(selected) != 1:
            raise ValueError("DOCUMENTARY_PACKAGE_NOT_FOUND")
        data = selected[0].as_dict()
        if document is None:
            return data
        matches = [d for d in items(data["documents"], 1000) if d["id"] == document]
        if len(matches) != 1:
            raise ValueError("DOCUMENTARY_DOCUMENT_NOT_FOUND")
        doc = matches[0]
        sources = {str(s["id"]): s for s in items(data["sources"], 1000)}
        return {"archive_sha256": archive, "snapshot_sha256": selected[0].sha256, "document": doc,
                "sources": [sources[ref] for ref in cast(list[str], doc["source_ids"])],
                "authority": data["authority"]}

    def verify_files(self, archive: str) -> dict[str, object]:
        data = self.read(archive)
        for row in items(data["files"], 100):
            file = self.store.attachment(archive, str(row["name"]))
            if file.sha256 != row["sha256"] or len(file.content) != row["bytes"]:
                raise ValueError("DOCUMENTARY_ATTACHMENT_CHANGED")
        return {"state": "ALL_ORIGINAL_FILES_VERIFIED", "files": len(items(data["files"], 100)), "provider_calls": 0}
