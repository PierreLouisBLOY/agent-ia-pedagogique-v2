"""Mechanical ID-only derivation of simple captured content, never generation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.section_identity import valid_section_id
from backend.shared_kernel._safe_data import freeze_safe_mapping

CONTENT_FIELDS = {"title", "sections", "questions", "corrections", "marking", "limitations"}


@dataclass(frozen=True, slots=True)
class SectionIdRepair:
    content: Mapping[str, object] = field(repr=False)
    audit: Mapping[str, object]


def inspect_section_ids(content: Mapping[str, object]) -> dict[str, object]:
    data = object_data(content, CONTENT_FIELDS)
    sections = items(data["sections"], 16)
    values = [row.get("section_id") for row in sections]
    return {"section_count": len(sections), "section_ids": values,
        "faults": [{"index": index, "section_id": value} for index, value in enumerate(values)
                   if not valid_section_id(value)],
        "question_count": len(items(data["questions"], 60)),
        "question_ids": [row.get("question_id") for row in items(data["questions"], 60)],
        "correction_count": len(items(data["corrections"], 60)),
        "correction_question_ids": [row.get("question_id") for row in items(data["corrections"], 60)],
        "marking_count": len(items(data["marking"], 60)),
        "formal_section_id_references": "NONE_IN_CLOSED_SIMPLE_CONTENT_CONTRACT"}


class RepairCapturedSectionIds:
    def execute(self, content: Mapping[str, object]) -> SectionIdRepair:
        data = object_data(as_plain(content), CONTENT_FIELDS)
        for field_name, fields in (
            ("questions", {"question_id", "prompt", "options"}),
            ("corrections", {"question_id", "expected_answer", "rationale"}),
            ("marking", {"question_id", "points", "criteria"}),
        ):
            for row in items(data[field_name], 60):
                object_data(row, fields)
        sections = items(data["sections"], 16)
        identities: list[str] = []
        for row in sections:
            row = object_data(row, {"section_id", "heading", "text"})
            value = row["section_id"]
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ValueError("CAPTURE_SECTION_ID_AMBIGUOUS")
            identities.append(value)
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("CAPTURE_SECTION_DUPLICATE_OR_ABSENT")
        changed = [value for value in identities if not valid_section_id(value)]

        def references(value: object, path: tuple[object, ...] = ()) -> bool:
            if isinstance(value, Mapping):
                return any(references(item, (*path, key)) for key, item in value.items()
                    if not (len(path) == 2 and path[0] == "sections" and key == "section_id"))
            if isinstance(value, (list, tuple)):
                return any(references(item, (*path, index)) for index, item in enumerate(value))
            return isinstance(value, str) and any(old in value for old in changed)

        # No formal cross-reference to section_id exists in this closed contract.
        # A textual occurrence is ambiguous: never rewrite prose to guess intent.
        if references(data):
            raise ValueError("CAPTURE_SECTION_TEXTUAL_REFERENCE_AMBIGUOUS")
        used = {value for value in identities if valid_section_id(value)}
        mapping: dict[str, str] = {}
        for old in identities:
            if valid_section_id(old):
                continue
            candidate = old.upper()
            if not valid_section_id(candidate):
                raise ValueError("CAPTURE_SECTION_ID_NOT_CASE_REPAIRABLE")
            if candidate in used:
                raise ValueError("CAPTURE_SECTION_MAPPING_COLLISION")
            used.add(candidate)
            mapping[old] = candidate
        before = cast(dict[str, object], as_plain(data))
        repaired = cast(dict[str, object], as_plain(data))
        rows = cast(list[dict[str, object]], repaired["sections"])
        diff = []
        for index, row in enumerate(rows):
            old = str(row["section_id"])
            if old in mapping:
                row["section_id"] = mapping[old]
                diff.append({"field_path": ["sections", index, "section_id"], "before": old, "after": mapping[old]})
        unchanged = cast(dict[str, object], as_plain(repaired))
        for index, row in enumerate(cast(list[dict[str, object]], unchanged["sections"])):
            row["section_id"] = identities[index]
        if unchanged != before or len(set(mapping.values())) != len(mapping):
            raise ValueError("CAPTURE_SECTION_REPAIR_CONTENT_CHANGED")
        audit = {"operation": "LOCAL_CAPTURE_SECTION_ID_REPAIR_1",
            "provider_content_before_sha256": fingerprint(before),
            "provider_content_after_sha256": fingerprint(repaired), "diff": diff,
            "mapping": mapping, "mapping_sha256": fingerprint(mapping),
            "content_and_order_preserved": True, "semantic_completion": "NOT_PERFORMED"}
        return SectionIdRepair(freeze_safe_mapping(repaired), freeze_safe_mapping(audit))
