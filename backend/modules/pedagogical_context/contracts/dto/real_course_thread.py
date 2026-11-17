"""Versioned public documentary thread; identity/source presence is not factual promotion."""
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import cast
from urllib.parse import urlsplit

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    nonempty,
    object_data,
)
from backend.modules.resource_library.contracts.dto.documentary_course_thread import (
    DOCUMENTARY_THREAD,
    DocumentaryCourseThread,
)
from backend.modules.resource_library.contracts.dto.organization_evidence import (
    OrganizationEvidence,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

REAL_THREAD = "COURSE-REAL-THREAD-1.0"
REAL_CHAPTER = "COURSE-CHAPTER-REAL-5.0"
FICTION_NOTICE = "Situation pédagogique construite — ne décrit pas une pratique attestée de "
DOCUMENT_FIELDS = {"id", "title", "source_url", "publisher", "retrieved_on", "excerpt",
                   "excerpt_sha256", "rights", "notion_refs"}


@dataclass(frozen=True, slots=True)
class RealCourseThread:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.data.get("contract_id") == DOCUMENTARY_THREAD:
            object.__setattr__(self, "data", DocumentaryCourseThread(self.data).data)
            return
        data = object_data(as_plain(self.data), {"contract_id", "identity", "documents"})
        if data["contract_id"] != REAL_THREAD:
            raise ValueError("COURSE_REAL_THREAD_CONTRACT")
        identity = OrganizationEvidence(object_data(data["identity"]))
        nonempty(identity.data["organization_label"], 180)
        nonempty(identity.documentary_text(), 4000)
        nonempty(identity.data["source_url"], 1000)
        if re.fullmatch(r"siren:[0-9]{9}", str(identity.data["organization_id"])) is None:
            raise ValueError("COURSE_REAL_IDENTITY")
        documents = items(data["documents"], 6)
        if not documents or len({d.get("id") for d in documents}) != len(documents):
            raise ValueError("COURSE_REAL_DOCUMENTS_REQUIRED")
        for row in documents:
            object_data(row, DOCUMENT_FIELDS)
            if re.fullmatch(r"S[1-6]", str(row["id"])) is None:
                raise ValueError("COURSE_REAL_DOCUMENT_ID")
            for key, maximum in (("title", 200), ("publisher", 300), ("excerpt", 4000),
                                 ("rights", 1000)):
                nonempty(row[key], maximum)
            parsed = urlsplit(nonempty(row["source_url"], 1000))
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("COURSE_REAL_SOURCE_URL")
            date.fromisoformat(str(row["retrieved_on"]))
            if hashlib.sha256(str(row["excerpt"]).encode()).hexdigest() != row["excerpt_sha256"]:
                raise ValueError("COURSE_REAL_EXCERPT_CHANGED")
            refs = row["notion_refs"]
            if (not isinstance(refs, (list, tuple)) or not 1 <= len(refs) <= 16
                    or any(not isinstance(r, str) or not r.startswith("notion:") for r in refs)
                    or len(set(refs)) != len(refs)):
                raise ValueError("COURSE_REAL_DOCUMENT_NOTIONS")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    @property
    def organization_id(self) -> str:
        if self.data["contract_id"] == DOCUMENTARY_THREAD:
            return DocumentaryCourseThread(self.data).organization_id
        return str(object_data(self.data["identity"])["organization_id"])

    @property
    def label(self) -> str:
        if self.data["contract_id"] == DOCUMENTARY_THREAD:
            return DocumentaryCourseThread(self.data).label
        return str(object_data(self.data["identity"])["organization_label"])

    @property
    def fiction_notice(self) -> str:
        return FICTION_NOTICE + self.label + "."

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))

    def summary(self) -> dict[str, object]:
        if self.data["contract_id"] == DOCUMENTARY_THREAD:
            return {"organization_id": self.organization_id, "organization_label": self.label,
                    "dossier_sha256": self.sha256, "source_count": len(items(self.data["documents"])),
                    "notion_refs": [], "canonical_admission": "NOT_GRANTED", "source_kind": "LOCAL_PEDAGOGICAL_SYNTHESIS"}
        return {"organization_id": self.organization_id, "organization_label": self.label,
                "dossier_sha256": self.sha256, "source_count": len(items(self.data["documents"])),
                "notion_refs": sorted({str(n) for d in items(self.data["documents"])
                                      for n in cast(tuple[str, ...], d["notion_refs"])}),
                "canonical_admission": "NOT_GRANTED"}

    def source_rows(self) -> list[dict[str, object]]:
        if self.data["contract_id"] == DOCUMENTARY_THREAD:
            return DocumentaryCourseThread(self.data).source_rows()
        identity = OrganizationEvidence(object_data(self.data["identity"]))
        base = identity.data
        rows = [{"id": "IDENTITY", "title": "Identité documentaire de " + self.label,
                 "source_url": base["source_url"], "publisher": base["publisher"],
                 "retrieved_on": base["retrieved_on"], "excerpt": identity.documentary_text(),
                 "rights": str(base["license"]) + " — " + str(base["reuse_scope"]), "notion_refs": []}]
        rows.extend(object_data(as_plain(d)) for d in items(self.data["documents"]))
        return rows

    def references(self) -> list[dict[str, object]]:
        from backend.modules.pedagogical_design.contracts.dto.p0_production import (
            P0_PROVENANCE_LABEL,
        )

        result = []
        for row in self.source_rows():
            checksum = fingerprint(row)
            result.append({"evidence_id": "evidence:" + checksum[:32],
                "source_ref": "public-organization:" + self.organization_id + ":" + str(row["id"]),
                "locator": row["source_url"], "checksum_or_version": checksum,
                "excerpt_sha256": hashlib.sha256(str(row["excerpt"]).encode()).hexdigest(),
                "provenance_label": P0_PROVENANCE_LABEL})
        return result

    def evidence(self) -> dict[str, str]:
        return {str(ref["evidence_id"]): str(row["excerpt"])
                for ref, row in zip(self.references(), self.source_rows(), strict=True)}

    def passages(self) -> list[dict[str, object]]:
        result = [{"object_ref": ref["source_ref"], "passage_ref": ref["locator"],
                 "version_or_checksum": ref["checksum_or_version"],
                 "object_kind": "PUBLIC_ORGANIZATION_DOCUMENT", "notion_ref": self.organization_id,
                 "excerpt": row["excerpt"], "excerpt_truncated": False,
                 "authority": "PUBLIC_DOCUMENTARY_PROPOSAL",
                 "authority_basis": "PINNED_ORGANIZATION_DOSSIER_NOT_OFFICIAL_PROGRAMME",
                 "provenance": {k: row[k] for k in ("title", "publisher", "retrieved_on", "rights")},
                 "source_status": {"dossier_sha256": self.sha256, "canonical_admission": "NOT_GRANTED"}}
                for ref, row in zip(self.references(), self.source_rows(), strict=True)]
        if self.data["contract_id"] == DOCUMENTARY_THREAD:
            for passage, row in zip(result, self.source_rows(), strict=True):
                passage["authority"] = "LOCAL_PEDAGOGICAL_SYNTHESIS_NOT_ADMITTED"
                passage["authority_basis"] = "EXACT_SUPPLIED_DOCUMENTARY_LIBRARY_SELECTION"
                provenance = object_data(passage["provenance"])
                for key in ("origin", "citations"):
                    if key in row:
                        provenance[key] = row[key]
                passage["provenance"] = provenance
        return result

    def public_projection(self) -> dict[str, object]:
        if self.data["contract_id"] == DOCUMENTARY_THREAD:
            return DocumentaryCourseThread(self.data).public_projection()
        return {"organization_label": self.label,
                "notice": "Organisation réelle étudiée sur documents. Les mises en situation sont pédagogiques.",
                "sources": [{k: row[k] for k in ("title", "source_url", "publisher",
                                                "retrieved_on", "rights")}
                            for row in self.source_rows()]}


def thread_from_context(context: Mapping[str, object]) -> RealCourseThread | None:
    resolution = context.get("institutional_resolution")
    if not isinstance(resolution, Mapping) or "course_thread" not in resolution:
        return None
    return RealCourseThread(object_data(resolution["course_thread"]))


def validate_real_course(thread: RealCourseThread, chapter: Mapping[str, object],
                         references: object) -> None:
    if (object_data(chapter["context"])["title"] != thread.label
            or as_plain(chapter.get("organization_thread")) != thread.as_dict()):
        raise ValueError("COURSE_REAL_ORGANIZATION_CHANGED")
    provided = {str(r["evidence_id"]): r for r in items(references, 8)}
    expected = thread.references()
    for ref in expected:
        if provided.get(str(ref["evidence_id"])) != ref:
            raise ValueError("COURSE_REAL_SOURCE_CHANGED")
    texts = thread.evidence()
    identity_id = str(expected[0]["evidence_id"])
    required = set(texts) - {identity_id}
    used = set()
    docs = items(chapter["documents"])
    delivered = {str(d) for p in items(chapter["parts"]) for d in cast(tuple[str, ...], p["document_ids"])}
    for doc in docs:
        provenance = object_data(doc["provenance"])
        source = str(provenance["source_ref"])
        if provenance["kind"] == "SUPPLIED_REFERENCE" and source in texts:
            if doc["text"] != texts[source] or doc["table"] is not None:
                raise ValueError("COURSE_REAL_DOCUMENT_NOT_EXACT")
            if doc["id"] in delivered:
                used.add(source)
        elif provenance["kind"] == "LOCAL_FICTION" and not str(doc["text"]).startswith(thread.fiction_notice):
            raise ValueError("COURSE_REAL_CONSTRUCTION_NOTICE_REQUIRED")
    if not required <= used:
        raise ValueError("COURSE_REAL_DOCUMENT_NOT_USED")
