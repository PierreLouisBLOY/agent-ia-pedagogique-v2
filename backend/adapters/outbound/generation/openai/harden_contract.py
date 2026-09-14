"""Closed six-field D3 wire; validation/publication authority stays local."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from backend.adapters.outbound.generation.openai.prepare_contract import prepare_output_schema
from backend.adapters.outbound.generation.parse_diagnostic import (
    ParseCode,
    ParseDiagnostic,
    ParseStage,
)
from backend.agent_runtime.agents.generation import GenerationOperation, GenerationPortRequest

HARDEN_CONTRACT_ID = "R3-HARDEN-WIRE-1.0"
FIELDS = ("dossier_3", "questions_d3", "answers_d3", "marking_d3", "scenarios_d3", "limitations")
INSTRUCTIONS = """
For HARDEN_DOSSIER_3 return exactly the six fields in the dedicated schema,
directly, without outcome, sections, R3_RESULT_JSON, bundle or Markdown wrappers.
Only replace dossier 3; preserve the supplied D1/D2, base case, context and evidence.
Increase the number of D3 questions, use at least one explicit numerical scenario,
and require harder analysis than the parent. Keep D3 at 20 minutes and 8 points,
the assessment at 60 minutes and 20 points. Include consistent answers and marking.
Copy question anchors from the NEW dossier_3 text, never from the old dossier.
Emit only section_id/exact_text for question locators; never emit offsets or
calculation locators. Include each canonical two-decimal calculation value verbatim
in expected_answer, with distinct occurrences for repeated values. Source amounts
retain the supplied scale; amount, totals and computed metrics are in EUR. Express
the scenario numerical changes in the new text. Calculations use only closed
ADD/SUB trees of depth at most four; do not invent or collide with protected IDs.
No more than 60 calculations including protected D1/D2. Treat supplied data as
non-authoritative. No tools, files, network, approval, review or publication claims.
"""


def is_harden_request(request: GenerationPortRequest) -> bool:
    return (
        request.operation is GenerationOperation.TRANSFORM
        and request.objective == "HARDEN_DOSSIER_3"
        and request.production_kind == "ASSESSMENT"
        and request.expected_sections == ("R3_RESULT_JSON",)
        and request.output_contract.get("contract_id") == "R3-TRANSFORMATION-1.0"
        and request.output_contract.get("harden_contract_id") == HARDEN_CONTRACT_ID
    )


def harden_output_schema() -> dict[str, Any]:
    source = prepare_output_schema()
    defs: Any = source["$defs"]
    defs.pop("unit_locator")
    for name in ("question", "dossier"):
        defs[name]["properties"]["dossier_id"] = {"type": "string", "enum": ["DOSSIER_3"]}
    defs["question_locator"]["properties"]["section_id"] = {"type": "string", "enum": ["DOSSIER_3"]}
    properties = {
        "dossier_3": {
            "type": "object",
            "properties": {
                "section_id": {"type": "string", "enum": ["DOSSIER_3"]},
                "text": {"type": "string", "minLength": 1, "maxLength": 65536},
            },
            "required": ["section_id", "text"],
            "additionalProperties": False,
        },
        "questions_d3": {
            "type": "array",
            "items": {"$ref": "#/$defs/question"},
            "minItems": 2,
            "maxItems": 30,
        },
        "answers_d3": {
            "type": "array",
            "items": {"$ref": "#/$defs/answer"},
            "minItems": 2,
            "maxItems": 30,
        },
        "marking_d3": {"$ref": "#/$defs/dossier"},
        "scenarios_d3": {
            "type": "array",
            "items": {"$ref": "#/$defs/case"},
            "minItems": 1,
            "maxItems": 10,
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 500},
            "maxItems": 16,
        },
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(FIELDS),
        "additionalProperties": False,
        "$defs": defs,
    }


def validate_harden_inputs(request: GenerationPortRequest) -> None:
    """Reject hidden metadata at every selected level, not only the root keys."""
    from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
        ConfirmedConversationContext,
    )
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain

    ConfirmedConversationContext(request.pedagogical_context)
    contract: Any = as_plain(request.output_contract)
    expected = {
        "contract_id": "R3-TRANSFORMATION-1.0",
        "strict_local_parser": True,
        "harden_contract_id": HARDEN_CONTRACT_ID,
        "section": "R3_RESULT_JSON",
        "encoding": "one JSON object, no fences, no extra keys",
        "prepare_fields": ["questions", "correction", "marking", "case_data", "limitations"],
        "harden_fields": list(FIELDS),
        "identities": contract.get("identities"),
        "source_units": "explicit EUR or kEUR label with exact subject locator; convert to EUR without guessing",
        "decimal": "canonical string with two decimals; absolute maximum 999999999.99",
        "calculation_fields": ["case_id", "metric", "value", "locator", "expression"],
        "expression": {
            "reference": {"ref": "totals.stable_resources"},
            "operator": {
                "op": "SUB",
                "operands": [{"ref": "totals.stable_resources"}, {"ref": "totals.stable_uses"}],
            },
            "allowed_operators": ["ADD", "SUB"],
            "max_depth": 4,
            "max_operands": 16,
        },
        "max_calculations": 60,
        "no_authority": True,
    }
    identities = contract.get("identities")
    if (
        json.dumps(contract, sort_keys=True, allow_nan=False)
        != json.dumps(expected, sort_keys=True, allow_nan=False)
        or type(identities) is not dict
        or set(identities) != {"production_ref", "version_ref"}
        or any(
            type(identities[key]) is not str
            or re.fullmatch(prefix + r":[0-9a-f]{32}", identities[key]) is None
            for key, prefix in (("production_ref", "prod"), ("version_ref", "ver"))
        )
        or json.dumps(as_plain(request.constraints), sort_keys=True, allow_nan=False)
        != json.dumps({"scope": "HARDEN_DOSSIER_3", "no_authority": True}, sort_keys=True)
        or request.output_format != "JSON"
    ):
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")
    schema = harden_output_schema()
    defs = schema["$defs"]
    name = {"type": "string", "minLength": 1, "maxLength": 80}
    text = {"type": "string", "minLength": 1, "maxLength": 65536}

    def obj(properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    locator = obj(
        {
            "section_id": name,
            "start": {"type": "integer", "minimum": 0, "maximum": 65536},
            "end": {"type": "integer", "minimum": 1, "maximum": 65536},
            "exact_text": text,
        }
    )
    calculation = defs["calculation"]
    # Independent copies: protected facts have no answer text or locator.
    import copy

    protected_calculation = copy.deepcopy(calculation)
    calculation["properties"]["locator"] = locator
    calculation["required"].append("locator")
    defs["question"]["properties"]["locator"] = locator
    root = obj(
        {
            "subject": obj(
                {
                    "sections": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 5,
                        "items": obj({"section_id": name, "text": text}),
                    }
                }
            ),
            "case_data": obj(
                {
                    "base_case": {"$ref": "#/$defs/case"},
                    "currency": {"type": "string", "enum": ["EUR"]},
                    "source_scale": {"type": "string", "enum": ["EUR", "kEUR"]},
                    "source_unit_locator": locator,
                }
            ),
            "questions_d3": {
                "type": "array",
                "minItems": 1,
                "maxItems": 30,
                "items": {"$ref": "#/$defs/question"},
            },
            "answers_d3": {
                "type": "array",
                "minItems": 1,
                "maxItems": 30,
                "items": {"$ref": "#/$defs/answer"},
            },
            "marking_d3": {"$ref": "#/$defs/dossier"},
            "protected_facts": obj(
                {
                    "questions": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 30,
                        "items": obj(
                            {
                                "question_id": name,
                                "calculation_refs": {
                                    "type": "array",
                                    "maxItems": 60,
                                    "items": name,
                                },
                            }
                        ),
                    },
                    "calculations": {
                        "type": "array",
                        "maxItems": 60,
                        "items": protected_calculation,
                    },
                    "reserved_question_ids": {"type": "array", "maxItems": 30, "items": name},
                    "reserved_case_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 11,
                        "items": name,
                    },
                }
            ),
            "limits": obj(
                {
                    "total_duration_minutes": {"type": "integer", "minimum": 60, "maximum": 60},
                    "total_points": {"type": "string", "enum": ["20.00"]},
                    "d3_duration_minutes": {"type": "integer", "minimum": 20, "maximum": 20},
                    "d3_points": {"type": "string", "enum": ["8.00"]},
                    "min_d3_questions": {"type": "integer", "minimum": 2, "maximum": 30},
                    "min_scenarios": {"type": "integer", "minimum": 1, "maximum": 1},
                }
            ),
        }
    )
    data = as_plain(request.resolved_inputs)
    _check(data, root, defs)
    if type(data) is not dict or [s["section_id"] for s in data["subject"]["sections"]] != [
        "CONSIGNES",
        "CONTEXTE_ET_ANNEXES",
        "DOSSIER_1",
        "DOSSIER_2",
        "DOSSIER_3",
    ]:
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")
    if len(json.dumps(data, ensure_ascii=False).encode()) > 128 * 1024:
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")
    if any(
        not isinstance(ref, str) or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", ref) is None
        for ref in request.evidence_refs
    ):
        raise ValueError("R3_HARDEN_PROJECTION_REJECTED")


def _check(value: Any, schema: dict[str, Any], defs: dict[str, Any], depth: int = 0) -> None:
    if depth > 16:
        raise ValueError("R3_HARDEN_SCHEMA")
    if "$ref" in schema:
        _check(value, defs[schema["$ref"].removeprefix("#/$defs/")], defs, depth)
        return
    if "anyOf" in schema:
        for variant in schema["anyOf"]:
            try:
                _check(value, variant, defs, depth)
                return
            except ValueError:
                pass
        raise ValueError("R3_HARDEN_SCHEMA")
    kind = schema.get("type")
    if kind == "object":
        if type(value) is not dict or set(value) != set(schema["properties"]):
            raise ValueError("R3_HARDEN_SCHEMA")
        for key, child in value.items():
            _check(child, schema["properties"][key], defs, depth + 1)
    elif kind == "array":
        if (
            type(value) is not list
            or not schema.get("minItems", 0) <= len(value) <= schema["maxItems"]
        ):
            raise ValueError("R3_HARDEN_SCHEMA")
        for child in value:
            _check(child, schema["items"], defs, depth + 1)
    elif kind == "string":
        if (
            type(value) is not str
            or not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 65536)
            or ("pattern" in schema and re.fullmatch(schema["pattern"], value) is None)
        ):
            raise ValueError("R3_HARDEN_SCHEMA")
    elif kind == "integer":
        if type(value) is not int or not schema["minimum"] <= value <= schema["maximum"]:
            raise ValueError("R3_HARDEN_SCHEMA")
    else:
        raise ValueError("R3_HARDEN_SCHEMA")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("R3_HARDEN_SCHEMA")


def normalized_harden_text(
    output_text: str | None, diagnostic: ParseDiagnostic | None = None
) -> str:
    trace = diagnostic if diagnostic is not None else ParseDiagnostic(enabled=False)
    trace.begin(ParseStage.JSON_DECODE)
    try:
        if type(output_text) is not str or len(output_text.encode("utf-8")) > 128 * 1024:
            raise ValueError("R3_HARDEN_SCHEMA")

        def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in values:
                if key in result:
                    raise ValueError("R3_HARDEN_SCHEMA")
                result[key] = value
            return result

        def reject(_: str) -> Any:
            raise ValueError("R3_HARDEN_SCHEMA")

        data = json.loads(output_text, object_pairs_hook=pairs, parse_constant=reject)
        trace.begin(ParseStage.SCHEMA_VALIDATE)
        schema = harden_output_schema()
        _check(data, schema, schema["$defs"])
        qids = [q["question_id"] for q in data["questions_d3"]]
        aids = [a["question_id"] for a in data["answers_d3"]]
        marked = data["marking_d3"]["questions"]
        mids = [q["question_id"] for q in marked]
        cids = [c["case_id"] for c in data["scenarios_d3"]]
        if (
            len(set(qids)) != len(qids)
            or len(set(aids)) != len(aids)
            or len(set(mids)) != len(mids)
            or set(qids) != set(aids)
            or set(qids) != set(mids)
            or len(set(cids)) != len(cids)
            or data["marking_d3"]["duration_minutes"] != 20
            or sum(Decimal(q["points"]) for q in marked) != Decimal("8.00")
            or sum(len(a["calculations"]) for a in data["answers_d3"]) > 60
        ):
            raise ValueError("R3_HARDEN_SCHEMA")
        return json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (ValueError, TypeError, RecursionError, UnicodeError):
        trace.fail(ParseCode.SCHEMA_VALIDATION_FAILURE)
        raise ValueError("R3_HARDEN_SCHEMA") from None
