"""Static, closed provider schema for a rich COURSE; no local identities."""
from backend.adapters.outbound.openai.schema import validate_openai_strict_schema


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def _string(maximum: int = 4000) -> dict[str, object]:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def _array(item: dict[str, object], maximum: int = 30,
           minimum: int = 1) -> dict[str, object]:
    return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum}


def rich_course_content_schema() -> dict[str, object]:
    """Instance allowlists are checked by Application, not embedded in the SHA."""
    identifier: dict[str, object] = {"type": "string", "pattern": "^[A-Z][A-Z0-9_-]{0,39}$"}
    ids = _array(identifier)
    cell = {"type": "string", "maxLength": 1500}
    table = _object({"columns": _array(_string(2000), 5),
                     "rows": _array(_array(cell, 5), 20)})
    nullable_table = {"anyOf": [table, {"type": "null"}]}
    nullable_evidence = {"anyOf": [
        {"type": "string", "pattern": "^evidence:[0-9a-f]{32}$"},
        {"type": "null"}]}
    chapter = _object({
        "context": _object({"title": _string(200), "text": _string(8000)}),
        "documents": _array(_object({
            "id": identifier, "title": _string(200), "function": _string(200),
            "text": _string(8000), "table": nullable_table,
            "provenance": _object({
                "kind": {"type": "string", "enum": ["LOCAL_FICTION", "SUPPLIED_REFERENCE"]},
                "evidence_id": nullable_evidence})})),
        "parts": _array(_object({
            "id": identifier, "title": _string(200), "document_ids": ids,
            "observation": ids, "analysis": ids, "concept_ids": ids, "reinvestment": ids}), 8),
        "questions": _array(_object({
            "id": identifier, "number": {"type": "integer", "minimum": 1, "maximum": 60},
            "prompt": _string(), "document_ids": _array(identifier, 30, 0),
            "capability_ids": _array({"type": "string", "pattern": "^C(?:[1-9]|1[0-6])$"}, 16),
            "response": _object({
                "kind": {"type": "string", "enum": ["LINES", "TABLE"]},
                "lines": {"type": "integer", "minimum": 1, "maximum": 8},
                "table": nullable_table})}), 60),
        "concepts": _array(_object({
            "id": identifier, "notion": _string(3000), "definition": _string(3000),
            "explanation": _string(3000), "example": _string(3000)})),
        "knowledge_check": ids,
        "transfer": _object({"title": _string(200), "document_ids": ids, "question_ids": ids}),
        "synthesis": _string(8000),
        "teacher_answers": _array(_object({
            "id": identifier, "expected_answer": _string(), "rationale": _string(),
            "vigilance": _string(), "remediation": _string()}), 60),
    })
    schema = _object({"title": _string(200), "course_chapter": chapter,
                      "limitations": _array(_string(500), 15, 0)})
    validate_openai_strict_schema(schema)
    return schema
