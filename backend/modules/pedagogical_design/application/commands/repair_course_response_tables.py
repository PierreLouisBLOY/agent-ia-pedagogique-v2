"""Remove only surplus empty cells after named columns in student response tables."""
from collections.abc import Mapping
from typing import cast

from backend.modules.pedagogical_design.application.commands.repair_captured_sections import (
    SectionIdRepair,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.course_table import validate_course_table


class RepairCourseResponseTables:
    def execute(self, content: Mapping[str, object]) -> SectionIdRepair:
        original = object_data(as_plain(content))
        repaired = object_data(as_plain(content))
        chapter = object_data(repaired["course_chapter"])
        questions = cast(list[dict[str, object]], chapter["questions"])
        changes: list[dict[str, object]] = []
        for index, question in enumerate(questions):
            response = object_data(question["response"])
            table = response["table"]
            if table is None:
                continue
            data = object_data(table, {"columns", "rows"})
            columns, rows = data["columns"], data["rows"]
            if not isinstance(columns, list) or not isinstance(rows, list):
                raise ValueError("COURSE_RESPONSE_TABLE_REPAIR_AMBIGUOUS")
            width = len(columns)
            new_rows = []
            for row_index, row in enumerate(rows):
                if not isinstance(row, list) or len(row) < width:
                    raise ValueError("COURSE_RESPONSE_TABLE_REPAIR_AMBIGUOUS")
                extra = row[width:]
                if extra:
                    if response["kind"] != "TABLE" or any(cell != "" for cell in extra):
                        raise ValueError("COURSE_RESPONSE_TABLE_REPAIR_CONTENT_LOSS")
                    changes.append({"question_index": index, "question_id": question["id"],
                        "row_index": row_index, "before": list(row), "after": row[:width]})
                new_rows.append(row[:width])
            fixed = {"columns": columns, "rows": new_rows}
            validate_course_table(fixed)
            response["table"] = fixed
            question["response"] = response
        if not changes:
            raise ValueError("COURSE_RESPONSE_TABLE_REPAIR_NOT_REQUIRED")
        restored = object_data(as_plain(repaired))
        restored_questions = cast(list[dict[str, object]],
            object_data(restored["course_chapter"])["questions"])
        for change in changes:
            response = object_data(restored_questions[cast(int, change["question_index"])]["response"])
            table = object_data(response["table"])
            cast(list[object], table["rows"])[cast(int, change["row_index"])] = change["before"]
        if restored != original:
            raise ValueError("COURSE_RESPONSE_TABLE_REPAIR_TEXT_CHANGED")
        return SectionIdRepair(repaired, {
            "operation": "LOCAL_SURPLUS_EMPTY_RESPONSE_CELLS_1",
            "provider_content_before_sha256": fingerprint(original),
            "provider_content_after_sha256": fingerprint(repaired),
            "diff": changes,
            "mapping_sha256": fingerprint(changes),
            "removed_empty_cells": sum(
                len(cast(list[object], c["before"])) - len(cast(list[object], c["after"]))
                for c in changes),
            "text_and_order_preserved": True,
            "semantic_completion": "NOT_PERFORMED",
        })
