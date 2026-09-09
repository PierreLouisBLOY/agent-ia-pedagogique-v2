"""Closed R3 PREPARE wire shape; decoding has no validation/publication authority."""
from __future__ import annotations

import json
import re
from typing import Any, NoReturn, cast

from backend.adapters.outbound.generation.parse_diagnostic import (
    ParseCode,
    ParseDiagnostic,
    ParseStage,
)
from backend.agent_runtime.agents.generation import (
    GenerationOperation,
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
)

FIELDS = ("questions", "correction", "marking", "case_data", "limitations")
GROUPS = ("stable_resources", "stable_uses", "current_assets", "current_liabilities",
          "cash_assets", "cash_liabilities")
MAX_BYTES = 128 * 1024
INSTRUCTIONS = """
For this PREPARE_SUPPLEMENTS transformation return the five-field JSON object
directly, exactly as the output schema specifies. Do not return outcome,
sections, R3_RESULT_JSON, a bundle, Markdown fences or any other wrapper.
Use the supplied production_ref and version_ref in correction and marking.
Copy exact source locators from the supplied subject; never rewrite the subject.
Keep source_value in its explicitly located source unit and amount in EUR;
use canonical two-decimal strings. Return explicit structured calculations,
not executable text. State uncertainty in limitations. This is an unvalidated
candidate: do not claim validation, review, approval or publication.
"""


def is_prepare_request(request: GenerationPortRequest) -> bool:
    return (request.operation is GenerationOperation.TRANSFORM
            and request.objective == "PREPARE_SUPPLEMENTS"
            and request.production_kind == "ASSESSMENT"
            and request.expected_sections == ("R3_RESULT_JSON",)
            and request.output_contract.get("contract_id") == "R3-TRANSFORMATION-1.0")


def _object(**properties: object) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def _ref(name: str) -> dict[str, str]:
    return {"$ref": "#/$defs/" + name}


def _array(item: object, maximum: int) -> dict[str, object]:
    return {"type": "array", "items": item, "maxItems": maximum}


def prepare_output_schema() -> dict[str, object]:
    """A fresh schema each time. Cross-field arithmetic stays exclusively in CAP-A01."""
    text = {"type": "string", "minLength": 1, "maxLength": 4000}
    name = {"type": "string", "minLength": 1, "maxLength": 80}
    money = {"type": "string", "pattern": r"^-?(?:0|[1-9][0-9]{0,8})\.[0-9]{2}$"}
    dossier = {"type": "string", "enum": ["DOSSIER_1", "DOSSIER_2", "DOSSIER_3"]}
    defs: dict[str, Any] = {
        "locator": _object(section_id=name, start={"type": "integer", "minimum": 0},
                           end={"type": "integer", "minimum": 1}, exact_text=text),
        "question": _object(question_id=name, dossier_id=dossier, locator=_ref("locator"),
                            instruction=text, expected_skill=text,
                            calculation_refs=_array(name, 60)),
        "calculation": _object(case_id=name, metric={"type": "string", "enum": ["FRNG", "BFR", "TN"]},
                               value=money, locator=_ref("locator"), expression=_ref("expression1")),
        "answer": _object(question_id=name, expected_answer=text, rationale=text,
                          calculations=_array(_ref("calculation"), 60)),
        "criterion": _object(criterion_id=name, description=text, points=money),
        "marked_question": _object(question_id=name, points=money,
                                   criteria=_array(_ref("criterion"), 8)),
        "dossier": _object(dossier_id=dossier,
                           duration_minutes={"type": "integer", "minimum": 1, "maximum": 60},
                           questions=_array(_ref("marked_question"), 30)),
        "component": _object(component_id=name, source_value=money, amount=money),
        "case": _object(case_id=name,
                        components=_object(**{key: _array(_ref("component"), 16) for key in GROUPS}),
                        totals=_object(**dict.fromkeys(GROUPS, money)),
                        computed=_object(**dict.fromkeys(("FRNG", "BFR", "TN"), money))),
    }
    # Same four-level expression bound as CAP-A01; no unbounded recursive schema.
    for depth in range(4, 0, -1):
        leaf = _object(ref=name)
        defs["expression" + str(depth)] = leaf if depth == 4 else {"anyOf": [
            leaf, _object(op={"type": "string", "enum": ["ADD", "SUB"]},
                          operands={"type": "array", "minItems": 2, "maxItems": 16,
                                    "items": _ref("expression" + str(depth + 1))})]}
    root = _object(
        questions=_array(_ref("question"), 30),
        correction=_object(production_ref={"type": "string", "pattern": "^prod:[0-9a-f]{32}$"},
                           version_ref={"type": "string", "pattern": "^ver:[0-9a-f]{32}$"},
                           answers=_array(_ref("answer"), 60)),
        marking=_object(production_ref={"type": "string", "pattern": "^prod:[0-9a-f]{32}$"},
                        version_ref={"type": "string", "pattern": "^ver:[0-9a-f]{32}$"},
                        total_points=money, dossiers=_array(_ref("dossier"), 3)),
        case_data=_object(currency={"type": "string", "enum": ["EUR"]},
                          source_scale={"type": "string", "enum": ["EUR", "kEUR"]},
                          source_unit_locator=_ref("locator"), base_case=_ref("case"),
                          scenarios=_array(_ref("case"), 10)),
        limitations=_array({"type": "string", "minLength": 1, "maxLength": 500}, 16),
    )
    root["$defs"] = defs
    return root


class _Mismatch(ValueError):
    def __init__(self, code: ParseCode) -> None:
        self.code = code
        super().__init__(code.value)


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _Mismatch(ParseCode.SCHEMA_VALIDATION_FAILURE)
        result[key] = value
    return result


def _nonfinite(_: str) -> NoReturn:
    raise _Mismatch(ParseCode.SCHEMA_VALIDATION_FAILURE)


def _validate(value: object, schema: dict[str, Any], defs: dict[str, Any],
              depth: int = 0) -> None:
    """Validate only our closed, private schema dialect; never coerce or mutate data."""
    if depth > 16:
        raise _Mismatch(ParseCode.CARDINALITY_INVALID)
    if "$ref" in schema:
        _validate(value, defs[schema["$ref"].removeprefix("#/$defs/")], defs, depth)
        return
    if "anyOf" in schema:
        for alternative in schema["anyOf"]:
            try:
                _validate(value, alternative, defs, depth)
                return
            except _Mismatch:
                pass
        raise _Mismatch(ParseCode.SCHEMA_VALIDATION_FAILURE)
    kind = schema["type"]
    expected = {"object": dict, "array": list, "string": str, "integer": int}[kind]
    if type(value) is not expected:  # bool is not an integer, including locator offsets.
        raise _Mismatch(ParseCode.TYPE_MISMATCH)
    if kind == "object":
        data = cast(dict[str, object], value)
        fields = schema["properties"]
        if set(data) != set(fields):
            raise _Mismatch(ParseCode.REQUIRED_FIELD_MISSING if set(fields) - set(data)
                            else ParseCode.SCHEMA_VALIDATION_FAILURE)
        for key, child in data.items():
            _validate(child, fields[key], defs, depth + 1)
    elif kind == "array":
        values = cast(list[object], value)
        if not schema.get("minItems", 0) <= len(values) <= schema["maxItems"]:
            raise _Mismatch(ParseCode.CARDINALITY_INVALID)
        for child in values:
            _validate(child, schema["items"], defs, depth + 1)
    elif kind == "string":
        string = cast(str, value)
        if not schema.get("minLength", 0) <= len(string) <= schema.get("maxLength", MAX_BYTES):
            raise _Mismatch(ParseCode.CARDINALITY_INVALID)
        if "pattern" in schema and re.fullmatch(schema["pattern"], string) is None:
            raise _Mismatch(ParseCode.SCHEMA_VALIDATION_FAILURE)
    elif kind == "integer":
        number = cast(int, value)
        if number < schema.get("minimum", number) or number > schema.get("maximum", number):
            raise _Mismatch(ParseCode.CARDINALITY_INVALID)
    if "enum" in schema and value not in schema["enum"]:
        raise _Mismatch(ParseCode.ENUM_INVALID)


def normalized_prepare_text(output_text: str | None, diagnostic: ParseDiagnostic) -> str:
    """Strict direct JSON -> lossless R3_RESULT_JSON text; no implicit envelope unwrapping."""
    try:
        diagnostic.begin(ParseStage.TEXT_EXTRACT)
        if output_text is None:
            raise _Mismatch(ParseCode.OUTPUT_TEXT_MISSING)
        if not isinstance(output_text, str):
            raise _Mismatch(ParseCode.TYPE_MISMATCH)
        if len(output_text.encode("utf-8")) > MAX_BYTES:
            raise _Mismatch(ParseCode.CARDINALITY_INVALID)
        diagnostic.begin(ParseStage.JSON_DECODE)
        data = json.loads(output_text, object_pairs_hook=_unique, parse_constant=_nonfinite)
        diagnostic.begin(ParseStage.SCHEMA_VALIDATE)
        schema = prepare_output_schema()
        _validate(data, schema, cast(dict[str, Any], schema["$defs"]))
        normalized = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if len(normalized.encode("utf-8")) > MAX_BYTES:
            raise _Mismatch(ParseCode.CARDINALITY_INVALID)
        return normalized
    except _Mismatch as error:
        diagnostic.fail(error.code)
    except (json.JSONDecodeError, RecursionError, UnicodeError):
        diagnostic.fail(ParseCode.JSON_DECODE_FAILURE)
    raise GenerationPortError(GenerationPortErrorCode.INVALID_RESPONSE,
                              "OPENAI_PREPARE_OUTPUT_DOES_NOT_MATCH_CONTRACT") from None
