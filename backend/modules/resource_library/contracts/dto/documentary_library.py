"""Documentary snapshots carry evidence, never canonical or operational authority."""
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

SCHEMA = "V2-DOCUMENTARY-LIBRARY-SNAPSHOT-1.0"


def documentary_hash(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("DOCUMENTARY_HASH_REQUIRED")
    return value


@dataclass(frozen=True)
class DocumentaryAttachment:
    name: str
    content: bytes

    def __post_init__(self) -> None:
        if (re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", self.name) is None
                or not isinstance(self.content, bytes) or len(self.content) > 4_000_000):
            raise ValueError("DOCUMENTARY_ATTACHMENT_REJECTED")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class DocumentarySnapshot:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), {"schema", "archive_sha256", "manifest", "organizations",
            "documents", "sources", "files", "authority"})
        documentary_hash(data["archive_sha256"])
        if (data["schema"] != SCHEMA or data["authority"] != {
                "canonical_admission": "NOT_GRANTED", "pedagogical_validation": "NOT_GRANTED",
                "transfer_consent": "NOT_GRANTED", "generation_right": "NONE"}):
            raise ValueError("DOCUMENTARY_AUTHORITY_REJECTED")
        organizations = items(data["organizations"], 100)
        org_ids = {str(o["id"]) for o in organizations}
        if not organizations or len(org_ids) != len(organizations):
            raise ValueError("DOCUMENTARY_ORGANIZATIONS")
        for row in organizations:
            object_data(row, {"id", "label", "entity_scope", "legal_anchor_status"})
            if row["entity_scope"] != "GROUP_AS_DESCRIBED_BY_SUPPLIED_SOURCES" or row["legal_anchor_status"] != "NOT_MAPPED_TO_CANONICAL_IDENTITY":
                raise ValueError("DOCUMENTARY_ENTITY_SCOPE")
        sources = items(data["sources"], 1000)
        source_ids = {str(s["id"]) for s in sources}
        if not sources or len(source_ids) != len(sources):
            raise ValueError("DOCUMENTARY_SOURCES")
        for row in sources:
            parsed = urlsplit(str(row.get("url", "")))
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("DOCUMENTARY_SOURCE_URL")
        files = items(data["files"], 100)
        file_index = {str(f["name"]): f for f in files}
        if len(files) != len(file_index):
            raise ValueError("DOCUMENTARY_FILES")
        for row in files:
            object_data(row, {"name", "sha256", "bytes"})
            DocumentaryAttachment(str(row["name"]), b"")
            documentary_hash(row["sha256"])
            if type(row["bytes"]) is not int or not 0 <= row["bytes"] <= 4_000_000:
                raise ValueError("DOCUMENTARY_FILE_SIZE")
        documents = items(data["documents"], 1000)
        ids = {str(d["id"]) for d in documents}
        if not documents or len(ids) != len(documents):
            raise ValueError("DOCUMENTARY_DOCUMENTS")
        for doc in documents:
            object_data(doc, {"id", "organization_id", "metadata", "origin", "blocks", "source_ids", "content_sha256"})
            meta, origin = object_data(doc["metadata"]), object_data(doc["origin"])
            refs = doc["source_ids"]
            if (doc["organization_id"] not in org_ids or not isinstance(refs, (list, tuple)) or not refs
                    or any(not isinstance(ref, str) or ref not in source_ids for ref in refs)
                    or len(set(refs)) != len(refs) or as_plain(refs) != meta.get("sources")
                    or meta.get("classification") != "SYNTHÈSE PÉDAGOGIQUE ORIGINALE DE SOURCES PUBLIQUES"
                    or meta.get("pedagogical_approval") != "NON_VALIDÉE_PAR_PROPRIÉTAIRE"):
                raise ValueError("DOCUMENTARY_LINK_OR_CLASSIFICATION")
            captured = file_index.get(str(origin.get("file")))
            if (captured is None or origin.get("file_sha256") != captured["sha256"]
                    or origin.get("part") != "word/document.xml" or origin.get("capsule_id") != doc["id"]
                    or not items(doc["blocks"], 300) or fingerprint(doc["blocks"]) != doc["content_sha256"]):
                raise ValueError("DOCUMENTARY_ORIGIN_OR_CONTENT_CHANGED")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))
