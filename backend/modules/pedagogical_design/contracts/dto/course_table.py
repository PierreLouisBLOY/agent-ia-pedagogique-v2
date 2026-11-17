"""Canonical rectangular table limits shared by chapter validation and provider schema."""
from collections.abc import Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import nonempty, object_data

MAX_COLUMNS = 5
MAX_ROWS = 20
MAX_CELL_LENGTH = 1500
MAX_HEADER_LENGTH = 2000


def validate_course_table(value: object) -> Mapping[str, object] | None:
    if value is None:
        return None
    data = object_data(value, {"columns", "rows"})
    raw_columns = data["columns"]
    if not isinstance(raw_columns, (tuple, list)) or not 1 <= len(raw_columns) <= MAX_COLUMNS:
        raise ValueError("COURSE_CHAPTER_LIST")
    columns = tuple(nonempty(v, MAX_HEADER_LENGTH) for v in raw_columns)
    if len(columns) != len(set(columns)):
        raise ValueError("COURSE_CHAPTER_DUPLICATE")
    rows = data["rows"]
    if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("COURSE_CHAPTER_TABLE")
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != len(columns):
            raise ValueError("COURSE_CHAPTER_TABLE")
        if any(not isinstance(cell, str) or len(cell) > MAX_CELL_LENGTH for cell in row):
            raise ValueError("COURSE_CHAPTER_TABLE")
    return data
