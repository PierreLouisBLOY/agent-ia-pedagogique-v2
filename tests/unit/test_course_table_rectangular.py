"""Regression for strict rectangular course tables and lossless response-space repair."""
import copy

import pytest

from backend.adapters.outbound.generation.openai.p0_course_content_schema import (
    rich_course_content_schema,
    rich_course_notion_content_schema,
)
from backend.adapters.outbound.openai.schema import validate_openai_strict_schema
from backend.modules.pedagogical_design.application.commands.repair_course_response_tables import (
    RepairCourseResponseTables,
)
from backend.modules.pedagogical_design.contracts.dto.course_table import validate_course_table


def content():
    return {"course_chapter": {"questions": [{"id": "Q1", "prompt": "Conserver la consigne",
        "response": {"kind": "TABLE", "lines": 4, "table": {
            "columns": ["Fait", "Interprétation"], "rows": [["", "", ""]] * 4}}}],
        "documents": [{"text": "Conserver le document"}],
        "teacher_answers": [{"expected_answer": "Conserver le corrigé"}]}}


@pytest.mark.parametrize("factory", [rich_course_content_schema, rich_course_notion_content_schema])
def test_strict_schema_enforces_one_cell_per_header(factory):
    schema = factory()
    validate_openai_strict_schema(schema)
    chapter = schema["properties"]["course_chapter"]["properties"]
    for nullable in (chapter["documents"]["items"]["properties"]["table"],
                     chapter["questions"]["items"]["properties"]["response"]["properties"]["table"]):
        branches = [b for b in nullable["anyOf"] if b.get("type") != "null"]
        assert len(branches) == 5
        for width, branch in enumerate(branches, 1):
            columns = branch["properties"]["columns"]
            row = branch["properties"]["rows"]["items"]
            assert columns["minItems"] == columns["maxItems"] == width
            assert row["minItems"] == row["maxItems"] == width


def test_repair_is_reversible_without_changing_any_text():
    original = content()
    before = copy.deepcopy(original)
    repaired = RepairCourseResponseTables().execute(original)
    assert original == before
    assert repaired.audit["removed_empty_cells"] == 4
    assert repaired.audit["text_and_order_preserved"] is True
    assert repaired.content["course_chapter"]["documents"] == before["course_chapter"]["documents"]
    assert repaired.content["course_chapter"]["teacher_answers"] == before["course_chapter"]["teacher_answers"]
    table = repaired.content["course_chapter"]["questions"][0]["response"]["table"]
    validate_course_table(table)
    with pytest.raises(ValueError, match="NOT_REQUIRED"):
        RepairCourseResponseTables().execute(repaired.content)


@pytest.mark.parametrize("row", [["", "", "réponse"], ["", "", " "], [""]])
def test_no_content_or_missing_cell_is_guessed(row):
    original = content()
    original["course_chapter"]["questions"][0]["response"]["table"]["rows"] = [row]
    with pytest.raises(ValueError):
        RepairCourseResponseTables().execute(original)


def test_validator_still_rejects_surplus_cells():
    with pytest.raises(ValueError, match="COURSE_CHAPTER_TABLE"):
        validate_course_table({"columns": ["A", "B"], "rows": [["", "", ""]]})
