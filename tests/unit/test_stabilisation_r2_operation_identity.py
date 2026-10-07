"""Operation correlation at real Application dispatchs, with declared local doubles."""
from dataclasses import replace
from secrets import token_hex

import pytest

from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity
from tests.support.p0_generation_double import P0GenerationDouble
from tests.support.r3_fakes import harness, run
from tests.unit.test_p0_agentic_routing import TechnicalCritic, candidate, identity
from tests.unit.test_p0_creation_contract import service


def test_two_p0_reviews_preserve_source_parent_and_are_never_replayed():
    critic = TechnicalCritic()
    observed = []
    for _ in range(2):
        app = service(P0GenerationDouble())
        app.review = P0ReviewAdapter(critic, authorize=lambda request: True)
        view, _ = candidate(app)
        bundle = app.records[view["version_ref"]]
        before = bundle.sha256
        command = token_hex(16)
        body = {"command_id": command, **identity(view)}
        result = app.execute("review", body)
        assert app.execute("review", body) == result
        port = critic.requests[-1]
        meta = port.output_contract["operation_identity"]
        assert meta["run_id"] == "op:" + command
        assert meta["step_id"] == port.source_step_id == "step:" + command
        assert meta["parent_step_id"] == bundle.data["lineage"]["source_step_id"]
        assert meta["correlation_id"] == bundle.data["lineage"]["conversation_id"]
        assert result["report"]["bundle_sha256"] == before == bundle.sha256
        observed.append(meta)
    assert len(critic.requests) == 2
    assert observed[0]["run_id"] != observed[1]["run_id"]


def test_r3_reserved_operation_reaches_generation_and_review_with_correlation():
    conv, app, jobs, prod = harness()
    original = fingerprint(prod.data)
    prepared, preparation = run(conv, app, "assessment-preparations", prod)
    assert prepared["state"] == "SUCCEEDED"
    assert app.service.execute(preparation)["operation_ref"] == prepared["operation_ref"]
    reviewed, review = run(conv, app, "reviews", prod)
    assert reviewed["state"] == "SUCCEEDED"
    assert app.service.execute(review)["operation_ref"] == reviewed["operation_ref"]
    assert len(jobs.generation.calls) == len(jobs.reviewer.calls) == 1
    for receipt, port, envelope in zip(
            (prepared, reviewed), (jobs.generation.calls[0], jobs.reviewer.calls[0]),
            jobs.requests, strict=True):
        meta = port.output_contract["operation_identity"]
        assert meta == envelope.identity.as_dict()
        assert meta["run_id"] == receipt["operation_ref"]
        assert meta["step_id"] == port.source_step_id
        assert meta["correlation_id"] == prod.conversation_id
    assert jobs.generation.calls[0].source_step_id != jobs.reviewer.calls[0].source_step_id
    assert fingerprint(prod.data) == original
    with pytest.raises(ValueError, match="R3_JOB_IDENTITY"):
        replace(jobs.requests[0], identity=jobs.requests[1].identity)


@pytest.mark.parametrize("fault", ["parent", "field", "contract", "value"])
def test_operation_metadata_rejects_substitution_before_a_port(fault):
    data = OperationIdentity("op:one", "step:one", "step:source", "conv:one").as_dict()
    if fault == "parent":
        data["parent_step_id"] = data["step_id"]
    elif fault == "field":
        data["authority"] = "allowed"
    elif fault == "contract":
        data["contract_id"] = "OPERATION-IDENTITY-99.0"
    else:
        data["run_id"] = "<instruction>"
    with pytest.raises(ValueError, match="OPERATION_IDENTITY_REJECTED"):
        OperationIdentity.from_mapping(data)


@pytest.mark.parametrize("fault", ["version", "missing", "extra"])
def test_p0_envelope_contract_refuses_unknown_or_incomplete_shapes_before_port(fault):
    app = service(P0GenerationDouble())
    captured = []
    critic = TechnicalCritic()
    app.review = P0ReviewAdapter(critic, authorize=lambda request: captured.append(request) or True)
    view, _ = candidate(app)
    app.execute("review", {"command_id": token_hex(16), **identity(view)})
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain

    request = as_plain(captured[0])
    if fault == "version":
        request["contract_id"] = "P0-INDEPENDENT-REVIEW-REQUEST-99.0"
    elif fault == "missing":
        request.pop("operation_identity")
    else:
        request["authority"] = "allow"
    with pytest.raises(ValueError, match="P0_REVIEW_REQUEST_"):
        app.review.review(request=request)
    assert len(critic.requests) == 1
