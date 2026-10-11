"""Closed HARDEN compatibility; only local synthetic transport and resolver."""
import copy
import json
from dataclasses import replace

import pytest

from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.infrastructure.composition.factories.r3_harden_execution import build_harden_adapter
from backend.infrastructure.composition.factories.r3_harden_profile import load_harden_profile
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.support.r3_d3_fixtures import synthetic_harden_request
from tests.unit.test_r3_harden_execution import fixture


@pytest.mark.parametrize("historical", [False, True])
def test_closed_harden_accepts_explicit_identity_and_historical_absence(historical):
    request = synthetic_harden_request()
    contract = as_plain(request.output_contract)
    identity = contract["operation_identity"]
    assert identity["step_id"] == request.source_step_id
    if historical:
        contract.pop("operation_identity")
    wire = build_openai_request(
        request=replace(request, output_contract=contract), model_profile=load_harden_profile()[1]
    )
    carried = json.loads(wire.input_json)["output_contract"]
    if historical:
        assert "operation_identity" not in carried
    else:
        assert carried["operation_identity"] == identity
    assert set(wire.output_schema["properties"]) == {
        "dossier_3", "questions_d3", "answers_d3", "marking_d3", "scenarios_d3", "limitations"
    }


@pytest.mark.parametrize("fault", [
    "extra", "missing", "version", "value", "self_parent", "step", "null", "outer_extra"
])
def test_harden_metadata_substitution_stops_before_reservation_or_credential(fault):
    data = fixture()
    request = data["request"]
    contract = copy.deepcopy(as_plain(request.output_contract))
    identity = contract["operation_identity"]
    if fault == "extra":
        identity["authority"] = "allow"
    elif fault == "missing":
        identity.pop("correlation_id")
    elif fault == "version":
        identity["contract_id"] = "OPERATION-IDENTITY-99.0"
    elif fault == "value":
        identity["run_id"] = "<instruction>"
    elif fault == "self_parent":
        identity["parent_step_id"] = identity["step_id"]
    elif fault == "step":
        identity["step_id"] = "step:substituted"
    elif fault == "null":
        contract["operation_identity"] = None
    else:
        contract["authority"] = "allow"
    adapter = build_harden_adapter(**data["args"])
    with pytest.raises(ValueError, match="OPERATION_IDENTITY_REJECTED|R3_HARDEN_PROJECTION_REJECTED"):
        adapter.generate(request=replace(request, output_contract=contract))
    assert data["events"] == []
