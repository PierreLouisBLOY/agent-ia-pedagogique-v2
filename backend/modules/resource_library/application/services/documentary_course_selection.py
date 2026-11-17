"""Read-only, exact documentary selection. Data selection conveys no generation authority."""
from collections.abc import Callable, Mapping
from threading import Lock
from typing import cast

from backend.modules.pedagogical_context.contracts.dto.real_course_thread import RealCourseThread
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.resource_library.contracts.dto.documentary_course_thread import (
    DOCUMENTARY_THREAD,
)
from backend.modules.resource_library.contracts.dto.documentary_library import documentary_hash


class DocumentaryCourseSelectionApplication:
    def __init__(self, execute: Callable[..., dict[str, object]], *, database_sha256: str,
                 archive_sha256: str, snapshot_sha256: str) -> None:
        self.execute = execute
        self.database_sha256 = documentary_hash(database_sha256)
        self.archive_sha256 = documentary_hash(archive_sha256)
        self.snapshot_sha256 = documentary_hash(snapshot_sha256)
        self._selections: dict[tuple[str, str], dict[str, object]] = {}
        self._lock = Lock()
        self._snapshot()

    def _summary(self) -> None:
        summary = self.execute("summary")
        if object_data(summary["database"])["sha256"] != self.database_sha256:
            raise ValueError("DOCUMENTARY_DATABASE_CHANGED")
        packages = items(summary["packages"], 100)
        if not any(p["archive_sha256"] == self.archive_sha256 and p["snapshot_sha256"] == self.snapshot_sha256
                   for p in packages):
            raise ValueError("DOCUMENTARY_SNAPSHOT_CHANGED")

    def _snapshot(self) -> dict[str, object]:
        self._summary()
        snapshot = self.execute("read", archive=self.archive_sha256)
        if fingerprint(snapshot) != self.snapshot_sha256:
            raise ValueError("DOCUMENTARY_SNAPSHOT_CHANGED")
        self._summary()
        return snapshot

    def catalogue(self) -> dict[str, object]:
        data = self._snapshot()
        return {"binding": "APPLICATION_READ_ONLY_EXACT_SELECTION", "archive_sha256": self.archive_sha256,
            "snapshot_sha256": self.snapshot_sha256, "database_sha256": self.database_sha256,
            "organizations": as_plain(data["organizations"]),
            "documents": [{"id": d["id"], "organization_id": d["organization_id"],
                "title": object_data(d["metadata"])["title"], "source_ids": as_plain(d["source_ids"]),
                "classification": object_data(d["metadata"])["classification"]}
                for d in items(data["documents"], 1000)], "authority": as_plain(data["authority"]),
            "max_selected_documents": 6}

    def inspect(self, document: str) -> dict[str, object]:
        self._snapshot()
        result = self.execute("read", archive=self.archive_sha256, document=document)
        if result["snapshot_sha256"] != self.snapshot_sha256:
            raise ValueError("DOCUMENTARY_SNAPSHOT_CHANGED")
        self._summary()
        return result

    def select(self, choice: Mapping[str, object]) -> Mapping[str, object]:
        chosen = object_data(as_plain(choice), {"organization_id", "document_ids", "archive_sha256", "snapshot_sha256"})
        if chosen["archive_sha256"] != self.archive_sha256 or chosen["snapshot_sha256"] != self.snapshot_sha256:
            raise ValueError("DOCUMENTARY_SELECTION_CHANGED")
        ids = chosen["document_ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 6 or any(not isinstance(i, str) for i in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("DOCUMENTARY_SELECTION_REQUIRED")
        data = self._snapshot()
        orgs = [o for o in items(data["organizations"], 100) if o["id"] == chosen["organization_id"]]
        documents = {str(d["id"]): d for d in items(data["documents"], 1000)}
        if len(orgs) != 1 or any(i not in documents or documents[i]["organization_id"] != orgs[0]["id"] for i in ids):
            raise ValueError("DOCUMENTARY_ORGANIZATION_SELECTION")
        selected = [documents[i] for i in ids]
        used = dict.fromkeys(ref for d in selected for ref in cast(list[str], d["source_ids"]))
        sources = {str(s["id"]): s for s in items(data["sources"], 1000)}
        thread = RealCourseThread({"contract_id": DOCUMENTARY_THREAD,
            "archive_sha256": self.archive_sha256, "snapshot_sha256": self.snapshot_sha256,
            "organization": orgs[0], "documents": selected, "sources": [sources[r] for r in used],
            "created_on": object_data(data["manifest"])["created_on"], "authority": data["authority"]})
        with self._lock:
            if len(self._selections) >= 64 and (thread.organization_id, thread.sha256) not in self._selections:
                raise ValueError("DOCUMENTARY_SELECTION_SESSION_FULL")
            self._selections[(thread.organization_id, thread.sha256)] = chosen
        return thread.as_dict()

    def read(self, choice: Mapping[str, object]) -> Mapping[str, object]:
        with self._lock:
            prior = self._selections.get((str(choice.get("organization_id")), str(choice.get("dossier_sha256"))))
        if prior is None:
            raise ValueError("DOCUMENTARY_SELECTION_NOT_PREPARED")
        current = RealCourseThread(self.select(prior))
        if current.sha256 != choice["dossier_sha256"]:
            raise ValueError("DOCUMENTARY_SELECTION_CHANGED")
        return current.as_dict()
