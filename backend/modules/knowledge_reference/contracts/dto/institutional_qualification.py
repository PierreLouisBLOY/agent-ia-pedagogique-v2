"""Versioned proof on existing institutional identities; lifecycle is not admission."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    items,
    nonempty,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

CONTRACT = "INSTITUTIONAL-QUALIFICATION-1.0"
DISPOSITIONS = frozenset(
    {
        "VERIFIED_EXPLICIT",
        "VERIFIED_IMPLICIT",
        "NO_APPLICABLE_FRAMEWORK",
        "SOURCE_GAP",
        "HUMAN_REVIEW_REQUIRED",
    }
)
FIELDS = {
    "contract_id",
    "owner_decision_sha256",
    "documents",
    "versions",
    "elements",
    "attachments",
    "notions",
    "regulatory_context",
}


def sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("INSTITUTIONAL_SHA256")
    return value


@dataclass(frozen=True, slots=True)
class InstitutionalQualification:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(self.data, FIELDS)
        if data["contract_id"] != CONTRACT:
            raise ValueError("INSTITUTIONAL_QUALIFICATION_CONTRACT")
        sha(data["owner_decision_sha256"])
        documents = items(data["documents"], 8)
        versions = items(data["versions"], 16)
        elements = items(data["elements"], 3000)
        attachments = items(data["attachments"], 6000)
        notions = items(data["notions"], 628)
        if not documents or not versions or not elements or len(notions) != 628:
            raise ValueError("INSTITUTIONAL_QUALIFICATION_BOUNDS")

        def unique(rows: tuple[dict[str, object], ...], key: str) -> set[str]:
            refs = [nonempty(row[key], 200) for row in rows]
            if len(refs) != len(set(refs)):
                raise ValueError("INSTITUTIONAL_DUPLICATE_ID")
            return set(refs)

        doc_ids = unique(documents, "id")
        unique(documents, "candidate_id")
        version_ids = unique(versions, "id")
        unique(versions, "frame")
        element_ids = unique(elements, "id")
        notion_ids = unique(notions, "notion_ref")
        unique(attachments, "id")
        for row in documents:
            object_data(
                row,
                {
                    "id",
                    "candidate_id",
                    "title",
                    "url",
                    "sha256",
                    "publication_date",
                    "source_ref",
                    "source_name",
                    "provenance",
                    "pages",
                },
            )
            sha(row["sha256"])
            if (
                row["candidate_id"] not in {"A01", "A02", "A03", "A04B"}
                or type(row["pages"]) is not int
                or not 1 <= row["pages"] <= 200
            ):
                raise ValueError("INSTITUTIONAL_DOCUMENT_SCOPE")
            for key in (
                "title",
                "url",
                "publication_date",
                "source_ref",
                "source_name",
                "provenance",
            ):
                nonempty(row[key], 2000)
        for row in versions:
            object_data(
                row,
                {
                    "id",
                    "framework_ref",
                    "frame",
                    "version_label",
                    "publication_date",
                    "document_ref",
                },
            )
            if row["document_ref"] not in doc_ids:
                raise ValueError("INSTITUTIONAL_VERSION_DOCUMENT")
            for value in row.values():
                nonempty(value, 2000)
        by_element = {str(row["id"]): row for row in elements}
        by_version = {str(row["id"]): row for row in versions}
        for row in elements:
            object_data(
                row,
                {
                    "id",
                    "version_ref",
                    "parent_ref",
                    "element_type",
                    "official_code",
                    "official_label",
                    "official_text",
                    "document_ref",
                    "page",
                    "locator",
                    "position",
                },
            )
            if (
                row["version_ref"] not in version_ids
                or row["document_ref"] not in doc_ids
                or (row["parent_ref"] is not None and row["parent_ref"] not in element_ids)
            ):
                raise ValueError("INSTITUTIONAL_ELEMENT_BINDING")
            parent = by_element.get(str(row["parent_ref"]))
            if row["document_ref"] != by_version[str(row["version_ref"])]["document_ref"]:
                raise ValueError("INSTITUTIONAL_CROSS_DOCUMENT_ELEMENT")
            if parent is not None and parent["version_ref"] != row["version_ref"]:
                raise ValueError("INSTITUTIONAL_CROSS_PROGRAMME_PARENT")
            if row["element_type"] not in {
                "THEME",
                "QUESTION",
                "PROCESS",
                "ACTIVITY",
                "CAPACITY",
                "COMPETENCY",
                "KNOWLEDGE",
                "OBJECTIVE",
                "OTHER",
            }:
                raise ValueError("INSTITUTIONAL_ELEMENT_TYPE")
            document = next(d for d in documents if d["id"] == row["document_ref"])
            page, pages = row["page"], document["pages"]
            if (
                not isinstance(page, int)
                or isinstance(page, bool)
                or not isinstance(pages, int)
                or not 1 <= page <= pages
            ):
                raise ValueError("INSTITUTIONAL_LOCATOR")
            position = row["position"]
            if type(position) is not int or not 0 <= position <= 10000:
                raise ValueError("INSTITUTIONAL_ELEMENT_POSITION")
            if row["official_code"] is not None:
                nonempty(row["official_code"], 200)
            for key in ("official_label", "official_text", "locator"):
                nonempty(row[key], 16000)
            visited = {str(row["id"])}
            while parent is not None:
                if str(parent["id"]) in visited:
                    raise ValueError("INSTITUTIONAL_PARENT_CYCLE")
                visited.add(str(parent["id"]))
                parent = by_element.get(str(parent["parent_ref"]))
        for row in attachments:
            object_data(
                row,
                {
                    "id",
                    "notion_ref",
                    "element_ref",
                    "disposition",
                    "justification",
                    "importance",
                    "official_depth",
                    "pedagogical_depth",
                    "validated_by",
                    "validated_at",
                    "evidence_ref",
                },
            )
            if (
                row["notion_ref"] not in notion_ids
                or row["element_ref"] not in element_ids
                or row["disposition"] not in {"VERIFIED_EXPLICIT", "VERIFIED_IMPLICIT"}
            ):
                raise ValueError("INSTITUTIONAL_ATTACHMENT_BINDING")
            for key in ("justification", "validated_by", "validated_at", "evidence_ref"):
                nonempty(row[key], 8000)
            if row["pedagogical_depth"] not in {"DISCOVERY", "APPLICATION", "ANALYSIS"}:
                raise ValueError("INSTITUTIONAL_PEDAGOGICAL_DEPTH")
            if row["official_depth"] is not None:
                nonempty(row["official_depth"], 2000)
            if row["importance"] is not None:
                nonempty(row["importance"], 200)
        for row in notions:
            object_data(
                row,
                {
                    "notion_ref",
                    "label",
                    "disposition",
                    "reason",
                    "attachment_refs",
                    "candidate_scopes",
                },
            )
            if row["disposition"] not in DISPOSITIONS:
                raise ValueError("INSTITUTIONAL_DISPOSITION")
            nonempty(row["reason"], 8000)
            nonempty(row["label"], 1000)
            scopes = row["candidate_scopes"]
            if (
                not isinstance(scopes, (tuple, list))
                or len(scopes) > 16
                or any(not isinstance(s, str) or not s for s in scopes)
            ):
                raise ValueError("INSTITUTIONAL_CANDIDATE_SCOPES")
            refs = row["attachment_refs"]
            if (
                not isinstance(refs, (tuple, list))
                or any(not isinstance(r, str) for r in refs)
                or len(set(refs)) != len(refs)
                or set(refs)
                != {a["id"] for a in attachments if a["notion_ref"] == row["notion_ref"]}
            ):
                raise ValueError("INSTITUTIONAL_NOTION_COVERAGE")
            linked = [a for a in attachments if a["notion_ref"] == row["notion_ref"]]
            expected = (
                "VERIFIED_EXPLICIT"
                if any(a["disposition"] == "VERIFIED_EXPLICIT" for a in linked)
                else "VERIFIED_IMPLICIT"
                if linked
                else None
            )
            if (expected is not None and row["disposition"] != expected) or (
                str(row["disposition"]).startswith("VERIFIED_") and not refs
            ):
                raise ValueError("INSTITUTIONAL_UNSUPPORTED_CLAIM")
        for row in items(data["regulatory_context"], 8):
            object_data(row, {"id", "url", "scope", "precedence"})
            for value in row.values():
                nonempty(value, 4000)
        if len(encoded(data)) > 12 * 1024 * 1024:
            raise ValueError("INSTITUTIONAL_QUALIFICATION_SIZE")
        # The corpus contains 628 notions. Apply the unchanged generic scanner
        # to each closed, bounded row; do not enlarge its shared limits.
        frozen: dict[str, object] = {
            "contract_id": CONTRACT,
            "owner_decision_sha256": data["owner_decision_sha256"],
        }
        for key in (
            "documents",
            "versions",
            "elements",
            "attachments",
            "notions",
            "regulatory_context",
        ):
            frozen[key] = tuple(freeze_safe_mapping(row) for row in items(data[key], 6000))
        object.__setattr__(self, "data", MappingProxyType(frozen))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))
