"""Derive D3 locators only, without repairing or publishing provider content."""

import json
from typing import cast

from backend.adapters.outbound.generation.openai.harden_contract import (
    is_harden_request,
    normalized_harden_text,
)
from backend.adapters.outbound.generation.openai.locator_materialization import (
    calculation_locators,
    materialize_anchor,
)
from backend.adapters.outbound.generation.parse_diagnostic import ParseDiagnostic
from backend.agent_runtime.agents.generation import GenerationPortRequest
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data


def materialized_harden_text(
    output_text: str | None,
    request: GenerationPortRequest,
    diagnostic: ParseDiagnostic | None = None,
) -> str:
    if not is_harden_request(request):
        raise ValueError("R3_HARDEN_OPERATION_REJECTED")
    data = json.loads(normalized_harden_text(output_text, diagnostic))
    projection = object_data(request.resolved_inputs)
    protected = object_data(projection["protected_facts"])
    reserved = set(cast(tuple[str, ...], protected["reserved_question_ids"]))
    reserved_cases = set(cast(tuple[str, ...], protected["reserved_case_ids"]))
    minimum = object_data(projection["limits"])["min_d3_questions"]
    if type(minimum) is not int:
        raise ValueError("R3_HARDEN_DEPENDENCY")
    if (
        len(data["questions_d3"]) < minimum
        or any(q["question_id"] in reserved for q in data["questions_d3"])
        or any(c["case_id"] in reserved_cases for c in data["scenarios_d3"])
        or len(items(protected["calculations"]))
        + sum(len(a["calculations"]) for a in data["answers_d3"])
        > 60
    ):
        raise ValueError("R3_HARDEN_DEPENDENCY")
    for question in data["questions_d3"]:
        anchor = question["locator"]
        question["locator"] = materialize_anchor(
            anchor["section_id"], anchor["exact_text"], [data["dossier_3"]]
        )
    for answer in data["answers_d3"]:
        locators = calculation_locators(
            answer["question_id"],
            answer["expected_answer"],
            tuple(c["value"] for c in answer["calculations"]),
        )
        for calculation, locator in zip(answer["calculations"], locators, strict=True):
            calculation["locator"] = locator
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
