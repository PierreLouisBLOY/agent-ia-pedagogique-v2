"""Static, closed provider schema for a rich COURSE; no local identities."""
from backend.adapters.outbound.openai.schema import validate_openai_strict_schema
from backend.modules.pedagogical_design.contracts.dto.course_table import (
    MAX_CELL_LENGTH,
    MAX_COLUMNS,
    MAX_HEADER_LENGTH,
    MAX_ROWS,
)


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def _string(maximum: int = 4000) -> dict[str, object]:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def _array(item: dict[str, object], maximum: int = 30,
           minimum: int = 1) -> dict[str, object]:
    return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum}


def _rich_course_content_schema(*, notion_alias: bool, real_organization: bool = False,
                                progressive: bool = False) -> dict[str, object]:
    """Instance allowlists are checked by Application, not embedded in the SHA."""
    identifier: dict[str, object] = {"type": "string", "pattern": "^[A-Z][A-Z0-9_-]{0,39}$"}
    ids = _array(identifier)
    cell = {"type": "string", "maxLength": MAX_CELL_LENGTH}
    nullable_table = {"anyOf": [
        *[_object({"columns": _array(_string(MAX_HEADER_LENGTH), width, width),
                   "rows": _array(_array(cell, width, width), MAX_ROWS)})
          for width in range(1, MAX_COLUMNS + 1)],
        {"type": "null"},
    ]}
    nullable_evidence = {"anyOf": [
        {"type": "string", "pattern": "^evidence:[0-9a-f]{32}$"},
        {"type": "null"}]}
    qid: dict[str, object] = {"type": "string", "pattern": "^Q([1-9]|[1-5][0-9]|60)$"} if progressive else identifier
    questions = _array(qid)
    transfer = _object({"title": _string(200), "document_ids": ids, "question_ids": questions})
    chapter = _object({
        "context": _object({"title": _string(200), "text": _string(8000),
                            **({"organization_id": _string(200)} if real_organization else {})}),
        "documents": _array(_object({
            "id": identifier, "title": _string(200), "function": _string(200),
            "text": _string(8000), "table": nullable_table,
            "provenance": _object({
                "kind": {"type": "string", "enum": ["LOCAL_FICTION", "SUPPLIED_REFERENCE"]},
                "evidence_id": nullable_evidence})})),
        "parts": _array(_object({
            "id": identifier, "title": _string(200), "document_ids": _array(identifier, 2) if progressive else ids,
            **({"formalization": {"type": "string", "enum": [
                "AFTER_DOCUMENTS", "AFTER_OBSERVATION", "AFTER_ANALYSIS"]}} if progressive else {}),
            "observation": questions, "analysis": questions,
            "concept_ids": _array(identifier, 3) if progressive else ids, "reinvestment": questions}), 8),
        "questions": _array(_object({
            "id": qid, "number": {"type": "integer", "minimum": 1, "maximum": 60},
            "prompt": _string(), "document_ids": _array(identifier, 30, 0),
            "capability_ids": _array({"type": "string", "pattern": "^C(?:[1-9]|1[0-6])$"}, 16),
            "response": _object({
                "kind": {"type": "string", "enum": ["LINES", "TABLE"]},
                "lines": {"type": "integer", "minimum": 1, "maximum": 8},
                "table": nullable_table})}), 60),
        "concepts": _array(_object({
            "id": identifier,
            ("notion_id" if notion_alias else "notion"): (
                {"type": "string", "pattern": "^N(?:[1-9]|1[0-6])$"} if notion_alias else _string(3000)),
            "definition": _string(3000),
            "explanation": _string(3000), "example": _string(3000)})),
        "knowledge_check": questions,
        "transfer": _array(transfer, 2, 2) if progressive else transfer,
        "synthesis": _string(8000),
        "teacher_answers": _array(_object({
            "id": qid, "expected_answer": _string(), "rationale": _string(),
            "vigilance": _string(), "remediation": _string()}), 60),
    })
    schema = _object({"title": _string(200), "course_chapter": chapter,
                      "limitations": _array(_string(500), 15, 0)})
    validate_openai_strict_schema(schema)
    return schema


def rich_course_content_schema(*, progressive: bool = False) -> dict[str, object]:
    """Closed rich schema with rectangular tables of one to five columns."""
    return _rich_course_content_schema(notion_alias=False, progressive=progressive)


def rich_course_notion_content_schema(*, progressive: bool = False) -> dict[str, object]:
    """P0-COURSE-RICH-CONTENT-2.0; aliases are bound against the exact selection."""
    return _rich_course_content_schema(notion_alias=True, progressive=progressive)


def rich_course_real_content_schema(*, progressive: bool = False) -> dict[str, object]:
    """Explicit real-thread successor; historical schemas keep their fields."""
    return _rich_course_content_schema(notion_alias=True, real_organization=True, progressive=progressive)
