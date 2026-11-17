"""Apply an explicit owner decision to one exact chapter, without official promotion."""

import re
from collections.abc import Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)


class ReadOwnerLocalChapterLinks:
    def __init__(self, decision: Mapping[str, object]) -> None:
        self.data = object_data(
            decision,
            {
                "schema",
                "status",
                "context_sha256",
                "reference_scope_sha256",
                "native_qualification_sha256",
                "native_owner_admission_sha256",
                "program_version",
                "question_ref",
                "links",
                "owner_statement",
            },
        )
        if (
            self.data["schema"] != "OWNER-LOCAL-CHAPTER-LINKS-1.0"
            or self.data["status"] != "OWNER_ADOPTED"
        ):
            raise ValueError("OWNER_LOCAL_CHAPTER_DECISION_REQUIRED")
        for key in (
            "context_sha256",
            "reference_scope_sha256",
            "native_qualification_sha256",
            "native_owner_admission_sha256",
        ):
            if re.fullmatch("[a-f0-9]{64}", str(self.data[key])) is None:
                raise ValueError("OWNER_LOCAL_CHAPTER_IDENTITY")
        self.links = items(self.data["links"], 3)
        if not self.links or len({r.get("notion_ref") for r in self.links}) != len(self.links):
            raise ValueError("OWNER_LOCAL_CHAPTER_LINKS")
        for row in self.links:
            row = object_data(row, {"notion_ref", "source_wording"})
            if (
                not isinstance(row["notion_ref"], str)
                or not isinstance(row["source_wording"], str)
                or not row["source_wording"]
            ):
                raise ValueError("OWNER_LOCAL_CHAPTER_LINKS")
        if not isinstance(self.data["owner_statement"], str) or not self.data["owner_statement"]:
            raise ValueError("OWNER_LOCAL_CHAPTER_DECISION_REQUIRED")
        self.sha256 = fingerprint(self.data)

    def execute(
        self, context: Mapping[str, object], native: Mapping[str, object]
    ) -> Mapping[str, object]:
        local = object_data(as_plain(context))
        local["institutional_resolution"] = None
        if fingerprint(local) != self.data["context_sha256"]:
            return native
        result = object_data(as_plain(native))
        if result.get("status") == "RESOLVED_ADMITTED":
            return native
        expected_gaps = {
            "NOTION_ATTACHMENT_NOT_ADMITTED:" + str(row["notion_ref"]) for row in self.links
        }
        native_gaps = result.get("gaps")
        if not isinstance(native_gaps, (list, tuple)) or set(native_gaps) != expected_gaps:
            raise ValueError("OWNER_LOCAL_CHAPTER_UNCOVERED_GAP")
        if (
            result.get("qualification_sha256") != self.data["native_qualification_sha256"]
            or result.get("owner_admission_sha256") != self.data["native_owner_admission_sha256"]
            or result.get("program_version") != self.data["program_version"]
            or object_data(result.get("question", {})).get("id") != self.data["question_ref"]
            or fingerprint(result.get("reference_scope")) != self.data["reference_scope_sha256"]
        ):
            raise ValueError("OWNER_LOCAL_CHAPTER_NATIVE_IDENTITY_CHANGED")
        selected = object_data(local["institutional"])
        notions = selected["notion_refs"]
        if not isinstance(notions, (list, tuple)) or not {
            row["notion_ref"] for row in self.links
        }.issubset(set(notions)):
            raise ValueError("OWNER_LOCAL_CHAPTER_NOTION_SELECTION")
        wording = str(object_data(result["question"]).get("official_text", "")).casefold()
        for row in self.links:
            if (
                re.search(
                    r"(?<!\w)" + re.escape(str(row["source_wording"]).casefold()) + r"(?!\w)",
                    wording,
                )
                is None
            ):
                raise ValueError("OWNER_LOCAL_CHAPTER_SOURCE_WORDING_MISSING")
        result["native_institutional_resolution"] = object_data(as_plain(native))
        result["local_attachment_admission"] = {
            "contract_id": "OWNER-LOCAL-CHAPTER-LINKS-1.0",
            "decision_sha256": self.sha256,
            "context_sha256": self.data["context_sha256"],
            "links": as_plain(self.links),
            "authority": "OWNER_LOCAL_CHAPTER_ONLY",
            "official": False,
        }
        links = list(items(result["attachments"], 128))
        links.extend(
            {
                "id": "owner-local:" + fingerprint(row)[:32],
                "notion_ref": row["notion_ref"],
                "element_ref": self.data["question_ref"],
                "disposition": "OWNER_LOCAL_ADMITTED",
                "justification": "Correspondance p\u00e9dagogique locale adopt\u00e9e : "
                + str(row["source_wording"]),
                "owner_decision_sha256": self.sha256,
                "official": False,
            }
            for row in self.links
        )
        result["attachments"] = links
        result["gaps"] = []
        result["status"] = "RESOLVED_ADMITTED"
        # This is a local permission, not the original A admission. Existing
        # authority-layer guards consequently retain institutional UNVERIFIED.
        result["native_owner_admission_sha256"] = result["owner_admission_sha256"]
        result["owner_admission_sha256"] = self.sha256
        result["authority_scope"] = "OWNER_LOCAL_CHAPTER_ONLY"
        return result
