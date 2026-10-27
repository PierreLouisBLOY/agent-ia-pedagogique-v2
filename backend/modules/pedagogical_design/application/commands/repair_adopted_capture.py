"""Exact owner-adopted local ID/status transform, never a general repair policy."""
from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from backend.modules.pedagogical_design.application.commands.repair_captured_sections import (
    RepairCapturedSectionIds,
    SectionIdRepair,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

PLAN_SHA256 = "ee6d0fb99e5d498e5175f7f9525d7595850530d3241b0570d9acacf5d72ca5fe"


class RepairAdoptedCapture:
    def __init__(self, plan: Mapping[str, object]) -> None:
        if fingerprint(plan) != PLAN_SHA256:
            raise ValueError("LOCAL_REPAIR_EXACT_ADOPTED_PLAN_REQUIRED")
        # Verify the complete adopted document, then project only business rules.
        # Infrastructure exclusions (including secret-related keys) never enter
        # a business structured value or weaken its safety guard.
        fields = {"section_mapping_already_in_current_scope", "additional_question_mapping",
            "normal_local_candidate_marker"}
        self.plan = freeze_safe_mapping({key: as_plain(plan[key]) for key in fields})

    def execute(self, content: Mapping[str, object]) -> SectionIdRepair:
        original_sections = items(content["sections"], 16)
        section_map = object_data(self.plan["section_mapping_already_in_current_scope"])
        if [row.get("section_id") for row in original_sections] != list(section_map):
            raise ValueError("LOCAL_REPAIR_ORIGINAL_SECTION_SCOPE")
        section_repair = RepairCapturedSectionIds().execute(content)
        repaired = object_data(as_plain(section_repair.content))
        expected_sections = list(object_data(self.plan["section_mapping_already_in_current_scope"]).values())
        if [row["section_id"] for row in items(repaired["sections"])] != expected_sections:
            raise ValueError("LOCAL_REPAIR_SECTION_SCOPE")
        question_map = object_data(self.plan["additional_question_mapping"])
        expected_questions = list(question_map)
        for field in ("questions", "corrections"):
            if [row["question_id"] for row in items(repaired[field])] != expected_questions:
                raise ValueError("LOCAL_REPAIR_QUESTION_SCOPE_OR_LINK")
        if repaired["marking"]:
            raise ValueError("LOCAL_REPAIR_MARKING_SCOPE")

        def ambiguous(value: object, path: tuple[object, ...] = ()) -> bool:
            if isinstance(value, Mapping):
                return any(ambiguous(item, (*path, key)) for key, item in value.items()
                    if not (len(path) == 2 and path[0] in {"questions", "corrections"} and key == "question_id"))
            if isinstance(value, (tuple, list)):
                return any(ambiguous(item, (*path, index)) for index, item in enumerate(value))
            return isinstance(value, str) and any(old in value for old in question_map)

        if ambiguous(repaired):
            raise ValueError("LOCAL_REPAIR_QUESTION_TEXT_REFERENCE_AMBIGUOUS")
        diff = list(cast(list[dict[str, object]], as_plain(section_repair.audit["diff"])))
        for field in ("questions", "corrections"):
            for index, row in enumerate(cast(list[dict[str, object]], repaired[field])):
                old = str(row["question_id"])
                row["question_id"] = question_map[old]
                diff.append({"field_path": [field, index, "question_id"], "before": old, "after": question_map[old]})
        marker = object_data(self.plan["normal_local_candidate_marker"])["text"]
        limitations = repaired["limitations"]
        if not isinstance(limitations, list) or not isinstance(marker, str):
            raise ValueError("LOCAL_REPAIR_LIMITATIONS_SCOPE")
        if any("CANDIDATE" in str(value) for value in limitations):
            raise ValueError("LOCAL_REPAIR_UNEXPECTED_EXISTING_CANDIDATE_MARKER")
        diff.append({"field_path": ["limitations", len(limitations)], "before": None,
            "after": marker, "origin": "LOCAL_APPLICATION_METADATA_NOT_PROVIDER_CONTENT"})
        limitations.append(marker)
        if len(diff) != 13:
            raise ValueError("LOCAL_REPAIR_EXACT_DIFF_REQUIRED")
        restored = object_data(as_plain(repaired))
        for row in reversed(diff):
            path = cast(list[object], row["field_path"])
            field, index = str(path[0]), cast(int, path[1])
            if len(path) == 2:
                cast(list[object], restored[field]).pop(index)
            else:
                cast(list[dict[str, object]], restored[field])[index][str(path[2])] = row["before"]
        if restored != as_plain(content):
            raise ValueError("LOCAL_REPAIR_OTHER_CONTENT_CHANGED")
        mapping = {**object_data(section_repair.audit["mapping"]), **question_map}
        audit = {"operation": "LOCAL_CAPTURE_ADOPTED_ID_AND_STATUS_REPAIR_1",
            "approved_plan_sha256": PLAN_SHA256, "diff": diff, "mapping": mapping,
            "mapping_sha256": fingerprint(mapping), "provider_content_before_sha256": fingerprint(content),
            "provider_content_after_sha256": fingerprint(repaired), "original_text_and_order_preserved": True,
            "local_metadata_additions": 1, "semantic_completion": "NOT_PERFORMED"}
        return SectionIdRepair(freeze_safe_mapping(repaired), freeze_safe_mapping(audit))
