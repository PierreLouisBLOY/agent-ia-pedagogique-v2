"""Strict provider projection of the versioned exercise content only."""
from backend.adapters.outbound.openai.schema import validate_openai_strict_schema
from backend.modules.pedagogical_design.contracts.dto.section_identity import QUESTION_ID_PATTERN


def exercise_content_schema(*, case_study: bool = False) -> dict[str, object]:
    def obj(properties: dict[str, object]) -> dict[str, object]:
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

    def array(item: dict[str, object]) -> dict[str, object]:
        return {"type": "array", "items": item}

    string: dict[str, object] = {"type": "string"}
    strings = array(string)
    qid = {"type": "string", "pattern": QUESTION_ID_PATTERN}
    provenance = {"provenance": {"type": "string", "enum": ["LOCAL_FICTION", "SUPPLIED_REFERENCE"]},
                  "evidence_id": {"type": ["string", "null"]}}
    exercise = obj({
        "instructions": string,
        "objectives": array(obj({"capability_id": string, "goal": string})),
        "situation": obj({"text": string, **provenance}),
        "documents": array(obj({"document_id": string, "title": string, "text": string, **provenance})),
        "questions": array(obj({"question_id": qid, "stage": {"type": "string", "enum": ["OBSERVE", "ANALYSE", "APPLY"]},
                                "prompt": string, "capability_ids": strings, "document_ids": strings,
                                "success_criteria": strings, "answer_lines": {"type": "integer"}})),
        "teacher_answers": array(obj({"question_id": qid, "expected_answer": string, "rationale": string,
                                      "vigilance": string, "remediation": string})),
    })
    if case_study:
        from backend.modules.pedagogical_design.contracts.dto.case_study import case_study_schema
        props = exercise["properties"]
        assert isinstance(props, dict)
        props["case_study"] = case_study_schema()
        exercise = obj(props)
    schema = obj({"title": string, "exercise": exercise, "limitations": strings})
    validate_openai_strict_schema(schema)
    return schema
