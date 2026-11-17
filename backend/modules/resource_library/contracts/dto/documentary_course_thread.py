"""Exact selection of supplied local syntheses; no invented legal identity or admission."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    nonempty,
    object_data,
)
from backend.modules.resource_library.contracts.dto.documentary_library import documentary_hash
from backend.shared_kernel._safe_data import freeze_safe_mapping

DOCUMENTARY_THREAD = "COURSE-DOCUMENTARY-THREAD-1.0"


def documentary_text(document: Mapping[str, object]) -> str:
    parts = []
    for block in items(document["blocks"], 300):
        if block["kind"] == "PARAGRAPH":
            parts.append(str(block["text"]))
        elif block["kind"] == "TABLE":
            rows = cast(list[list[str]], as_plain(block["rows"]))
            parts.extend(" | ".join(row) for row in rows)
        else:
            raise ValueError("COURSE_DOCUMENTARY_BLOCK")
    return "\n".join(parts)


@dataclass(frozen=True)
class DocumentaryCourseThread:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), {"contract_id", "archive_sha256", "snapshot_sha256",
            "organization", "documents", "sources", "created_on", "authority"})
        if data["contract_id"] != DOCUMENTARY_THREAD or data["authority"] != {
                "canonical_admission": "NOT_GRANTED", "pedagogical_validation": "NOT_GRANTED",
                "transfer_consent": "NOT_GRANTED", "generation_right": "NONE"}:
            raise ValueError("COURSE_DOCUMENTARY_AUTHORITY")
        documentary_hash(data["archive_sha256"])
        documentary_hash(data["snapshot_sha256"])
        date.fromisoformat(str(data["created_on"]))
        org = object_data(data["organization"], {"id", "label", "entity_scope", "legal_anchor_status"})
        nonempty(org["id"], 100)
        nonempty(org["label"], 180)
        if (org["entity_scope"] != "GROUP_AS_DESCRIBED_BY_SUPPLIED_SOURCES"
                or org["legal_anchor_status"] != "NOT_MAPPED_TO_CANONICAL_IDENTITY"):
            raise ValueError("COURSE_DOCUMENTARY_SCOPE")
        sources = items(data["sources"], 100)
        source_ids = {str(s["id"]) for s in sources}
        if len(source_ids) != len(sources):
            raise ValueError("COURSE_DOCUMENTARY_SOURCES")
        documents = items(data["documents"], 6)
        if not documents or len({d["id"] for d in documents}) != len(documents):
            raise ValueError("COURSE_DOCUMENTARY_SELECTION")
        used = set()
        for doc in documents:
            if doc["organization_id"] != org["id"] or fingerprint(doc["blocks"]) != doc["content_sha256"]:
                raise ValueError("COURSE_DOCUMENTARY_CONTENT_CHANGED")
            meta, origin = object_data(doc["metadata"]), object_data(doc["origin"])
            if (meta.get("classification") != "SYNTHÈSE PÉDAGOGIQUE ORIGINALE DE SOURCES PUBLIQUES"
                    or meta.get("pedagogical_approval") != "NON_VALIDÉE_PAR_PROPRIÉTAIRE"
                    or origin.get("capsule_id") != doc["id"] or origin.get("part") != "word/document.xml"):
                raise ValueError("COURSE_DOCUMENTARY_CLASSIFICATION")
            documentary_hash(origin.get("file_sha256"))
            refs = cast(list[str], doc["source_ids"])
            if not refs or not set(refs) <= source_ids or refs != meta.get("sources"):
                raise ValueError("COURSE_DOCUMENTARY_SOURCE_LINK")
            used.update(refs)
            nonempty(documentary_text(doc), 4000)
        if used != source_ids:
            raise ValueError("COURSE_DOCUMENTARY_UNUSED_SOURCE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def organization_id(self) -> str:
        return "documentary:" + str(object_data(self.data["organization"])["id"])

    @property
    def label(self) -> str:
        return str(object_data(self.data["organization"])["label"]) + " — Groupe"

    def source_rows(self) -> list[dict[str, object]]:
        archive = str(self.data["archive_sha256"])
        rows: list[dict[str, object]] = [{"id": "IDENTITY", "title": "Périmètre documentaire — " + self.label,
            "source_url": "documentary-library:" + archive + "#" + self.organization_id,
            "publisher": "Dossier documentaire fourni", "retrieved_on": self.data["created_on"],
            "excerpt": "Organisation étudiée : " + self.label + ". Périmètre de groupe décrit par les sources du dossier. "
                "Ne pas attribuer automatiquement ces données à une filiale. Aucun rattachement juridique canonique n'est déduit.",
            "rights": "Description locale du périmètre ; aucune licence tierce attribuée.", "notion_refs": []}]
        source_index = {str(s["id"]): s for s in items(self.data["sources"], 100)}
        for doc in items(self.data["documents"], 6):
            meta, origin = object_data(doc["metadata"]), object_data(doc["origin"])
            rows.append({"id": doc["id"], "title": str(meta["title"]) + " — synthèse pédagogique locale",
                "source_url": "documentary-library:" + archive + "/" + str(origin["file"]) + "#" + str(doc["id"]),
                "publisher": "Dossier documentaire fourni", "retrieved_on": self.data["created_on"],
                "excerpt": documentary_text(doc), "rights": meta["rights_policy"], "notion_refs": [],
                "origin": as_plain(origin), "citations": [as_plain(source_index[r]) for r in cast(tuple[str, ...], doc["source_ids"])]})
        return rows

    def public_projection(self) -> dict[str, object]:
        sources: list[dict[str, object]] = []
        for doc in items(self.data["documents"], 6):
            sources.append({"title": str(object_data(doc["metadata"])["title"]) + " — synthèse pédagogique locale",
                "publisher": "Dossier documentaire fourni", "source_url": "", "retrieved_on": self.data["created_on"],
                "rights": object_data(doc["metadata"])["rights_policy"]})
        for source in items(self.data["sources"], 100):
            sources.append({"title": source["title"], "publisher": source["publisher"], "source_url": source["url"],
                "retrieved_on": source["consulted_on"], "rights": source["rights_status"]})
        return {"organization_label": self.label,
            "notice": "Périmètre groupe. Synthèses pédagogiques locales de sources publiques, distinctes de citations primaires. "
                "Les situations construites ne décrivent pas des pratiques individuelles attestées.", "sources": sources}
