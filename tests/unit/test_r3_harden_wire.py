"""Closed HARDEN wire and deterministic new-D3-only materialization."""

import copy
import json
from dataclasses import replace
from typing import Any

import pytest

from backend.adapters.outbound.generation.openai.harden_contract import (
    FIELDS,
    harden_output_schema,
    normalized_harden_text,
)
from backend.adapters.outbound.generation.openai.harden_materialization import (
    materialized_harden_text,
)
from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.infrastructure.composition.factories.r3_harden_profile import load_harden_profile
from backend.infrastructure.composition.factories.r3_harden_serialization import (
    r3_harden_count_parameters,
    r3_harden_request_parameters,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, encoded
from tests.support.r3_d3_fixtures import synthetic_harden_request, wire_output


def test_six_fields_new_unicode_anchors_and_values_preserved() -> None:
    request = synthetic_harden_request()
    value = wire_output()
    original = copy.deepcopy(value)
    output = json.loads(materialized_harden_text(json.dumps(value), request))
    assert set(output) == set(FIELDS)
    for before, after in zip(original["answers_d3"], output["answers_d3"], strict=True):
        for old, new in zip(before["calculations"], after["calculations"], strict=True):
            assert {k: v for k, v in new.items() if k != "locator"} == old
            loc = new["locator"]
            assert (
                after["expected_answer"][loc["start"] : loc["end"]]
                == loc["exact_text"]
                == old["value"]
            )
    for question in output["questions_d3"]:
        loc = question["locator"]
        assert output["dossier_3"]["text"][loc["start"] : loc["end"]] == loc["exact_text"]
    assert wire_output() == original
    assert "start" not in harden_output_schema()["$defs"]["question_locator"]["properties"]


@pytest.mark.parametrize(
    "kind",
    [
        "extra",
        "missing",
        "wrapper",
        "offset",
        "calc_locator",
        "bool",
        "depth",
        "wrong_dossier",
        "wrong_points",
        "same_ids",
        "volume",
        "no_scenario",
    ],
)
def test_closed_wire_rejects_invalid_shapes(kind: str) -> None:
    value = wire_output()
    if kind == "extra":
        value["approval"] = True
    elif kind == "missing":
        del value["limitations"]
    elif kind == "wrapper":
        value = {"sections": value}
    elif kind == "offset":
        value["questions_d3"][0]["locator"]["start"] = 0
    elif kind == "calc_locator":
        value["answers_d3"][0]["calculations"][0]["locator"] = {}
    elif kind == "bool":
        value["marking_d3"]["duration_minutes"] = True
    elif kind == "depth":
        node: Any = {"ref": "totals.stable_resources"}
        for _ in range(20):
            node = {"op": "ADD", "operands": [node, {"ref": "totals.stable_uses"}]}
        value["answers_d3"][0]["calculations"][0]["expression"] = node
    elif kind == "wrong_dossier":
        value["questions_d3"][0]["dossier_id"] = "DOSSIER_2"
    elif kind == "wrong_points":
        value["marking_d3"]["questions"][0]["points"] = "7.00"
    elif kind == "same_ids":
        value["questions_d3"][1]["question_id"] = value["questions_d3"][0]["question_id"]
    elif kind == "volume":
        value["limitations"] = ["x" * 140000]
    else:
        value["scenarios_d3"] = []
    with pytest.raises(ValueError):
        normalized_harden_text(json.dumps(value))


@pytest.mark.parametrize(
    "raw", ['{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}', "```json\n{}\n```", "{}", "null"]
)
def test_json_grammar_and_wrappers_are_closed(raw: str) -> None:
    with pytest.raises(ValueError):
        normalized_harden_text(raw)


@pytest.mark.parametrize(
    "kind", ["old_anchor", "ambiguous", "reserved_id", "reserved_case", "missing_value"]
)
def test_materialization_does_not_repair_or_redistribute(kind: str) -> None:
    value = wire_output()
    request = synthetic_harden_request()
    data: Any = as_plain(request.resolved_inputs)
    if kind == "old_anchor":
        value["questions_d3"][0]["locator"]["exact_text"] = "OLD ABSENT ANCHOR"
    elif kind == "ambiguous":
        value["dossier_3"]["text"] += value["dossier_3"]["text"]
    elif kind == "reserved_id":
        qid = data["protected_facts"]["reserved_question_ids"][0]
        value["questions_d3"][0]["question_id"] = qid
        value["answers_d3"][0]["question_id"] = qid
        value["marking_d3"]["questions"][0]["question_id"] = qid
    elif kind == "reserved_case":
        value["scenarios_d3"][0]["case_id"] = data["protected_facts"]["reserved_case_ids"][0]
    else:
        value["answers_d3"][0]["expected_answer"] = "Absent number"
    with pytest.raises(ValueError):
        materialized_harden_text(json.dumps(value), request)


def test_profile_and_seven_count_fields_exact_no_clamp() -> None:
    provider, model = load_harden_profile()
    request = synthetic_harden_request()
    wire = build_openai_request(request=request, model_profile=model)
    create = r3_harden_request_parameters(wire, model_profile=model)
    count = r3_harden_count_parameters(wire, model_profile=model)
    assert set(count) == {
        "model",
        "instructions",
        "input",
        "text",
        "reasoning",
        "tools",
        "tool_choice",
    }
    assert count == {k: create[k] for k in count}
    assert encoded(create) == encoded(json.loads(encoded(create)))
    assert create["max_output_tokens"] == 8192 and create["store"] is False
    assert model.invocation_limits.max_cost is None
    assert provider.profile_id.value == "openai.r3.harden.private"
    for limit in (4096, 8191, 8193):
        with pytest.raises(ValueError):
            r3_harden_request_parameters(
                replace(wire, max_output_tokens=limit), model_profile=model
            )
    with pytest.raises(ValueError):
        build_openai_request(
            request=replace(request, output_contract={"contract_id": "R3-TRANSFORMATION-1.0"}),
            model_profile=model,
        )


@pytest.mark.parametrize(
    "level",
    [
        "root",
        "subject",
        "question",
        "answer",
        "protected",
        "context",
        "evidence",
        "contract",
        "contract_bool",
        "constraints_bool",
    ],
)
def test_positive_projection_rejects_extra_nested_data(level: str) -> None:
    request = synthetic_harden_request()
    _, model = load_harden_profile()
    data: Any = as_plain(request.resolved_inputs)
    if level == "contract":
        request = replace(request, output_contract={**request.output_contract, "private": "marker"})
    elif level == "contract_bool":
        request = replace(
            request, output_contract={**request.output_contract, "strict_local_parser": 1}
        )
    elif level == "constraints_bool":
        request = replace(request, constraints={**request.constraints, "no_authority": 1})
    elif level == "context":
        request = replace(
            request, pedagogical_context={**request.pedagogical_context, "private": "marker"}
        )
    elif level == "evidence":
        request = replace(request, evidence_refs=("C:/private/file",))
    else:
        target = {
            "root": data,
            "subject": data["subject"],
            "question": data["questions_d3"][0],
            "answer": data["answers_d3"][0],
            "protected": data["protected_facts"],
        }[level]
        target["private"] = "SYNTHETIC_PRIVATE_MARKER"
        request = replace(request, resolved_inputs=data)
    with pytest.raises(ValueError):
        build_openai_request(request=request, model_profile=model)
